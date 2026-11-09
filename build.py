import base64, json, pathlib, re, sys, random, hashlib

root = pathlib.Path(__file__).parent
tpl = (root / "src/template.html").read_text(encoding="utf-8")
meta = json.loads((root / "src/subjects.json").read_text(encoding="utf-8"))

# 汇总所有科目题库：src/data/<subject>.json（mnemos.json 是口诀表，单独处理）
questions = []
for f in sorted((root / "src/data").glob("*.json")):
    if f.name == "mnemos.json":
        continue
    sub = f.stem.split("-")[0]          # 文件名前缀即科目：hist-1.json / hist-2.json → hist
    bank = json.loads(f.read_text(encoding="utf-8"))
    for q in bank:
        q["sub"] = sub
    questions += bank
    print(f"  {f.name}: {len(bank)} 题 → {sub}")

# 记忆口诀表：按专题索引 {t: {m: 口诀, k: 知识关联}}，注入 window.__MN__
MNEMO = json.loads((root / "src/data/mnemos.json").read_text(encoding="utf-8"))

# 统一分配全局唯一 id，并按题干哈希稳定打乱选项
seen = {}
for q in questions:
    seen[q["sub"]] = seen.get(q["sub"], 0) + 1
    q["id"] = f"{q['sub']}-{seen[q['sub']]:03d}"
    seed = int(hashlib.md5(q["q"].encode("utf-8")).hexdigest()[:8], 16)
    rnd = random.Random(seed)
    order = list(range(len(q["o"])))
    rnd.shuffle(order)
    q["o"] = [q["o"][i] for i in order]
    q["a"] = order.index(q["a"])

# 每科配额统计，供前端显示
for s in meta:
    pool = [q for q in questions if q.get("sub") == s["id"]]
    s["count"] = len(pool)
    s["d"] = {str(k): sum(1 for q in pool if q["d"] == k) for k in (1, 2, 3, 4)}
    if not s.get("planned") and len(pool) < 60:
        print(f"  ! {s['name']} 题量偏少（{len(pool)}），建议至少 250 题", file=sys.stderr)

if not questions:
    raise SystemExit("没有找到任何题库：src/data/*.json")

payload_q = json.dumps(questions, ensure_ascii=False, separators=(",", ":"))
payload_s = json.dumps(meta, ensure_ascii=False, separators=(",", ":"))

# 题库外置：不再内嵌进 HTML（占首屏下载量大头），改为独立的 questions.js
# 由前端启动时动态 <script> 注入（window.__QB__），file:// 下同样可用
out = tpl.replace("__SUBJECTS__", payload_s)

# 外链素材：模板里写 __ASSET:文件名__，构建时替换为 assets/ 相对路径
# （不再 base64 内联——内联会让首屏必须下载全部图片，加载慢；外链后图片只在
#   结算屏首次显示时才按需加载，index.html 体积从 ~1MB 降到 ~360KB）
assets_dir = root / "src/assets"


# 内容版本号：题库或任一素材变化 → VER 变化 → SW 换新缓存、素材 URL 失效旧缓存
import hashlib
ver_src = payload_q.encode() + json.dumps(MNEMO, ensure_ascii=False).encode() + b"".join(sorted(f.read_bytes() for f in assets_dir.iterdir() if f.is_file()))
VER = hashlib.md5(ver_src).hexdigest()[:10]

ASSET_FILES = sorted(f.name for f in assets_dir.iterdir() if f.is_file())


def link_asset(m):
    if m.group(1) not in ASSET_FILES:
        raise SystemExit(f"缺少素材文件：src/assets/{m.group(1)}")
    return f"assets/{m.group(1)}?v={VER}"


out = re.sub(r"__ASSET:([\w.\-]+)__", link_asset, out)

# Service Worker：预缓存全部静态资源，二次打开秒开、断网可玩
precache = ["./", "index.html", f"questions.js?v={VER}"] + [f"assets/{n}?v={VER}" for n in ASSET_FILES]
SW_JS = """/* 由 build.py 生成，请勿手改 · 版本 __VER__ */
const VER = '__VER__';
const CACHE = 'cgq-' + VER;
const PRECACHE = %s;

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if(req.method !== 'GET') return;
  const url = new URL(req.url);
  if(url.origin !== location.origin) return;

  /* 页面导航：网络优先（在线拿最新版），失败回退缓存（离线可玩） */
  if(req.mode === 'navigate' || req.destination === 'document'){
    e.respondWith(
      fetch(req).then(r => {
        if(r.ok){
          const cp = r.clone();
          caches.open(CACHE).then(c => { c.put(req, cp); c.put('./', r.clone()); });
        }
        return r;
      }).catch(() =>
        caches.match('./').then(m => m || caches.match(req) || caches.match('index.html'))
      )
    );
    return;
  }

  /* 其余静态资源：缓存优先，未命中才走网络并写入缓存 */
  e.respondWith(
    caches.match(req).then(m => m || fetch(req).then(r => {
      if(r.ok){
        const cp = r.clone();
        caches.open(CACHE).then(c => c.put(req, cp));
      }
      return r;
    }))
  );
});
""" % json.dumps(precache)
SW_JS = SW_JS.replace("__VER__", VER)

out = out.replace("__VER__", VER)

assert "__QUESTIONS__" not in out and "__SUBJECTS__" not in out and "__VER__" not in out

dist = root / "dist"
dist.mkdir(exist_ok=True, parents=True)
(dist / "index.html").write_text(out, encoding="utf-8")
(dist / "questions.js").write_text("window.__QB__=" + payload_q + ";\nwindow.__MN__=" + json.dumps(MNEMO, ensure_ascii=False, separators=(",", ":")) + ";", encoding="utf-8")
(dist / "sw.js").write_text(SW_JS, encoding="utf-8")
# 复制素材到 dist/assets/
adist = dist / "assets"
if not adist.exists():
    adist.mkdir()
for f in sorted(assets_dir.iterdir()):
    if f.is_file():
        (adist / f.name).write_bytes(f.read_bytes())
print(f"questions: {len(questions)} | subjects: {len(meta)} | size KB: {round(len(out.encode())/1024, 1)}")

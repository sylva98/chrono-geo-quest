import json, pathlib, sys, random, hashlib

root = pathlib.Path(__file__).parent
tpl = (root / "src/template.html").read_text(encoding="utf-8")
meta = json.loads((root / "src/subjects.json").read_text(encoding="utf-8"))

# 汇总所有科目题库：src/data/<subject>.json
questions = []
for f in sorted((root / "src/data").glob("*.json")):
    sub = f.stem.split("-")[0]          # 文件名前缀即科目：hist-1.json / hist-2.json → hist
    bank = json.loads(f.read_text(encoding="utf-8"))
    for q in bank:
        q["sub"] = sub
    questions += bank
    print(f"  {f.name}: {len(bank)} 题 → {sub}")

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
    s["d"] = {str(k): sum(1 for q in pool if q["d"] == k) for k in (1, 2, 3)}
    if not s.get("planned") and len(pool) < 60:
        print(f"  ! {s['name']} 题量偏少（{len(pool)}），建议至少 250 题", file=sys.stderr)

if not questions:
    raise SystemExit("没有找到任何题库：src/data/*.json")

payload_q = json.dumps(questions, ensure_ascii=False, separators=(",", ":"))
payload_s = json.dumps(meta, ensure_ascii=False, separators=(",", ":"))

out = tpl.replace("__QUESTIONS__", payload_q).replace("__SUBJECTS__", payload_s)
assert "__QUESTIONS__" not in out and "__SUBJECTS__" not in out

dist = root / "dist"
dist.mkdir(exist_ok=True, parents=True)
(dist / "index.html").write_text(out, encoding="utf-8")
print(f"questions: {len(questions)} | subjects: {len(meta)} | size KB: {round(len(out.encode())/1024, 1)}")

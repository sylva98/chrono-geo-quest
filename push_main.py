#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把本地 master 的源码树同步到 GitHub main 分支。
沙箱无法直接 git push（github.com:443 不通），改走 api.github.com 的 Git Data API。

两个坑：
1. 不含 base_tree 的全量树若文件多，请求会被网关拦（404）→ 分批累加建树。
2. token 无 workflow 权限，写 .github/workflows/* 会 404 → 跳过该文件，
   以远端树为基底，让远端已有的 workflow 原样保留。

用法：python3 push_main.py "提交说明"
"""
import base64, json, subprocess, sys, pathlib, time
import requests

ROOT = pathlib.Path(__file__).resolve().parent
REPO = "sylva98/chrono-geo-quest"
BRANCH = "main"
TOKEN = pathlib.Path("/root/.gh_token_chrono").read_text().strip()
CACHE = ROOT / ".blob_cache.json"
MSG = sys.argv[1] if len(sys.argv) > 1 else "sync: 源码同步"
BATCH = 12
SKIP = (".github/workflows/",)   # token 无 workflow 权限

S = requests.Session()
S.headers.update({"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json",
                  "User-Agent": "chrono-deploy"})


def api(method, path, **kw):
    for attempt in range(4):
        try:
            r = S.request(method, "https://api.github.com" + path, timeout=180, **kw)
            if r.status_code < 300:
                return r.json() if r.text else {}
            print("  !", method, path, r.status_code, r.text[:160])
        except Exception as e:
            print("  !", method, path, type(e).__name__, str(e)[:120])
        time.sleep(2 + attempt * 2)
    print("FAILED", method, path)
    sys.exit(1)


def local_files():
    out = subprocess.run(["git", "-C", str(ROOT), "ls-tree", "-r", "-z", "master"],
                         capture_output=True, check=True).stdout
    items = []
    for ch in out.split(b"\0"):
        if not ch:
            continue
        meta, path = ch.split(b"\t", 1)
        mode, typ, sha = meta.decode().split()
        items.append((path.decode(), mode, sha))
    return items


def blob_bytes(sha):
    return subprocess.run(["git", "-C", str(ROOT), "cat-file", "blob", sha],
                          capture_output=True, check=True).stdout


ref = api("GET", f"/repos/{REPO}/git/ref/heads/{BRANCH}")
parent = ref["object"]["sha"]
base_tree = api("GET", f"/repos/{REPO}/git/commits/{parent}")["tree"]["sha"]
print("远端 main HEAD:", parent[:9], "tree:", base_tree[:9])

remote = api("GET", f"/repos/{REPO}/git/trees/{base_tree}?recursive=1")
remote_paths = {e["path"] for e in remote.get("tree", []) if e["type"] == "blob"}

cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
items = local_files()
local_paths = {p for p, _, _ in items}

entries = []
for path, mode, sha in items:
    if path.startswith(SKIP):
        print(f"  skip  {path}（无 workflow 权限，保留远端版本）")
        continue
    bs = blob_bytes(sha)
    ck = f"{sha}:{len(bs)}"
    if ck in cache:
        bsha = cache[ck]
    else:
        r = api("POST", f"/repos/{REPO}/git/blobs",
                json={"content": base64.b64encode(bs).decode(), "encoding": "base64"})
        bsha = r["sha"]
        cache[ck] = bsha
        CACHE.write_text(json.dumps(cache))
        print(f"  blob  {path} {len(bs)}B")
    entries.append({"path": path, "mode": mode, "type": "blob", "sha": bsha})

# 远端有、本地已删除的文件 → 置空
for p in sorted(remote_paths - local_paths):
    entries.append({"path": p, "mode": "100644", "type": "blob", "sha": None})
    print(f"  del   {p}")

print(f"共 {len(entries)} 项变更，分批建树 ...")
tree_sha = base_tree
for i in range(0, len(entries), BATCH):
    chunk = entries[i:i + BATCH]
    r = api("POST", f"/repos/{REPO}/git/trees", json={"base_tree": tree_sha, "tree": chunk})
    tree_sha = r["sha"]
    print(f"  tree {i // BATCH + 1}: {tree_sha[:9]} (+{len(chunk)})")

commit = api("POST", f"/repos/{REPO}/git/commits",
             json={"message": MSG, "tree": tree_sha, "parents": [parent]})
api("PATCH", f"/repos/{REPO}/git/refs/heads/{BRANCH}",
    json={"sha": commit["sha"], "force": True})
print("pushed", commit["sha"][:9], "items:", len(entries), "tree:", tree_sha[:9])

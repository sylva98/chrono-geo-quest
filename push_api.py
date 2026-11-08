import base64, json, pathlib, sys, time
import requests

ROOT = pathlib.Path(__file__).resolve().parent
DIST = ROOT / "dist"
REPO = "sylva98/chrono-geo-quest"
BRANCH = "gh-pages"
TOKEN = pathlib.Path("/root/.gh_token_chrono").read_text().strip()

S = requests.Session()
S.headers.update({"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json",
                  "User-Agent": "chrono-deploy"})


def api(method, path, **kw):
    r = S.request(method, "https://api.github.com" + path, timeout=90, **kw)
    if r.status_code >= 300:
        print("ERR", method, path, r.status_code, r.text[:400])
        sys.exit(1)
    return r.json() if r.text else {}


ref = api("GET", f"/repos/{REPO}/git/ref/heads/{BRANCH}")
parent = ref["object"]["sha"]
base_commit = api("GET", f"/repos/{REPO}/git/commits/{parent}")
base_tree = base_commit["tree"]["sha"]

entries = []
for f in sorted(DIST.rglob("*")):
    if not f.is_file():
        continue
    rel = f.relative_to(DIST).as_posix()
    blob = api("POST", f"/repos/{REPO}/git/blobs",
               json={"content": base64.b64encode(f.read_bytes()).decode(), "encoding": "base64"})
    entries.append({"path": rel, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    print(f"  blob {rel} {f.stat().st_size}B")

tree = api("POST", f"/repos/{REPO}/git/trees", json={"base_tree": base_tree, "tree": entries})
commit = api("POST", f"/repos/{REPO}/git/commits",
             json={"message": "deploy: " + time.strftime("%Y-%m-%d %H:%M:%S"), "tree": tree["sha"], "parents": [parent]})
api("PATCH", f"/repos/{REPO}/git/refs/heads/{BRANCH}", json={"sha": commit["sha"], "force": True})
print("pushed", commit["sha"][:9], "files:", len(entries))

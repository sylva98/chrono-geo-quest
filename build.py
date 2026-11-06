import json, pathlib, re

root = pathlib.Path(__file__).parent
tpl = (root / "src/template.html").read_text(encoding="utf-8")
qs = json.loads((root / "src/questions.json").read_text(encoding="utf-8"))

payload = json.dumps(qs, ensure_ascii=False, separators=(",", ":"))
out = tpl.replace("__QUESTIONS__", payload)
assert "__QUESTIONS__" not in out

dist = root / "dist"
dist.mkdir(exist_ok=True, parents=True)
(dist / "index.html").write_text(out, encoding="utf-8")
print("questions:", len(qs))
print("size KB:", round(len(out.encode()) / 1024, 1))

#!/usr/bin/env python3
"""Build step. Two jobs, in order:

1. Re-embed data/puzzles.json into index.html as the offline fallback (the array
   after the /*PUZZLES*/ marker). The app prefers a live fetch of puzzles.json and
   only falls back to this copy, but a stale fallback means a failed fetch shows a
   different puzzle set than the one you're actually training on.
2. Re-inline index.html into worker.js.

Run after editing index.html or regenerating puzzles.
"""
import base64, json, os, re

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# --- 1. embed the puzzle fallback -------------------------------------------------
html = open("index.html", encoding="utf-8").read()
MARK = "/*PUZZLES*/"
i = html.find(MARK)
assert i > 0, "/*PUZZLES*/ marker not found in index.html"
start = html.index("[", i)
# bracket-match so a "[" inside the JSON can't end the array early
depth, j, in_str, esc = 0, start, False, False
while j < len(html):
    c = html[j]
    if in_str:
        if esc:      esc = False
        elif c == "\\": esc = True
        elif c == '"':  in_str = False
    elif c == '"':   in_str = True
    elif c == "[":   depth += 1
    elif c == "]":
        depth -= 1
        if depth == 0: break
    j += 1
assert depth == 0, "unbalanced brackets in the embedded PUZZLES array"

puzzles = json.load(open("data/puzzles.json", encoding="utf-8"))
new_html = html[:start] + json.dumps(puzzles, separators=(",", ":")) + html[j + 1:]
if new_html != html:
    open("index.html", "w", encoding="utf-8").write(new_html)
    html = new_html
    print(f"embedded {len(puzzles)} puzzles from data/puzzles.json into index.html")
else:
    print(f"embedded puzzles already current ({len(puzzles)})")

# --- 2. inline the app into the worker --------------------------------------------
b64 = base64.b64encode(html.encode("utf-8")).decode("ascii")
w = open("worker.js", encoding="utf-8").read()
w2, n = re.subn(r'const APP_B64\s*=\s*"[^"]*";', 'const APP_B64="%s";' % b64, w, count=1)
assert n == 1, "APP_B64 marker not found in worker.js"
open("worker.js", "w", encoding="utf-8").write(w2)
print("re-inlined", len(html), "bytes of index.html into worker.js")

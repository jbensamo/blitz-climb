#!/usr/bin/env python3
"""Re-inline index.html into worker.js. Run after editing index.html, before `wrangler deploy`."""
import base64, re
html = open("index.html").read()
b64 = base64.b64encode(html.encode("utf-8")).decode("ascii")
w = open("worker.js").read()
w2, n = re.subn(r'const APP_B64\s*=\s*"[^"]*";', 'const APP_B64="%s";' % b64, w, count=1)
assert n == 1, "APP_B64 marker not found in worker.js"
open("worker.js", "w").write(w2)
print("re-inlined", len(html), "bytes of index.html into worker.js")

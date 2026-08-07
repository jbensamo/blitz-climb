#!/usr/bin/env python3
# Re-inline index.html into worker.js after editing the app.
import base64
html=open("index.html").read()
b64=base64.b64encode(html.encode("utf-8")).decode("ascii")
w=open("worker.js").read()
import re
w=re.sub(r'const APP_B64 = "[^"]*";', 'const APP_B64 = "%s";'%b64, w, count=1)
open("worker.js","w").write(w)
print("re-inlined", len(html), "bytes of HTML into worker.js")

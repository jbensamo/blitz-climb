#!/usr/bin/env python3
"""PUT a puzzles JSON to the Worker so /puzzles.json serves it (weekly job uses this).
Env: CF_WORKER_URL (e.g. https://blitz-climb.<you>.workers.dev), ADMIN_TOKEN."""
import os, sys, urllib.request
path = sys.argv[1] if len(sys.argv) > 1 else "puzzles.json"
url = os.environ["CF_WORKER_URL"].rstrip("/") + "/api/puzzles"
tok = os.environ["ADMIN_TOKEN"]
data = open(path, "rb").read()
req = urllib.request.Request(url, data=data, method="PUT",
    headers={"x-admin-token": tok, "content-type": "application/json"})
with urllib.request.urlopen(req) as r:
    print(r.status, r.read().decode())

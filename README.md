# Blitz Climb — jbensamo's chess trainer

A single-page chess trainer that drills tactics built from your **own** Lichess blitz
games (engine-verified with Stockfish), tracks your progress, and syncs it across
devices via a tiny Cloudflare Worker + KV store.

## What's here
- `index.html` — the whole app (self-contained; board, puzzles, plan, log, cloud sync).
- `worker.js` — Cloudflare Worker: serves the app **and** a small progress API
  (`/api/state?u=<code>`, GET/PUT) backed by a KV namespace bound as `PROGRESS`.
- `wrangler.toml` — Worker + KV config (fill in the KV namespace id).
- `build.py` — re-inlines `index.html` into `worker.js` after you edit the app.

## Deploy (Cloudflare, free tier)
1. Create a KV namespace; put its id in `wrangler.toml` (`PROGRESS` binding).
2. `python3 build.py` (bundles the current `index.html` into the Worker).
3. `npx wrangler deploy`.
4. Open the `*.workers.dev` URL → **Sync** tab → Connect (creates a private sync code).
   Enter the same code on your other device to sync.

## How progress syncs
Progress is a small JSON blob stored in KV under `state:<code>`. The app keeps a
localStorage copy as an offline cache but the KV copy is the source of truth, so
clearing a browser or switching devices never loses your history.

## Roadmap
- Phase 2: a weekly GitHub Actions job pulls the latest Lichess games, re-runs
  Stockfish, regenerates the puzzle set from the newest blunders, and writes it to KV.

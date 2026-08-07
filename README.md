# Blitz Climb

A personal chess trainer for **jbensamo** (~1750 Lichess blitz -> 1900). It drills tactics
built from your **own** games (engine-verified with Stockfish), tracks your progress, and
syncs across devices — hosted on a tiny Cloudflare Worker + KV, no database, no framework.

**Open this in Claude Code and read `CLAUDE.md` — it has the full setup.**

## TL;DR setup
```bash
npm i -g wrangler && wrangler login
wrangler kv namespace create PROGRESS      # put the id in wrangler.toml
wrangler secret put ADMIN_TOKEN            # any long random string
python build.py && wrangler deploy         # -> your https://blitz-climb.*.workers.dev URL
```
Open the URL -> **Sync** tab -> Connect -> use the same sync code on your phone and laptop.

## What's inside
- `index.html` — the whole app (playable board, puzzles, weekly plan, progress log, sync).
- `worker.js` — serves the app + progress API (`/api/state`) + live puzzle set (`/puzzles.json`).
- `tools/` — Stockfish analysis + puzzle generation from your PGNs.
- `data/` — current puzzles, your baseline, and the analyzed game samples.
- `docs/plan.html` — your engine-verified study plan.
- `.github/workflows/weekly.yml` — optional weekly job that auto-refreshes puzzles from
  your latest games.

## The point
Your leak is dropping material — same rate at blitz and rapid, so it isn't the clock.
Baseline ACPL 55; target low-40s (~1900). Every puzzle here is a real position where you
had a winning move and missed it. Fix that habit (Checks-Captures-Threats before every
move) and the rating follows.

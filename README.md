# Blitz Climb

A personal chess trainer for **jbensamo** (~1750 Lichess blitz -> 1900). It drills tactics
built from your **own** games (engine-verified with Stockfish), tracks your progress, and
syncs across devices — all on GitHub, no server, no database, no framework.

### ▶ https://jbensamo.github.io/blitz-climb/

**Open this in Claude Code and read `CLAUDE.md` — it has the full setup.**

## Cross-device sync
Progress lives in a **private GitHub Gist** in your own account; the page talks to
`api.github.com` directly, so no backend is needed.

1. Make a classic token at github.com/settings/tokens with **only the `gist` scope**.
2. App -> **Sync** tab -> paste the token, leave *Gist ID* blank -> **Connect & sync**.
   It creates the gist and shows its ID.
3. On your other device: same token + that Gist ID -> **Connect & sync**.

The token stays in that browser's local storage and is only ever sent to GitHub. It can
read/write all your gists, so scope it to `gist` alone and set an expiry — details and
caveats in `docs/SETUP-sync.md`. Prefer no token? Sync off + **Export/Import** still works.

## What's inside
- `index.html` — the whole app (playable board, puzzles, weekly plan, progress log, sync).
- `puzzles.json` — the live puzzle set Pages serves (refreshed weekly, fetched relatively).
- `worker.js` — optional Cloudflare Worker build of the same app; **not used in production**.
- `tools/` — Stockfish analysis + puzzle generation from your PGNs.
- `data/` — current puzzles, your baseline, and the analyzed game samples.
- `docs/plan.html` — your engine-verified study plan.
- `docs/SETUP-sync.md` — how hosting + gist sync are wired, and the known edges.
- `.github/workflows/weekly.yml` — weekly job that re-analyzes your latest Lichess games
  and commits a fresh puzzle set; Pages redeploys and the app picks it up.

## The point
Your leak is dropping material — same rate at blitz and rapid, so it isn't the clock.
Baseline ACPL 55; target low-40s (~1900). Every puzzle here is a real position where you
had a winning move and missed it. Fix that habit (Checks-Captures-Threats before every
move) and the rating follows.

# Blitz Climb

A personal chess trainer for **jbensamo** (~1750 Lichess blitz -> 1900). It drills tactics
built from your **own** games (engine-verified with Stockfish), tracks your progress, and
syncs across devices — static hosting on GitHub Pages, a small Supabase table for sync,
no server of its own and no framework.

### ▶ https://jbensamo.github.io/blitz-climb/

**Open this in Claude Code and read `CLAUDE.md` — it has the full setup.**

## Cross-device sync
Progress lives in your own row of a **private Supabase Postgres** database, protected by
row-level security. Sign-in is email + password, and no email is ever sent.

1. App -> **Sync** tab -> enter your email and a 10+ character password.
2. **Sign in & sync**. The Home pill turns green. (The first device creates the account.)
3. Same email and password on your other device. That's it.

Sign in first on the device that already has your progress — sync is last-write-wins with
no merge. One-time project setup and the known edges are in `docs/SETUP-sync.md`. Prefer no
account at all? Leave sync off; **Export/Import** still works.

## What's inside
- `index.html` — the whole app (playable board, puzzles, weekly plan, progress log, sync).
- `puzzles.json` — the live puzzle set Pages serves (refreshed weekly, fetched relatively).
- `worker.js` — optional Cloudflare Worker build of the same app; **not used in production**.
- `tools/` — Stockfish analysis + puzzle generation from your PGNs.
- `data/` — current puzzles, your baseline, and the analyzed game samples.
- `docs/plan.html` — your engine-verified study plan.
- `docs/SETUP-sync.md` — how hosting + Supabase sync are wired, and the known edges.
- `db/schema.sql` — the progress table and its row-level-security policy.
- `.github/workflows/weekly.yml` — weekly job that re-analyzes your latest Lichess games
  and commits a fresh puzzle set; Pages redeploys and the app picks it up.

## The point
Your leak is dropping material — same rate at blitz and rapid, so it isn't the clock.
Baseline ACPL 55; target low-40s (~1900). Every puzzle here is a real position where you
had a winning move and missed it. Fix that habit (Checks-Captures-Threats before every
move) and the rating follows.

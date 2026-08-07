# CLAUDE.md — Blitz Climb

This file tells you (Claude Code) how to finish setting up and run this project. Read it
fully before acting. The owner is **jbensamo** (Jonathan), a ~1750 Lichess **blitz**
player working toward ~1900. This is a **personal** project — do NOT put it in any work
GitHub org; use a personal account.

## What this is
A single-page chess trainer that drills tactics generated from the owner's **own** games
(engine-verified with Stockfish), tracks progress, and syncs it across devices through a
Cloudflare Worker + KV store. There is intentionally **no framework, no bundler, no
database** — it's one HTML file plus a tiny Worker. Keep it that way. Do not "modernize"
it into React/Next/etc.; that would be over-engineering for a single-user tool.

## The owner's baseline (from Stockfish 16, 60 blitz games, Aug 2026)
See `data/baseline.json`. Headline: **ACPL 55**, **0.65 blunders + 0.70 mistakes + 2.3
inaccuracies per game**; blunders land **59% middlegame / 26% endgame / 15% opening**.
The core leak is dropping material / not scanning the opponent's Checks–Captures–Threats
(C.C.T.) before moving; endgames are a genuine second front. Targets: ACPL → low 40s,
blunders → ~0.40/game. Keep the C.C.T. habit central in any changes.

## Repo layout
```
index.html              The whole app (board, puzzles, plan, log, cloud sync). Edit here.
worker.js               Cloudflare Worker: serves the app + APIs. GENERATED from index.html.
build.py                Re-inlines index.html into worker.js (run after editing index.html).
wrangler.toml           Worker + KV config (fill in the KV namespace id).
tools/
  analyze.py            Stockfish ACPL/blunder analysis of a PGN.  `python tools/analyze.py <pgn> jbensamo`
  generate_puzzles.py   Build engine-verified puzzles from a PGN. Writes ./puzzles.json.
  publish_puzzles.py    PUT a puzzles JSON to the Worker so /puzzles.json serves it.
  requirements.txt      Python deps (python-chess). Stockfish is a system binary.
data/
  puzzles.json          Current puzzle set (18, from the owner's blitz games).
  baseline.json         The diagnostic baseline + targets.
  games/                Seed PGNs: blitz_60.pgn, rapid_60.pgn (the analyzed samples).
docs/
  plan.html             The engine-verified study plan (human-readable).
  SETUP-github-gist-alt.md   Alternative no-Cloudflare hosting path (GitHub Pages + gist).
.github/workflows/weekly.yml   Phase-2 automation (weekly Lichess pull -> analyze -> puzzles -> KV).
```

## Architecture notes
- **App** (`index.html`): pure vanilla JS. Puzzles are embedded as a fallback, but on load
  the app fetches **`/puzzles.json`** and uses it if present — so the weekly job can refresh
  puzzles without a redeploy. Progress persists to localStorage (`chessTrainer_v5`) AND, if
  cloud sync is on, to the Worker (`/api/state?u=<code>`); the cloud copy is source of truth.
- **Worker** (`worker.js`): routes —
  - `GET /` -> the app.
  - `GET/PUT /api/state?u=<code>` -> progress blob in KV key `state:<code>`.
  - `GET /puzzles.json` -> KV key `puzzles` (404 if unset -> app uses embedded).
  - `PUT /api/puzzles` (header `x-admin-token: $ADMIN_TOKEN`) -> sets KV `puzzles`.
  - KV binding: `PROGRESS`. Secret: `ADMIN_TOKEN`.
- After editing `index.html`, ALWAYS run `python build.py` then redeploy, or the Worker
  serves a stale app.

## SETUP — do this
Prereqs: a **personal** Cloudflare account, Node (for `wrangler`), Python 3.11+, and
Stockfish (`apt-get install -y stockfish`, or `brew install stockfish`).

1. **Install wrangler & log in**
   `npm i -g wrangler && wrangler login`
2. **Create the KV namespace and wire it**
   `wrangler kv namespace create PROGRESS` -> copy the `id` into `wrangler.toml`
   (the `[[kv_namespaces]] id`).
3. **Set the admin token** (used by the weekly publisher)
   `wrangler secret put ADMIN_TOKEN`  -> paste a long random string; keep a copy.
4. **Build & deploy**
   `python build.py && wrangler deploy` -> note the `https://blitz-climb.<subdomain>.workers.dev` URL.
5. **Publish the current puzzles** (optional but recommended)
   `CF_WORKER_URL=<that url> ADMIN_TOKEN=<token> python tools/publish_puzzles.py data/puzzles.json`
6. **Turn on sync on each device**
   Open the URL -> **Sync** tab -> Connect (first device creates a sync code) -> enter that
   same code on the other device. Progress now follows the owner everywhere and survives a
   browser wipe.

## SETUP — Phase 2 (weekly automation, optional)
Makes the training auto-adjust to the owner's latest games, hands-off.
1. Push this repo to a **personal** GitHub repo.
2. Repo -> Settings -> Secrets and variables -> Actions -> add:
   - `CF_WORKER_URL` = the workers.dev URL
   - `ADMIN_TOKEN`  = the same token from step 3 above
3. The workflow `.github/workflows/weekly.yml` runs Sundays (and via "Run workflow"):
   pulls the latest 60 blitz games from the Lichess API, runs `analyze.py` (writes
   `data/last_report.txt`), regenerates puzzles with `generate_puzzles.py`, publishes them
   to KV via `publish_puzzles.py`, and commits the refreshed data. The app picks up the new
   set automatically on next load.
   - Adjust the cron for the owner's timezone (currently `0 23 * * 0` = Sun 19:00 US Eastern).
   - Note: the Lichess games API works fine from GitHub Actions (a normal client); it is only
     blocked inside the Claude sandbox, which is why this runs in Actions, not here.

## Running the tools by hand
- Analyze a PGN: `python tools/analyze.py data/games/blitz_60.pgn jbensamo`
- Regenerate puzzles: `rm -f candidates.json && python tools/generate_puzzles.py data/games/blitz_60.pgn jbensamo`
  (writes `./puzzles.json`; `candidates.json` is a scan cache — delete it to force a rescan).
  Both scripts expect Stockfish at `/usr/games/stockfish` (edit the `ENGINE` constant if elsewhere).
- After regenerating, either publish to KV (`tools/publish_puzzles.py`) for the live set, or
  copy into `data/puzzles.json` and re-embed as the fallback with `python build.py` + deploy.

## Data schemas
- Puzzle: `{id, fen, sideToMove, userColor, line:[{uci,from,to,san,fen,user,promo}],
  motif, youPlayed, sourceUrl, moveNo, explain}`. Only the engine's move is accepted;
  `line` alternates user/opponent plies and each carries the resulting FEN.
- Progress (`state:<code>` / localStorage): `{version, player, checks, habitDays,
  sessions:[{date,acpl,blunders,note}], puzzles:{solved,attempts,firstTry,byDay}, updated}`.

## Verifying changes
- Worker logic: import `worker.js` in Node with a fake `env.PROGRESS` (Map) and hit the
  routes; expect `/api/state` GET->404 then PUT->200 then GET->blob, `/puzzles.json`->404
  until `/api/puzzles` PUT with the admin token, `/`->HTML containing `id="board"`.
- App: open `index.html` (or the deployed URL); solve a puzzle; confirm it persists after
  reload; connect sync on a second browser profile with the same code and confirm it pulls.

## Guardrails
- Keep it a single self-contained `index.html`. No framework, no build step beyond `build.py`.
- Never commit secrets (`ADMIN_TOKEN`, tokens). `.gitignore` already excludes `.dev.vars`.
- Don't weaken puzzle correctness: puzzles must stay Stockfish-verified (unique, decisive).

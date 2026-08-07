# CLAUDE.md — Blitz Climb

This file tells you (Claude Code) how to finish setting up and run this project. Read it
fully before acting. The owner is **jbensamo** (Jonathan), a ~1750 Lichess **blitz**
player working toward ~1900. This is a **personal** project — do NOT put it in any work
GitHub org; use a personal account.

## What this is
A single-page chess trainer that drills tactics generated from the owner's **own** games
(engine-verified with Stockfish), tracks progress, and syncs it across devices through a
**private GitHub Gist**. There is intentionally **no framework, no bundler, no database,
and no server of our own** — it's one HTML file. Keep it that way. Do not "modernize"
it into React/Next/etc.; that would be over-engineering for a single-user tool.

**Deployed:** https://jbensamo.github.io/blitz-climb/ — GitHub Pages from `main` of the
personal repo `jbensamo/blitz-climb`. Everything (hosting, sync, weekly refresh) runs on
GitHub; there is no Cloudflare dependency. See `docs/SETUP-sync.md`.

## The owner's baseline (from Stockfish 16, 60 blitz games, Aug 2026)
See `data/baseline.json`. Headline: **ACPL 55**, **0.65 blunders + 0.70 mistakes + 2.3
inaccuracies per game**; blunders land **59% middlegame / 26% endgame / 15% opening**.
The core leak is dropping material / not scanning the opponent's Checks–Captures–Threats
(C.C.T.) before moving; endgames are a genuine second front. Targets: ACPL → low 40s,
blunders → ~0.40/game. Keep the C.C.T. habit central in any changes.

## Repo layout
```
index.html              The whole app (board, puzzles, plan, log, gist sync). Edit here.
puzzles.json            Root copy served by Pages; the app fetches it RELATIVELY. Keep at root.
worker.js               Optional Cloudflare Worker (unused in prod). GENERATED from index.html.
build.py                Re-inlines index.html into worker.js (run after editing index.html).
wrangler.toml           Worker + KV config (KV namespace id left as a placeholder on purpose).
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
  SETUP-sync.md         How hosting + cross-device gist sync are set up (the live setup).
.github/workflows/weekly.yml   Phase-2 automation (weekly Lichess pull -> analyze -> puzzles -> commit).
```

## Architecture notes
- **App** (`index.html`): pure vanilla JS. Puzzles are embedded as a fallback, but on load
  the app fetches **`puzzles.json`** (relative — must stay at the site root, since Pages
  serves the app under `/blitz-climb/`) and uses it if present, so the weekly job refreshes
  puzzles without touching the app.
- **Sync** (cross-device): progress persists to localStorage (`chessTrainer_v5`) AND, if
  sync is on, to a **private GitHub Gist** file `blitz-climb-progress.json`, via
  `api.github.com` directly from the browser (GitHub sends CORS headers, so this works from
  a static host — verified from the live origin). The gist copy is source of truth on load.
  - Per-device config in localStorage `chessTrainer_cloud`: `{token, gistId, on}`. The
    token is a **classic PAT with only the `gist` scope**, entered per device, never
    committed and never in the served HTML. `Authorization: Bearer <token>` (classic and
    fine-grained PATs both accept `Bearer`).
  - No gist id yet -> `POST /gists` creates a private one; otherwise `PATCH /gists/{id}`.
    A gist deleted upstream (404) is transparently recreated rather than erroring.
  - Legacy devices may still hold the old `{code, on}` shape; without a token they simply
    start out "not connected". Don't break that fallback.
  - **Known edges** (measured, not guessed): gist reads can lag a write by up to ~2s
    (replica lag — a cache-busting query param does NOT fix it; `cache:"no-store"` on the
    GET is still required or the browser serves a `max-age=60` copy). Semantics are
    last-write-wins with no merge — fine for one person switching devices.
- **Worker** (`worker.js`): **not used in production** — kept so the app can also be hosted
  on Cloudflare if ever wanted. Routes: `GET /` -> app; `GET /puzzles.json` -> KV `puzzles`;
  `PUT /api/puzzles` (header `x-admin-token: $ADMIN_TOKEN`) -> sets it. `GET/PUT /api/state`
  is now **dead code** — sync no longer uses it; don't wire anything back to it without
  reading `docs/SETUP-sync.md` first.
- After editing `index.html`, ALWAYS run `python build.py` (keeps `worker.js` in sync).
  Deploying to Pages is just a push to `main`.

## SETUP — already done; recorded so it can be rebuilt
Hosting and sync are live. Full walkthrough in **`docs/SETUP-sync.md`**. In short:

1. Personal public repo `jbensamo/blitz-climb`, default branch `main`.
2. **Settings → Pages** → deploy from branch `main`, folder `/` → `https://jbensamo.github.io/blitz-climb/`.
3. **Settings → Actions → General → Workflow permissions = Read and write** (else the
   weekly job can't commit refreshed puzzles; it fails silently on `git push`).
4. Per device: **Sync** tab → paste a classic PAT with **only the `gist` scope**, leave
   Gist ID blank on the first device, then reuse that token + the shown Gist ID elsewhere.
   Deploying a change = `python build.py` + push to `main`.

Prereqs for the *tools* only (not for hosting): Python 3.11+ and Stockfish
(`brew install stockfish`, or `apt-get install -y stockfish`).

### Optional: also host on Cloudflare
Not needed and not currently used. If ever wanted, it must be a **personal** Cloudflare
account: `wrangler kv namespace create PROGRESS` -> put the id in `wrangler.toml`,
`wrangler secret put ADMIN_TOKEN`, `python build.py && wrangler deploy`. Note the Fi (work)
account **cannot** serve it: `*.fi-corp.workers.dev` is blocked at the edge (403 /
`error code: 1050`, zero Worker invocations) unless the hostname gets an explicit Access
allowlist app. Don't retry that path.

## SETUP — Phase 2 (weekly automation) — active
`.github/workflows/weekly.yml` runs Sundays (and via "Run workflow"): pulls the latest 60
blitz games from the Lichess API, runs `analyze.py` (writes `data/last_report.txt`),
regenerates puzzles with `generate_puzzles.py`, and commits the refreshed `puzzles.json`.
Pages redeploys on that commit and the app picks up the new set on next load — **the whole
loop is inside GitHub, no Cloudflare needed.**
- The Cloudflare KV publish step self-skips unless the `CF_WORKER_URL` and `ADMIN_TOKEN`
  repo secrets are set. Its `if:` reads **job-level** env on purpose — a step's own `env:`
  block is not visible to that step's `if:`, and getting this wrong makes
  `publish_puzzles.py` raise `KeyError` every Sunday.
- Adjust the cron for the owner's timezone (currently `0 23 * * 0` = Sun 19:00 US Eastern).
- Note: the Lichess games API works fine from GitHub Actions (a normal client); it is only
  blocked inside the Claude sandbox, which is why this runs in Actions, not here.

## Running the tools by hand
- Analyze a PGN: `python tools/analyze.py data/games/blitz_60.pgn jbensamo`
- Regenerate puzzles: `rm -f candidates.json && python tools/generate_puzzles.py data/games/blitz_60.pgn jbensamo`
  (writes `./puzzles.json`; `candidates.json` is a scan cache — delete it to force a rescan).
  Both scripts expect Stockfish at `/usr/games/stockfish` (edit the `ENGINE` constant if elsewhere).
- After regenerating, copy the new set to **both** `puzzles.json` (repo root — this is what
  Pages actually serves) and `data/puzzles.json`, then `python build.py` and push to `main`.
  (`tools/publish_puzzles.py` only matters for a Cloudflare deployment, which isn't live.)

## Data schemas
- Puzzle: `{id, fen, sideToMove, userColor, line:[{uci,from,to,san,fen,user,promo}],
  motif, youPlayed, sourceUrl, moveNo, explain}`. Only the engine's move is accepted;
  `line` alternates user/opponent plies and each carries the resulting FEN.
- Progress (gist file `blitz-climb-progress.json` / localStorage `chessTrainer_v5`):
  `{version, player, checks, habitDays, sessions:[{date,acpl,blunders,note}],
  puzzles:{solved,attempts,firstTry,byDay}, updated}`. `updated` (ISO string) is what
  decides adopt-remote vs push-local, so always set it before a write.

## Verifying changes
- App: open the deployed URL; solve a puzzle; confirm it persists after reload.
- Sync, without needing a token in a browser: the sync functions can be extracted from
  `index.html` and run in Node against the live API (stub `$`, `localStorage`, `STATE`).
  Covered that way already: create-private-gist, read-back, PATCH-reuses-same-gist,
  second-device-read, deleted-upstream-recreates, bad-token-message. Allow up to ~2s of
  replica lag before asserting a read reflects a write, or the test flakes.
- CORS from a static host is real and was verified from `https://jbensamo.github.io`:
  `POST /gists` and `PATCH /gists/{id}` with `Authorization` clear preflight (a readable
  `401 Bad credentials` with a junk token is the proof — no token needed for this check).
- Worker logic (only if you revive it): import `worker.js` in Node with a fake
  `env.PROGRESS` (Map); `/`->HTML containing `id="board"`, `/puzzles.json`->404 until
  `/api/puzzles` PUT with the admin token.

## Guardrails
- Keep it a single self-contained `index.html`. No framework, no build step beyond `build.py`.
- Never commit secrets (`ADMIN_TOKEN`, tokens). `.gitignore` already excludes `.dev.vars`.
- Don't weaken puzzle correctness: puzzles must stay Stockfish-verified (unique, decisive).

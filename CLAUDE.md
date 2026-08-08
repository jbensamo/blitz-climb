# CLAUDE.md — Blitz Climb

This file tells you (Claude Code) how to finish setting up and run this project. Read it
fully before acting. The owner is **jbensamo** (Jonathan), a ~1750 Lichess **blitz**
player working toward ~1900. This is a **personal** project — do NOT put it in any work
GitHub org; use a personal account.

## What this is
A single-page chess trainer that drills tactics generated from the owner's **own** games
(engine-verified with Stockfish), tracks progress, and syncs it across devices through a
**Supabase Postgres** database with email/password auth. There is intentionally
**no framework, no bundler, and no server of our own** — it's one HTML file that talks to
Supabase's REST APIs directly (no SDK, no CDN script). Keep it that way. Do not
"modernize" it into React/Next/etc.; that would be over-engineering for a single-user tool.

**Deployed:** https://jbensamo.github.io/blitz-climb/ — GitHub Pages from `main` of the
personal repo `jbensamo/blitz-climb`. Hosting and the weekly refresh run entirely on
GitHub; only cross-device sync depends on Supabase. No Cloudflare. See `docs/SETUP-sync.md`.

## The owner's baseline (from Stockfish 16, 60 blitz games, Aug 2026)
See `data/baseline.json`. Headline: **ACPL 55**, **0.65 blunders + 0.70 mistakes + 2.3
inaccuracies per game**; blunders land **59% middlegame / 26% endgame / 15% opening**.
The core leak is dropping material / not scanning the opponent's Checks–Captures–Threats
(C.C.T.) before moving; endgames are a genuine second front. Targets: ACPL → low 40s,
blunders → ~0.40/game. Keep the C.C.T. habit central in any changes.

## Repo layout
```
index.html              The whole app (board, puzzles, plan, log, sync). Edit here.
puzzles.json            Root copy served by Pages; the app fetches it RELATIVELY. Keep at root.
worker.js               Optional Cloudflare Worker (unused in prod). GENERATED from index.html.
build.py                Re-inlines index.html into worker.js (run after editing index.html).
wrangler.toml           Worker + KV config (KV namespace id left as a placeholder on purpose).
tools/
  analyze.py            Stockfish ACPL/blunder analysis of a PGN.  `python tools/analyze.py <pgn> jbensamo`
  generate_puzzles.py   Build engine-verified puzzles from a PGN. Writes ./puzzles.json.
  publish_puzzles.py    PUT a puzzles JSON to the Worker so /puzzles.json serves it.
  requirements.txt      Python deps (python-chess). Stockfish is a system binary.
db/schema.sql           Supabase table + RLS policy. Paste into the SQL Editor.
tools/verify_supabase.mjs  End-to-end sync check driving the app's own functions.
data/
  puzzles.json          Current puzzle set (18, from the owner's blitz games).
  baseline.json         The diagnostic baseline + targets.
  games/                Seed PGNs: blitz_60.pgn, rapid_60.pgn (the analyzed samples).
docs/
  plan.html             The engine-verified study plan (human-readable).
  SETUP-sync.md         How hosting + Supabase sync are set up (the live setup).
.github/workflows/weekly.yml   Phase-2 automation (weekly Lichess pull -> analyze -> puzzles -> commit).
```

## Architecture notes
- **Two kinds of module.** The list shows "From your own games" (built from his Lichess
  blunders — the irreplaceable part, keep it first) and "Graded curriculum" (648 puzzles
  from the Lichess CC0 database, rated 1600-2400). Provenance, filters and the legal
  reasoning are in `data/CORPUS.md`; **don't import exercises from books** — those are
  copyrighted selections and this repo is public.
- **Corpus modules are lazy.** `puzzles/index.json` is a manifest (name, blurb, id prefix,
  count, rating range, file); the app fetches it at boot so the list can show real counts
  and progress, and downloads `puzzles/<key>.json` only when a module is opened. 648
  puzzles is ~630KB — far too much for the page, and `build.py` embeds everything it finds
  in `data/puzzles.json`, so corpus puzzles must NEVER be merged in there.
  - `modStats()` uses the manifest count plus an id-prefix scan of solved ids for a module
    that isn't downloaded yet, so counts don't lie before the fetch.
  - `renderDash()` totals across ALL modules (manifest included), not `PUZZLES.length`, or
    the headline would jump every time a module is opened.
- **Train tab = module list -> trainer.** `MODULES` declares every trainable part of the
  plan; each has a `cat` (matching the puzzle's `cat`) and a `kind`:
  - `kind:"line"` — the classic trainer: play the engine's move(s) from `line[]`. Used by
    tactics, endgames, endgame theory, strategy and openings, so those need **no new UI**.
  - `kind:"find"` — click every square answering `prompt`; validated against `targets[]`.
    Used by the C.C.T. scan. Scoring is all-or-nothing on purpose: a scan that misses one
    capture is the scan that loses a piece.
  - `CURMOD` null = module list; set = trainer. `ACTIVE` is that module's items and is what
    puzzle navigation indexes. `renderDash()` deliberately still counts all of `PUZZLES`.
  - **`markSolved()` is the single write path for BOTH kinds** — streak, `byDay`, Home
    totals and cloud sync all depend on it. Never record a solve any other way.
  - A module with zero items renders greyed out ("not built yet"), never clickable.
  - `WORK` rows carry `mod` when that curriculum item is trainable in-app; the Plan tab
    links them to the module and the "More homework" card shows only the rows WITHOUT a
    `mod` (the Chernev book, the Woodpecker set) — the things that genuinely can't move
    in-app. Adding a module means adding `mod` to its `WORK` row, or the plan will list
    the same work twice.
  - "Today's module" is a second **view** of `STATE.checks[wkPre()+id]` — the same key the
    Plan tab's weekly list owns — never a copy. Nothing is ever locked.
- **App** (`index.html`): pure vanilla JS. Puzzles are embedded as a fallback, but on load
  the app fetches **`puzzles.json`** (relative — must stay at the site root, since Pages
  serves the app under `/blitz-climb/`) and uses it if present, so the weekly job refreshes
  puzzles without touching the app.
- **Sync** (cross-device): progress persists to localStorage (`chessTrainer_v5`) AND, if
  signed in, to one row in **Supabase Postgres** (`public.progress`, `data jsonb`). The
  remote copy wins on load when its `updated` is newer. Setup: `docs/SETUP-sync.md`;
  schema: `db/schema.sql`.
  - **No SDK.** The app calls the REST APIs directly so it stays one self-contained file:
    `POST /auth/v1/token?grant_type=password` (sign in) / `POST /auth/v1/signup` (first
    device) -> `POST /auth/v1/token?grant_type=refresh_token` (renew) and
    `GET|POST /rest/v1/progress` for data. Upsert is `POST` with
    `Prefer: resolution=merge-duplicates`.
  - **Auth is email + password with `mailer_autoconfirm` on, so NO email is ever sent.**
    This is forced, not a preference: free-tier projects cannot edit email templates at
    all (so `{{ .Token }}` for a 6-digit code is impossible) and `rate_limit_email_sent`
    is 2/hour. Don't "improve" this into magic links or OTP without a custom SMTP provider.
    Unknown email -> `/auth/v1/signup` creates the account; a wrong password is reported
    as such rather than leaking signup's "User already registered".
  - `SB_URL` / `SB_ANON` are top-of-section constants and **are meant to be committed**.
    The anon key is public by design; **RLS is the only thing protecting the data**, so
    never disable it and never let a policy widen past `auth.uid() = user_id`.
  - Per-device session in localStorage `chessTrainer_cloud`: `{email, uid, at, rt, exp, on}`.
    Access tokens are short-lived and refreshed a minute before `exp`.
  - Legacy devices may hold `{code, on}` (Cloudflare) or `{token, gistId, on}` (gist). Neither
    carries a session, so they start out "not connected". Don't break that fallback.
  - **`save()` sets `STATE.updated` on every local change** — not just on a successful cloud
    write. This is load-bearing: if the timestamp only moved when sync was on, a device used
    offline would carry a stale one and lose its progress to an empty device that signed in
    first. Don't "optimize" it back into the write path.
  - **Known edges:** last-write-wins with no merge; free-tier projects pause after ~a week
    idle, which makes sync fail until un-paused; project ref `ncodlvmhfehxmbvnyyuh`.
- **Worker** (`worker.js`): **not used in production** — kept so the app can also be hosted
  on Cloudflare if ever wanted. Routes: `GET /` -> app; `GET /puzzles.json` -> KV `puzzles`;
  `PUT /api/puzzles` (header `x-admin-token: $ADMIN_TOKEN`) -> sets it. `GET/PUT /api/state`
  is now **dead code** — sync no longer uses it; don't wire anything back to it without
  reading `docs/SETUP-sync.md` first.
- `build.py` does TWO things: re-embeds `data/puzzles.json` into `index.html` as the
  offline fallback (the array after the `/*PUZZLES*/` marker), then inlines `index.html`
  into `worker.js`. It used to only do the second, so the embedded fallback silently
  drifted. Run it after editing `index.html` OR after regenerating puzzles.
  Deploying to Pages is just a push to `main`.

## SETUP — already done; recorded so it can be rebuilt
Hosting and sync are live. Full walkthrough in **`docs/SETUP-sync.md`**. In short:

1. Personal public repo `jbensamo/blitz-climb`, default branch `main`.
2. **Settings → Pages** → deploy from branch `main`, folder `/` → `https://jbensamo.github.io/blitz-climb/`.
3. **Settings → Actions → General → Workflow permissions = Read and write** (else the
   weekly job can't commit refreshed puzzles; it fails silently on `git push`).
4. Supabase project + `db/schema.sql` + `mailer_autoconfirm`, then `SB_URL`/`SB_ANON`
   filled into `index.html` (both are meant to be committed). Steps: `docs/SETUP-sync.md`.
5. Per device: **Sync** tab → same email + password → **Sign in & sync**.
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
- The generators, one per module: `generate_puzzles.py` (tactics/endgames/strategy, from
  his games), `gen_cct.py` (C.C.T. scans — no engine, pure legal-move generation),
  `gen_endgame_theory.py` (K+P vs K only-move positions — **searched and engine-certified,
  never hand-authored FENs**, so the project ships no chess it hasn't verified),
  `gen_openings.py` (his own most-played lines, each of HIS moves engine-checked and the
  line cut before any real mistake). All write to `build/sets/`; `merge_sets.py` combines.
- **Every generated line must start AND end on a user move** — the trainer asks the user to
  play `line[0]`. As Black an opening line begins with White's move, so `gen_openings.py`
  replays the leading opponent plies into the starting FEN instead. Replay-verify new
  generators (legal moves, SAN and FEN consistency, first/last ply `user:true`) before
  merging; that check is what caught it.
- Rebuild the graded curriculum: download the dump to `build/corpus/` (gitignored) then
  `zstd -dc build/corpus/lichess_db_puzzle.csv.zst | python3 tools/build_corpus.py`. It
  early-exits once every (theme, rating-band) bucket is full — ~82k of 5M rows was enough.
  **The CSV's `FEN` is the position BEFORE the opponent's setup move and `Moves[0]` IS that
  move**; the solver plays `Moves[1]`. Replay-verify after building.
- Rebuild ALL puzzle sets: `bash tools/build_sets.sh` (~6 min; writes `build/sets/*.json`,
  which is gitignored). It drives `generate_puzzles.py` several times via env vars —
  `OUT`, `CACHE`, `ID_PREFIX`, `CAT`, `PHASE_ONLY`, `MAX_PUZZLES`, `WALL`, `ENGINE`.
  Then merge with `python tools/merge_sets.py`.
- One set by hand: `CACHE=/tmp/c.json OUT=/tmp/o.json ID_PREFIX=e CAT=endgame PHASE_ONLY=endgame
  python3 tools/generate_puzzles.py data/games/blitz_60.pgn`. `CACHE` is a scan cache —
  use a distinct path per set or runs poison each other. `ENGINE` defaults to
  `/usr/games/stockfish`; on macOS `brew install stockfish` puts it elsewhere, and
  `build_sets.sh` resolves it with `command -v`.
- Yield is low by design (engine-verified, unique, decisive): ~7-8 endgame candidates per
  60 games becomes ~4-6 puzzles. Partial results are normal, not a failure.
- `build/sets/*.json` is gitignored — only the MERGED output (`puzzles.json` +
  `data/puzzles.json`) is committed. Reproducing a set locally means re-running
  `build_sets.sh` (~6 min).
- **The library only grows.** `merge_sets.py` appends to `data/puzzles.json` and the weekly
  job adds ~10-20 genuinely-new positions a week (FEN dedupe stops repeats, but nothing
  prunes). Both the served `puzzles.json` and the `/*PUZZLES*/` embed in `index.html` grow
  with it — 18 -> 40 puzzles took index.html from 44KB to 68KB. At a few hundred puzzles
  this needs a cap or a retire-the-solved-and-old rule; it is not a problem yet.
- `tools/merge_sets.py` writes **both** `puzzles.json` (repo root — what Pages serves) and
  `data/puzzles.json`, deduping by FEN and refusing on an id collision. Then `python
  build.py` and push to `main`. (`tools/publish_puzzles.py` only matters for a Cloudflare
  deployment, which isn't live.)

## Data schemas
- Puzzle: `{id, fen, sideToMove, userColor, line:[{uci,from,to,san,fen,user,promo}],
  motif, cat, phase, youPlayed, sourceUrl, moveNo, explain}`. Only the engine's move is
  accepted; `line` alternates user/opponent plies and each carries the resulting FEN.
  - `cat` groups puzzles into the Train tab's sets (`tactics` | `endgame`); missing `cat`
    reads as `tactics`, which is how the original 18 still work. `phase` is the
    `analyze.py` classifier's label, so "endgame" means the same thing as in the baseline.
  - **Ids must be globally unique across sets** — progress is keyed by id alone
    (`STATE.puzzles.solved[id]`). Prefixes in use: `p` (blitz tactics), `r` (rapid
    tactics), `eb`/`er` (blitz/rapid endgames), `sb`/`sr` (strategy), `c` (C.C.T.),
    `et` (endgame theory), `o` (openings), `L<modkey>` (Lichess corpus, e.g. `Lrookend`),
    and `t<yymmdd>_`/`e<yymmdd>_` from the weekly job. Reusing a prefix silently marks new
    puzzles as already solved.
  - `merge_sets.py` only DERIVES `cat` for legacy items that lack one. It used to
    re-derive every run, which clobbered explicit cats (strategy/cct/opening) back to
    "tactics" on the second merge and silently emptied those modules.
- Progress (`public.progress.data` jsonb / localStorage `chessTrainer_v5`):
  `{version, player, checks, habitDays, sessions:[{date,acpl,blunders,note}],
  puzzles:{solved,attempts,firstTry,byDay}, homework:{"<ISO date>":{"<work id>":count}},
  updated}`. Any NEW top-level field must also be defaulted inside `adoptRemote` and
  `doImport`, or syncing from a device on an older build silently drops it. `updated` (ISO string) is what
  decides adopt-remote vs push-local; `save()` refreshes it on every local change.

## Verifying changes
- App: open the deployed URL; solve a puzzle; confirm it persists after reload.
- Sync: `SB_SERVICE=<service_role key> node tools/verify_supabase.mjs`. It extracts the shipped sync
  functions from `index.html` and drives them against the live project, so it tests the
  real code, not a copy. Covers anon-key-cannot-read (RLS), sign-in, write, read-back,
  upsert-not-duplicate, second-device read, and token refresh. It creates and deletes a
  throwaway account, so it needs no email and no interaction.
- The load-bearing check is the RLS one: `GET /rest/v1/progress` with only the anon key and
  no user session must return `[]`. If it returns rows, the public key in the shipped HTML
  is an open door and nothing else matters.
- Worker logic (only if you revive it): import `worker.js` in Node with a fake
  `env.PROGRESS` (Map); `/`->HTML containing `id="board"`, `/puzzles.json`->404 until
  `/api/puzzles` PUT with the admin token.

## Guardrails
- Keep it a single self-contained `index.html`. No framework, no build step beyond `build.py`.
- Never commit secrets (`ADMIN_TOKEN`, tokens). `.gitignore` already excludes `.dev.vars`.
- Don't weaken puzzle correctness: puzzles must stay Stockfish-verified (unique, decisive).

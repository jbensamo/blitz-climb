# Blitz Climb — Cross-Device Setup

The app is hosted on **GitHub Pages** and stores progress in a **Supabase Postgres**
database, one row per user, guarded by row-level security. Sign-in is email + password,
and **no email is ever sent** — see "Why password auth" below.

**Live:** https://jbensamo.github.io/blitz-climb/ (repo `jbensamo/blitz-climb`, Pages from `main`)

---

## Part 1 — Hosting (already done)
Recorded so it can be rebuilt:

1. Personal, public GitHub repo, default branch `main`.
2. **Settings → Pages** → Deploy from a branch → `main` / `/` → Save.
3. **Settings → Actions → General → Workflow permissions = Read and write**, or the
   weekly job can't commit refreshed puzzles.

`index.html` and `puzzles.json` both live at the repo root. The app fetches
`puzzles.json` **relatively**, so it resolves under the `/blitz-climb/` project path —
don't move either file into a subfolder without fixing that fetch.

## Part 2 — Supabase (one-time)

1. **Create the project** at https://supabase.com (free tier). Any region near you.
2. **Create the table**: dashboard → **SQL Editor** → New query → paste all of
   [`db/schema.sql`](../db/schema.sql) → **Run**. Safe to re-run.
3. **Turn on auto-confirm** so signup needs no email round-trip:
   `PATCH /v1/projects/{ref}/config/auth` with `{"mailer_autoconfirm": true,
   "password_min_length": 10}` (or Authentication → Providers → Email → uncheck
   "Confirm email"). Already applied to this project.
4. **Wire the keys into the app**: **Settings → API** → copy the **Project URL** and the
   **anon / publishable key** into the two constants at the top of the sync section in
   `index.html`:

   ```js
   const SB_URL="https://<project>.supabase.co";
   const SB_ANON="<anon key>";
   ```

   Then `python build.py` and push. Both values are **safe to commit** — the anon key is
   designed to ship in frontend code, and RLS is what actually protects the data. That is
   exactly why step 2 must not be skipped.
5. **Sign in once** (see Part 3), then **close the door**: **Authentication → Providers →
   Email → turn off "Allow new users to sign up."** Until you do, anyone who reads the
   anon key out of the page can create an account in your project. They still can't read
   your data — RLS scopes every row to its owner — but there's no reason to leave signup open.

### Why password auth, not codes or magic links
Both were tried and are **not viable on the free tier**:
- Email templates cannot be edited at all ("Email template modification is not available
  for free tier projects using the default email provider"), so `{{ .Token }}` can't be
  added and the mailer only ever sends a link.
- `rate_limit_email_sent` is **2 emails per hour**. Signing in on two devices plus one
  retry exhausts it.

Password auth sends no email, has no rate limit, and behaves identically on every device.
A magic link also opens in whichever browser owns links on that phone — usually not the
one you're syncing.

## Part 3 — Turn on sync (per device)
1. Open the app → **Sync** tab.
2. Enter your email and a password of 10+ characters → **Sign in & sync**.
   The first device you do this on creates the account; the rest just sign in.

The Home tab pill turns green and reads "Synced across your devices". Repeat on the other
device with the **same email and password**.

**Do the device that already has your progress first.** Sync is last-write-wins with no
merge, so if an empty device syncs last it wins.

## Verifying it works
```bash
SB_SERVICE=<service_role key> node tools/verify_supabase.mjs
```
Drives the *same* functions the app ships (extracted from `index.html`, not a
reimplementation): anon-key-cannot-read (RLS), account creation, repeat sign-in,
wrong-password message, write, read-back, upsert-not-duplicate, second-device read, and
token refresh. It creates and deletes a throwaway account, so it needs no email and no
interaction. The service_role key is read from the env and must never be committed.

The load-bearing assertion is the first one. If a bare anon key can read rows, RLS is off
and nothing else matters.

## Notes and known edges
- **Last write wins.** No merge. Fine for one person switching devices; don't drill on two
  at once.
- **Password is 10+ characters** (`password_min_length`). There's no reset flow wired up;
  if you forget it, reset the password from the Supabase dashboard under Authentication → Users.
- **Free tier projects pause after ~a week of inactivity** — a paused project makes sync
  fail (progress still saves locally, and the pill goes amber). Un-pause from the dashboard.
- **Export / Import** on the Sync tab still works with sync off, and needs no account.
- Sessions live in this browser's local storage and refresh automatically; **Sign out**
  clears them on that device only.

## Weekly puzzle refresh
`.github/workflows/weekly.yml` runs Sundays: pulls your latest 60 blitz games from the
Lichess API, re-runs Stockfish, regenerates `puzzles.json`, and commits it. Pages redeploys
and the app picks up the new set on next load — no Supabase and no Cloudflare involved.

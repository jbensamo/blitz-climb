# Blitz Climb — Cross-Device Setup (≈10 min, free, GitHub only)

Goal: open your trainer at one web address on any device, with progress saved in the
cloud (a **private GitHub Gist**) so it can't be wiped by clearing a browser.

Your progress lives in the Gist. The app on each device just reads and writes that Gist —
there is no server of our own. The token is **never** in the hosted file: you paste it
into the app once per device and it stays in that device's local storage only.

**Already hosted:** https://jbensamo.github.io/blitz-climb/ (repo `jbensamo/blitz-climb`,
GitHub Pages from `main`). If that's already up, skip to Step 2.

---

## Step 1 — Host the app (GitHub Pages)
Already done for this repo, recorded here so it can be rebuilt:

1. Push the repo to a **personal** GitHub account, public, default branch `main`.
2. **Settings → Pages** → Source: *Deploy from a branch* → Branch `main`, folder `/` → Save.
3. After ~1 min the app is at `https://<username>.github.io/blitz-climb/`.

`index.html` and `puzzles.json` both live at the repo root. The app fetches
`puzzles.json` **relatively**, so it resolves correctly under the `/blitz-climb/` project
path — don't move either file into a subfolder without fixing that fetch.

The hosted HTML is public, but it contains only chess puzzles from your own games plus
links to those games on Lichess. No token, no personal data.

## Step 2 — Make a token with only the `gist` scope
1. Go to https://github.com/settings/tokens → **Generate new token (classic)**.
2. Note: e.g. "blitz climb". Expiration: your call — an expiry is worth setting.
3. Check **only** the box named **`gist`**. Nothing else.
4. Generate, then **copy the token** (starts with `ghp_…`). You won't see it again.

### Read this before pasting it anywhere
- A `gist`-scoped token can read and write **all** of your gists — not just this one.
  That's the blast radius if it leaks.
- `<username>.github.io` is **one origin for every Pages project on your account**.
  Browser local storage is per-origin, so anything else you ever publish under
  `jbensamo.github.io` can read this token out of the same storage.
- It is revocable in one click on that same tokens page, and the app only ever sends it
  to `api.github.com` over HTTPS as an `Authorization` header.

If that trade isn't worth it to you, just don't turn sync on — the app works fine
device-local, and the Sync tab's **Export / Import** moves progress by hand.

## Step 3 — Turn on cloud sync
**On your first device (say, laptop):**
1. Open the app → **Sync** tab.
2. Paste your token into *GitHub token*. Leave *Gist ID* **blank**.
3. Tap **Connect & sync**. It creates a private Gist and shows its **Gist ID**
   (a long hex string). Copy that ID.

**On your second device (phone):**
1. Open the same URL → **Sync** tab.
2. Paste the **same token** and the **Gist ID** from above.
3. Tap **Connect & sync**. Your progress appears.

Success looks like: *"Synced ✓ — Gist ID "…" (enter that, with the same token, on your
other device)"*. A wrong or under-scoped token says
*"GitHub rejected the token (needs the "gist" scope)"*.

From then on, solving puzzles / logging sessions on either device writes to the Gist about
a second later, and each device pulls the latest when you open it. Offline, it keeps
everything locally and syncs on your next change.

---

## Notes and known edges
- **Give it a couple of seconds between devices.** GitHub's gist reads can lag a write by
  up to ~2 seconds (replica lag — a cache-busting parameter does not help, this was
  measured). Open device B a moment after device A, not instantly.
- **Last write wins.** There's no merge: whichever device saves most recently defines the
  state. Fine for one person switching devices; don't drill on two devices at once.
- **If you delete the Gist**, the next save transparently creates a fresh one and shows
  the new ID — you don't get an error, but the other device needs the new ID.
- **Reset** (Sync tab) clears both the local and the Gist copy when sync is on.
- **Export / Import** still works with sync off, and is the no-token path.
- Moving hosts later (Netlify, Cloudflare, your own domain)? The same single file works
  anywhere — only the URL changes; the Gist keeps your progress.

## Weekly puzzle refresh (no Cloudflare needed)
`.github/workflows/weekly.yml` runs Sundays: pulls your latest 60 blitz games from the
Lichess API, re-runs Stockfish, regenerates `puzzles.json` from your newest blunders, and
commits it. Pages redeploys, and the app picks up the new set on next load. This closes
the loop entirely inside GitHub — the Cloudflare KV publish step self-skips unless the
`CF_WORKER_URL` and `ADMIN_TOKEN` repo secrets are set.

Requires **Settings → Actions → General → Workflow permissions = Read and write**, or the
job can't commit the refreshed puzzles back.

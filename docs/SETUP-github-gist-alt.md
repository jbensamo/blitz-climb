# Blitz Climb — Cross-Device Setup (≈15 min, free)

Goal: open your trainer at one web address on any device, with progress saved in the
cloud (a private GitHub Gist) so it can't be wiped by clearing a browser.

Your progress lives in the Gist. The app on each device just reads/writes that Gist.
Your token is **never** stored in the hosted file — you paste it into the app once per
device and it stays in that device's local storage only.

---

## Step 1 — Get a GitHub account
If you don't have one: https://github.com/signup (free). Use a **personal** account,
not a work one.

## Step 2 — Make a token with only the `gist` scope
1. Go to https://github.com/settings/tokens?type=beta  → actually use **classic**:
   https://github.com/settings/tokens → **Generate new token (classic)**.
2. Note: e.g. "chess trainer". Expiration: your call (no expiry = never re-do this).
3. Check **only** the box named **`gist`**. Nothing else.
4. Generate, then **copy the token** (starts with `ghp_…`). You won't see it again.

Security: a `gist`-scoped classic token can read/write your gists and nothing else.
If it ever leaks, revoke it on that same page — takes one click.

## Step 3 — Host the app at a URL (GitHub Pages)
1. Create a new **public** repo, e.g. `chess-trainer`.
2. Upload `chess-trainer.html` and **rename it to `index.html`**.
3. Repo **Settings → Pages** → Source: *Deploy from a branch* → Branch: `main` / `/root`
   → Save.
4. Wait ~1 min. Your app is now at:
   `https://<your-username>.github.io/chess-trainer/`
   Bookmark that on your phone and laptop.

(The hosted HTML is public, but it only contains your chess puzzles — no token, no
personal data. The token is entered at runtime and stays on your device.)

## Step 4 — Turn on cloud sync
**On your first device (say, laptop):**
1. Open the Pages URL → **Sync** tab.
2. Paste your token into *GitHub token*. Leave *Gist ID* blank.
3. Tap **Connect & sync**. It creates a private Gist and shows its **Gist ID**
   (e.g. `gistABC123…`). Copy that ID.

**On your second device (phone):**
1. Open the same Pages URL → **Sync** tab.
2. Paste the **same token** and the **Gist ID** from step above.
3. Tap **Connect & sync**. Your progress appears.

That's it. From now on, solving puzzles / logging sessions on either device writes to
the Gist within ~1 second, and each device pulls the latest on open. If you're offline,
it keeps everything locally and syncs on your next change.

---

## Notes
- **Reset** (Sync tab) clears both local and cloud copies when sync is on.
- Want to move hosts later (Netlify, Cloudflare Pages, your own site)? Same single
  file works anywhere — only the URL changes; the Gist keeps your progress.
- **Phase 2 (later):** a weekly GitHub Actions job can auto-pull your latest Lichess
  games, re-run Stockfish, generate fresh puzzles from your newest blunders, and write
  them to the same Gist — fully hands-off. Say the word and I'll build it.

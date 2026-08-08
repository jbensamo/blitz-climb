// End-to-end check of the Supabase sync backend, driving the SAME functions the app
// ships (extracted from index.html) rather than a reimplementation.
//
//   SB_EMAIL=you@example.com node tools/verify_supabase.mjs
//
// It emails you one 6-digit code and waits for you to paste it. Supabase allows one
// code per minute, so don't loop this.
//
// The load-bearing check is RLS_ANON: reading the table with only the public anon key
// and no user session must come back empty. If it doesn't, the anon key in the shipped
// HTML is an open door and nothing else about this setup matters.
import fs from "node:fs";
import readline from "node:readline/promises";

const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");
const grab = (from, to) => {
  const a = html.indexOf(from), b = html.indexOf(to);
  if (a < 0 || b < 0) throw new Error(`could not locate ${from}`);
  return html.slice(a, b);
};
const src = grab('const SB_URL=', "function adoptRemote");

const store = new Map();
globalThis.localStorage = { getItem: k => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)) };
globalThis.$ = () => null;
globalThis.STATE = { version: 5, player: "jbensamo", checks: {}, habitDays: {}, sessions: [],
                     puzzles: { solved: { p1: true }, attempts: {}, firstTry: {}, byDay: {} },
                     updated: new Date().toISOString() };

const app = new Function(src + `
  return {cloud, sbFetch, sbSession, sbSendCode, sbVerifyCode, dbRead, dbWrite, sbConfigured, SB_URL, SB_ANON};`)();

if (!app.sbConfigured()) { console.error("FAIL — SB_URL / SB_ANON are still empty in index.html"); process.exit(1); }
const email = process.env.SB_EMAIL;
if (!email) { console.error("FAIL — set SB_EMAIL"); process.exit(1); }

const ok = (c, label) => console.log(`${c ? "PASS" : "FAIL"} — ${label}`);
let failures = 0;
const check = (c, label) => { ok(c, label); if (!c) failures++; };

// 1. anon-only read must be empty (RLS)
const anonRes = await fetch(`${app.SB_URL.replace(/\/$/, "")}/rest/v1/progress?select=*`, {
  headers: { apikey: app.SB_ANON },
});
const anonBody = await anonRes.text();
check(anonRes.status === 200 ? anonBody.trim() === "[]" : anonRes.status === 401 || anonRes.status === 403,
  `RLS_ANON: anon key alone cannot read rows (status ${anonRes.status}, body ${anonBody.slice(0, 60)})`);

// 2. sign in
await app.sbSendCode(email);
console.log(`\n  a 6-digit code was emailed to ${email}`);
const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
const code = (await rl.question("  paste it here: ")).trim();
rl.close();
await app.sbVerifyCode(email, code);
check(!!app.cloud.at && !!app.cloud.uid, "sign-in with the emailed code returns a session + user id");

// 3. write, then read back
await app.dbWrite();
const back = await app.dbRead();
check(back && back.puzzles?.solved?.p1 === true, "write then read returns this device's state");

// 4. upsert, not duplicate-insert
STATE.sessions.push({ date: "2026-08-07", acpl: 44, blunders: 0.4, note: "verify" });
STATE.updated = new Date().toISOString();
await app.dbWrite();
const back2 = await app.dbRead();
check(back2?.sessions?.length === 1 && back2.sessions[0].acpl === 44, "second write upserts the same row");
const rows = await app.sbFetch("/rest/v1/progress?select=user_id", {}, true);
check(rows.length === 1, `exactly one row for this user (got ${rows.length})`);

// 5. a second "device" with the same login sees it
const store2 = new Map();
const saved = globalThis.localStorage;
globalThis.localStorage = { getItem: k => (store2.has(k) ? store2.get(k) : null), setItem: (k, v) => store2.set(k, String(v)) };
const dev2 = new Function(src + "\n return {cloud, dbRead, sbSession};")();
globalThis.localStorage = saved;
Object.assign(dev2.cloud, { at: app.cloud.at, rt: app.cloud.rt, exp: app.cloud.exp, uid: app.cloud.uid, email });
const seen = await dev2.dbRead();
check(seen?.sessions?.[0]?.acpl === 44, "a second device with the same account reads the same row");

// 6. refresh-token path (what every reload after an hour depends on)
app.cloud.at = ""; app.cloud.exp = 0;
await app.sbSession();
check(!!app.cloud.at, "expired access token is refreshed from the refresh token");

console.log(failures ? `\n${failures} FAILURE(S)` : "\nall checks passed");
process.exit(failures ? 1 : 0);

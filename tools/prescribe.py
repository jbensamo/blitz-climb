#!/usr/bin/env python3
"""Turn data/diagnosis.json into a prescribed puzzle set aimed at his actual leaks.

    zstd -dc build/corpus/lichess_db_puzzle.csv.zst | python3 tools/prescribe.py

Writes puzzles/prescribed.json and updates puzzles/index.json so the module appears
first in the graded curriculum.

Weighting: a theme's share comes from how often he LOSES points to it, counting
"allowed" (what punished him) 1.5x "missed" (wins he didn't see) — the plan's core
leak is not scanning the opponent's threats, so being punished by a motif is the
stronger signal that he needs it.

No single theme may exceed CAP of the set. That guard exists because `quietMove` is
partly the classifier's fallback bucket, so its raw count overstates it; without the
cap the prescription would be 40% quiet moves on the strength of an artifact.
"""
import csv, json, os, sys
from collections import defaultdict
import chess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

TOTAL = int(os.environ.get("TOTAL", 90))
# Each rebuild is a NEW prescription, so it needs new ids: progress is keyed by id
# alone, and reusing "Lrx1" for a different puzzle would mark it already solved.
ID_PREFIX = os.environ.get("ID_PREFIX", "Lrx")
CAP = float(os.environ.get("CAP", 0.20))
ALLOWED_WEIGHT = float(os.environ.get("ALLOWED_WEIGHT", 1.5))
MIN_PLAYS, MAX_DEV, MIN_POP = 1000, 90, 90
BANDS = [(1600, 1900), (1900, 2200)]

# our classifier's vocabulary -> Lichess puzzle theme tags
THEME_MAP = {
    "fork": ["fork"], "pin": ["pin"], "skewer": ["skewer"],
    "discoveredAttack": ["discoveredAttack", "discoveredCheck"],
    "hangingPiece": ["hangingPiece"], "sacrifice": ["sacrifice"],
    "quietMove": ["quietMove", "zugzwang"], "advancedPawn": ["advancedPawn"],
    "mate": ["mateIn2", "mateIn3"],
    # our classifier's own label; Lichess has no "minorEndgame" tag, so map it
    "minorEndgame": ["bishopEndgame", "knightEndgame"],
    # "capture" and "check" are our fallback buckets, not real themes — ignored.
}
ENDGAME_TAGS = {"rookEndgame", "pawnEndgame", "bishopEndgame", "knightEndgame",
                "queenEndgame", "minorEndgame"}

diag = json.load(open("data/diagnosis.json"))
missed, allowed = diag["missed"], diag["allowed"]

score = defaultdict(float)
for t, c in missed.items():
    if t in THEME_MAP: score[t] += c
for t, c in allowed.items():
    if t in THEME_MAP: score[t] += c * ALLOWED_WEIGHT
# endgames get their own share, proportional to how often he errs in each type
eg = {k: v for k, v in diag.get("endgameTypes", {}).items() if k in ENDGAME_TAGS}
eg_total = sum(eg.values())

tac_total = sum(score.values())
if not tac_total:
    sys.exit("diagnosis has no usable themes")

# endgames take a share of the set equal to their share of his errors by phase
phases = diag.get("phases", {})
eg_share = phases.get("endgame", 0) / max(1, sum(phases.values()))
eg_slots = int(TOTAL * eg_share) if eg_total else 0
tac_slots = TOTAL - eg_slots

quota = {}
cap_n = int(TOTAL * CAP)
for t, s in score.items():
    quota[t] = min(cap_n, max(3, round(tac_slots * s / tac_total)))
for t, c in eg.items():
    quota[t] = min(cap_n, max(2, round(eg_slots * c / max(1, eg_total))))

# which Lichess tags satisfy each quota key
want = {}
for k in quota:
    want[k] = set(THEME_MAP.get(k, [k]))

print("prescription quotas (from his own error profile):", file=sys.stderr)
for k, v in sorted(quota.items(), key=lambda kv: -kv[1]):
    print(f"   {v:3d}  {k}", file=sys.stderr)

# never re-serve something he already has
seen_fen = {p["fen"] for p in json.load(open("data/puzzles.json"))}
for f in os.listdir("puzzles"):
    if f.endswith(".json") and f != "index.json" and f != "prescribed.json":
        for p in json.load(open(f"puzzles/{f}")):
            seen_fen.add(p["fen"])

buckets = defaultdict(list)
need = {(k, b) for k in quota for b in range(len(BANDS))}
per_band = {k: max(1, quota[k] // len(BANDS)) for k in quota}

reader = csv.reader(sys.stdin); next(reader)
scanned = 0
for row in reader:
    if not need: break
    if len(row) < 8: continue
    scanned += 1
    try:
        rating = int(row[3]); dev = int(row[4]); pop = int(row[5]); plays = int(row[6])
    except ValueError:
        continue
    if dev > MAX_DEV or pop < MIN_POP or plays < MIN_PLAYS: continue
    band = next((i for i, (lo, hi) in enumerate(BANDS) if lo <= rating < hi), None)
    if band is None: continue
    themes = set(row[7].split())
    if "oneMove" in themes: continue
    for k, tags in want.items():
        if (k, band) in need and (themes & tags):
            buckets[(k, band)].append(row)
            if len(buckets[(k, band)]) >= per_band[k]:
                need.discard((k, band))
            break

print(f"scanned {scanned:,} rows; {len(need)} buckets unfilled", file=sys.stderr)

def convert(row, pid, why):
    fen, moves = row[1], row[2].split()
    if len(moves) < 2: return None
    board = chess.Board(fen)
    setup = chess.Move.from_uci(moves[0])
    if setup not in board.legal_moves: return None
    board.push(setup)
    start = board.fen(); solver = board.turn
    line = []
    for u in moves[1:]:
        mv = chess.Move.from_uci(u)
        if mv not in board.legal_moves: return None
        is_user = (board.turn == solver)
        san = board.san(mv)
        frm, to = chess.square_name(mv.from_square), chess.square_name(mv.to_square)
        board.push(mv)
        line.append({"uci": u, "from": frm, "to": to, "san": san, "fen": board.fen(),
                     "user": is_user, "promo": (mv.promotion and chess.piece_symbol(mv.promotion)) or None})
    while line and not line[-1]["user"]: line.pop()
    if not line or not line[0]["user"]: return None
    return {"id": pid, "kind": "line", "cat": "prescribed", "fen": start,
            "sideToMove": "w" if solver == chess.WHITE else "b",
            "userColor": "w" if solver == chess.WHITE else "b",
            "line": line, "motif": why, "rating": int(row[3]), "youPlayed": "—",
            "sourceUrl": row[8], "moveNo": chess.Board(start).fullmove_number,
            "explain": f"Prescribed: you lose points to this. Lichess {row[0]} · rated {row[3]}."}

items, seen = [], set()
rows_by_key = {k: [] for k in quota}
for (k, b), rows in buckets.items():
    rows_by_key[k] += rows
for k in sorted(rows_by_key, key=lambda x: -quota[x]):
    rows = sorted(rows_by_key[k], key=lambda r: int(r[3]))[:quota[k]]
    for r in rows:
        if r[1] in seen_fen or r[1] in seen: continue
        it = convert(r, f"{ID_PREFIX}{len(items)+1}", k)
        if it is None: continue
        seen.add(r[1]); items.append(it)

items.sort(key=lambda p: p["rating"])
json.dump(items, open("puzzles/prescribed.json", "w"), separators=(",", ":"))

# put it first in the manifest
man = [m for m in json.load(open("puzzles/index.json")) if m["id"] != "prescribed"]
top = sorted(quota.items(), key=lambda kv: -kv[1])[:4]
man.insert(0, {
    "id": "prescribed", "cat": "prescribed", "name": "🎯 Prescribed for you",
    "blurb": "Chosen from your own error profile — heaviest on " +
             ", ".join(k for k, _ in top) + ". Rebuilt each Sunday.",
    "file": "puzzles/prescribed.json", "prefix": ID_PREFIX, "n": len(items),
    "ratingLo": items[0]["rating"] if items else 0,
    "ratingHi": items[-1]["rating"] if items else 0,
    "kb": round(os.path.getsize("puzzles/prescribed.json") / 1024),
})
json.dump(man, open("puzzles/index.json", "w"), indent=1)

by = defaultdict(int)
for p in items: by[p["motif"]] += 1
print(f"\nBUILT {len(items)} prescribed puzzles -> puzzles/prescribed.json")
for k, v in sorted(by.items(), key=lambda kv: -kv[1]): print(f"   {v:3d}  {k}")

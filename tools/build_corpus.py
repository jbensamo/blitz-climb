#!/usr/bin/env python3
"""Build the graded curriculum from the Lichess puzzle database (CC0).

    zstd -dc build/corpus/lichess_db_puzzle.csv.zst | python3 tools/build_corpus.py

Writes puzzles/<module>.json plus puzzles/index.json (the manifest the app reads at
boot so it can show module sizes without downloading every module).

Two things this file exists to get right:

1. THE OFFSET. In the Lichess CSV, `FEN` is the position *before* the opponent's
   setup move and `Moves[0]` IS that opponent move — the solver plays `Moves[1]`
   first. So the puzzle position is FEN+Moves[0], and the solver's colour is whoever
   is to move after it. Off by one here and every puzzle asks the user to play the
   opponent's move.
2. ONE MODULE PER PUZZLE. Puzzles carry several themes; each is assigned to the first
   matching group in GROUPS order, so the same position can't appear in two modules.
"""
import csv, json, os, sys
from collections import defaultdict
import chess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
OUTDIR = "puzzles"

PER_MODULE = int(os.environ.get("PER_MODULE", 54))
BANDS = [(1600, 1850), (1850, 2100), (2100, 2400)]      # each module ramps through these
PER_BAND = PER_MODULE // len(BANDS)

MIN_PLAYS = 1000
MAX_DEV = 90
MIN_POP = 90

# Order matters: a puzzle lands in the first group whose themes it matches.
GROUPS = [
    ("rookend",  "♜ Rook endgames",        {"rookEndgame"},
     "The most common endgame there is, and the one most often thrown away."),
    ("pawnend",  "♙ Pawn endgames",        {"pawnEndgame"},
     "Pure calculation: opposition, breakthroughs, races. No pieces to hide behind."),
    ("minorend", "♝ Minor-piece endgames", {"bishopEndgame", "knightEndgame"},
     "Bishop and knight endings — where the wrong trade decides the game."),
    ("queenend", "♛ Queen endgames",       {"queenEndgame", "queenRookEndgame"},
     "Perpetual-check dodging and centralisation."),
    ("mate",     "♔ Mating nets",          {"mateIn2", "mateIn3", "mateIn4", "mate"},
     "Forced mates in 2 to 4. Calculate to the end before you commit."),
    ("quiet",    "🧠 Quiet moves & zugzwang", {"quietMove", "zugzwang", "intermezzo"},
     "No check, no capture — the hardest kind of move to see. Directly on your leak."),
    ("defend",   "🛡 Defensive resources",  {"defensiveMove"},
     "You're under fire and there is exactly one move that holds. Find it."),
    ("deflect",  "🎣 Deflection & decoy",   {"deflection", "attraction", "clearance",
                                             "interference", "capturingDefender"},
     "Remove, overload or lure the defender. The tactics you miss most after forks."),
    ("discover", "💥 Discovered attacks",   {"discoveredAttack", "discoveredCheck", "doubleCheck"},
     "Move one piece, unleash another. Easy to miss from both sides."),
    ("pin",      "📌 Pins & skewers",       {"pin", "skewer", "xRayAttack"},
     "Line pieces doing two jobs at once."),
    ("fork",     "🍴 Forks & double attacks", {"fork", "doubleAttack"},
     "Two threats, one move — the most common way material actually changes hands."),
    ("attack",   "⚔ Attacking the king",   {"kingsideAttack", "queensideAttack", "exposedKing",
                                            "sacrifice", "advancedPawn", "promotion"},
     "Sustained attacks and breakthroughs against a king."),
]

def band_of(rating):
    for i, (lo, hi) in enumerate(BANDS):
        if lo <= rating < hi:
            return i
    return None

buckets = defaultdict(list)          # (group_key, band) -> rows
need = {(g[0], b) for g in GROUPS for b in range(len(BANDS))}

reader = csv.reader(sys.stdin)
header = next(reader)
scanned = 0
for row in reader:
    if len(row) < 8:
        continue
    scanned += 1
    if not need:
        break
    try:
        rating = int(row[3]); dev = int(row[4]); pop = int(row[5]); plays = int(row[6])
    except ValueError:
        continue
    if dev > MAX_DEV or pop < MIN_POP or plays < MIN_PLAYS:
        continue
    b = band_of(rating)
    if b is None:
        continue
    themes = set(row[7].split())
    if "oneMove" in themes:                      # too trivial to call advanced
        continue
    for key, _name, want, _blurb in GROUPS:
        if themes & want:
            if (key, b) in need:
                buckets[(key, b)].append(row)
                if len(buckets[(key, b)]) >= PER_BAND:
                    need.discard((key, b))
            break
    if scanned % 500000 == 0:
        print(f"  scanned {scanned:,}; {len(need)} buckets still filling", flush=True, file=sys.stderr)

print(f"scanned {scanned:,} rows; {len(need)} buckets unfilled", file=sys.stderr)

# ---- convert to the app's schema -------------------------------------------------
def convert(row, pid):
    fen, moves = row[1], row[2].split()
    if len(moves) < 2:
        return None
    board = chess.Board(fen)
    setup = chess.Move.from_uci(moves[0])        # the OPPONENT's move: FEN is before it
    if setup not in board.legal_moves:
        return None
    board.push(setup)
    start_fen = board.fen()
    solver = board.turn                           # whoever is to move now solves

    line = []
    for i, u in enumerate(moves[1:]):
        mv = chess.Move.from_uci(u)
        if mv not in board.legal_moves:
            return None
        is_user = (board.turn == solver)
        san = board.san(mv)
        frm, to = chess.square_name(mv.from_square), chess.square_name(mv.to_square)
        board.push(mv)
        line.append({"uci": u, "from": frm, "to": to, "san": san, "fen": board.fen(),
                     "user": is_user,
                     "promo": (mv.promotion and chess.piece_symbol(mv.promotion)) or None})
    while line and not line[-1]["user"]:
        line.pop()
    if not line or not line[0]["user"]:
        return None
    themes = [t for t in row[7].split()
              if t not in ("short", "long", "veryLong", "crushing", "advantage",
                           "master", "masterVsMaster", "middlegame", "opening", "endgame")]
    return {
        "id": pid,
        "kind": "line",
        "fen": start_fen,
        "sideToMove": "w" if solver == chess.WHITE else "b",
        "userColor": "w" if solver == chess.WHITE else "b",
        "line": line,
        "motif": ", ".join(themes[:3]) or "tactic",
        "rating": int(row[3]),
        "youPlayed": "—",
        "sourceUrl": row[9] if len(row) > 9 and row[9].startswith("http") else row[8],
        "moveNo": chess.Board(start_fen).fullmove_number,
        "explain": f"Lichess puzzle {row[0]} · rated {row[3]} · {', '.join(themes[:4])}",
    }

os.makedirs(OUTDIR, exist_ok=True)
manifest = []
own = {p["fen"] for p in json.load(open("data/puzzles.json"))}   # never duplicate his own

for key, name, _want, blurb in GROUPS:
    rows = []
    for b in range(len(BANDS)):
        rows += buckets[(key, b)]
    rows.sort(key=lambda r: int(r[3]))                    # ramp difficulty inside the module
    items, seen = [], set()
    for r in rows:
        if r[1] in own or r[1] in seen:
            continue
        it = convert(r, f"L{key}{len(items)+1}")
        if it is None:
            continue
        seen.add(r[1]); items.append(it)
    if not items:
        print(f"  !! {key}: nothing built", file=sys.stderr);  continue
    path = f"{OUTDIR}/{key}.json"
    json.dump(items, open(path, "w"), separators=(",", ":"))
    lo, hi = items[0]["rating"], items[-1]["rating"]
    manifest.append({"id": key, "cat": key, "name": name, "blurb": blurb,
                     "file": f"{OUTDIR}/{key}.json", "prefix": f"L{key}",
                     "n": len(items), "ratingLo": lo, "ratingHi": hi,
                     "kb": round(os.path.getsize(path) / 1024)})
    print(f"  {key:9s} {len(items):3d} puzzles  {lo}-{hi}  {manifest[-1]['kb']}KB")

json.dump(manifest, open(f"{OUTDIR}/index.json", "w"), indent=1)
total = sum(m["n"] for m in manifest)
print(f"\nBUILT {total} corpus puzzles in {len(manifest)} modules -> {OUTDIR}/")
print(f"total {sum(m['kb'] for m in manifest)}KB, fetched only when a module is opened")

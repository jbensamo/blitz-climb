#!/usr/bin/env python3
"""Build C.C.T. scan drills from the owner's own blunder positions.

The leak is not scanning the opponent's Checks / Captures / Threats before moving,
so the drill uses the positions where that actually cost something: the position
the owner was about to move in, right before a blunder.

Task: "Before you move — click every square where your opponent can capture."
Targets are the destination squares of the opponent's captures, found by giving
them a free move (a null move) and enumerating. No engine needed: this is legal
move generation, so it is exact by construction.

    python3 tools/gen_cct.py build/sets/cand_all_blitz.json [more caches...]

Writes build/sets/cct.json.
"""
import json, os, sys
import chess

OUT = os.environ.get("OUT", "build/sets/cct.json")
ID_PREFIX = os.environ.get("ID_PREFIX", "c")
MAX_ITEMS = int(os.environ.get("MAX_ITEMS", 14))
MIN_T, MAX_T = 1, 5          # too few is trivial, too many is a scavenger hunt
EXCLUDE = os.environ.get("EXCLUDE", "")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

def opponent_captures(board):
    """Squares the side NOT to move could capture on, if handed a free move."""
    b = board.copy()
    b.push(chess.Move.null())
    out = {}
    for m in b.legal_moves:
        if b.is_capture(m):
            victim = b.piece_at(m.to_square)
            if victim is None:            # en passant
                continue
            out[chess.square_name(m.to_square)] = victim.symbol().upper()
    return out

def checks_available(board):
    b = board.copy(); b.push(chess.Move.null())
    return sum(1 for m in b.legal_moves if b.gives_check(m))

seen_fen = set()
if EXCLUDE and os.path.exists(EXCLUDE):
    seen_fen = {p["fen"] for p in json.load(open(EXCLUDE))}
    print(f"excluding {len(seen_fen)} positions already in the library")

cands = []
for path in sys.argv[1:]:
    if not os.path.exists(path):
        print(f"  skip missing {path}");  continue
    cands += json.load(open(path))
print(f"{len(cands)} blunder candidates to draw from")

cands.sort(reverse=True, key=lambda c: c[0])       # worst blunders first
items, per_game = [], {}
for c in cands:
    if len(items) >= MAX_ITEMS: break
    drop, gi, fen, uc_s, played_uci, url, movno = c[0], c[1], c[2], c[3], c[4], c[5], c[6]
    if fen in seen_fen: continue
    if per_game.get(gi, 0) >= 2: continue
    board = chess.Board(fen)
    if board.is_check(): continue                   # a null move makes no sense in check
    caps = opponent_captures(board)
    if not (MIN_T <= len(caps) <= MAX_T): continue

    seen_fen.add(fen);  per_game[gi] = per_game.get(gi, 0) + 1
    squares = sorted(caps)
    items.append({
        "id": f"{ID_PREFIX}{len(items)+1}",
        "kind": "find",
        "cat": "cct",
        "fen": fen,
        "sideToMove": "w" if board.turn == chess.WHITE else "b",
        "userColor": uc_s,
        "prompt": "Before you move: click every square where your opponent can capture.",
        "targets": squares,
        "sourceUrl": url,
        "moveNo": movno,
        "motif": f"{len(squares)} capture{'s' if len(squares)!=1 else ''} available",
        "explain": ("Your opponent can capture on " + ", ".join(squares) +
                    f". They also have {checks_available(board)} check(s) here. "
                    "This is the position where you went wrong — the scan is what catches it."),
    })

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(items, open(OUT, "w"), indent=1)
print(f"\nBUILT {len(items)} C.C.T. drills -> {OUT}")
for it in items:
    print(f"  {it['id']}: {it['sideToMove']} to move | targets {it['targets']} | {it['sourceUrl']} m{it['moveNo']}")

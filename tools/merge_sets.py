#!/usr/bin/env python3
"""Merge the generated puzzle sets into the single puzzles.json the app serves.

    python3 tools/merge_sets.py [build/sets]

Writes ./puzzles.json (what GitHub Pages serves) and data/puzzles.json (the copy
that gets embedded into index.html as the offline fallback by build.py).

Refuses to write on a duplicate id: progress is keyed by id alone, so a collision
would mark a brand-new puzzle as already solved.
"""
import json, os, sys, glob

SRC = sys.argv[1] if len(sys.argv) > 1 else "build/sets"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

import chess

def phase_of(fen):
    """Same classifier as analyze.py / generate_puzzles.py."""
    b = chess.Board(fen)
    npm = sum({chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5,
               chess.QUEEN: 9, chess.KING: 0}[p.piece_type]
              for p in b.piece_map().values() if p.piece_type not in (chess.PAWN, chess.KING))
    if b.fullmove_number <= 12: return "opening"
    return "endgame" if npm <= 16 else "middlegame"

# The original blitz set is the baseline. Classify it by phase rather than calling it
# all "tactics": several of those positions really are endgames, and tagging them here
# keeps their ids (and therefore the owner's solved progress) while filing them under
# the set they belong in.
merged = json.load(open("data/puzzles.json"))
for p in merged:
    p["phase"] = p.get("phase") or phase_of(p["fen"])
    # Only DERIVE a cat for legacy items that never had one. Re-deriving every run
    # clobbered explicit cats (strategy/cct/opening) back to "tactics" on the second
    # merge, silently emptying those modules.
    if not p.get("cat"):
        p["cat"] = "endgame" if p["phase"] == "endgame" else "tactics"

seen_id = {p["id"] for p in merged}
seen_fen = {p["fen"]: p["id"] for p in merged}
added, dropped = {}, []

# Endgame sets before tactics sets: the phase-filtered run is the better home for a
# position that both runs found, and the unfiltered tactics run re-derives endgames.
paths = [q for q in sorted(glob.glob(os.path.join(SRC, "*.json")))
         if not os.path.basename(q).startswith("cand_")]
paths.sort(key=lambda q: 0 if "end_" in os.path.basename(q) else 1)

for path in paths:
    try:
        s = json.load(open(path))
    except Exception as e:
        print(f"  skip {path}: {e}");  continue
    if not isinstance(s, list) or not s or not ("line" in s[0] or "targets" in s[0]):
        print(f"  skip {path}: not a puzzle set");  continue
    kept = 0
    for p in s:
        if p["id"] in seen_id:
            # Same id AND same position = this set was already merged; re-running is a
            # no-op. Same id, DIFFERENT position is a real collision: progress is keyed
            # by id, so it would mark a new puzzle as already solved.
            if seen_fen.get(p["fen"]) == p["id"]:
                continue
            raise SystemExit(f"ID COLLISION: {p['id']} from {path} already exists with a "
                             f"different position. Change that set's ID_PREFIX — progress "
                             f"is keyed by id and would carry over to the wrong puzzle.")
        if p["fen"] in seen_fen:
            # Same position, different id: the owner would solve it twice.
            dropped.append((p["id"], os.path.basename(path), seen_fen[p["fen"]]))
            continue
        seen_id.add(p["id"]);  seen_fen[p["fen"]] = p["id"]
        merged.append(p);  kept += 1
        added[p.get("cat", "tactics")] = added.get(p.get("cat", "tactics"), 0) + 1
    print(f"  + {kept:2d} of {len(s):2d} from {os.path.basename(path)}")

for out in ("puzzles.json", "data/puzzles.json"):
    json.dump(merged, open(out, "w"), indent=1)

by_cat = {}
for p in merged:
    by_cat[p.get("cat", "tactics")] = by_cat.get(p.get("cat", "tactics"), 0) + 1
print(f"\nwrote puzzles.json and data/puzzles.json — {len(merged)} puzzles: {by_cat}")
print("added this run:", added or "nothing")
if dropped:
    print(f"dropped {len(dropped)} duplicate positions (same FEN as an existing puzzle):")
    for i, src, keeper in dropped:
        print(f"    {src}:{i} -> already present as {keeper}")
print("\nNow run: python3 build.py   (re-embeds the fallback into index.html -> worker.js)")

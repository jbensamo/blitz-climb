#!/usr/bin/env python3
"""Diagnose WHICH themes the owner actually loses points to, so training can be
prescribed against them instead of picked generically.

For every move where he lost significant evaluation, this records two things:

  missed   — the theme of the move the engine wanted (the win he didn't see)
  allowed  — the theme of the opponent's best reply to what he actually played
             (the punishment he didn't see coming — the C.C.T. failure)

plus the phase and, in endgames, the material type (rook / pawn / minor / queen).

Themes are named to match the Lichess puzzle database's tags, so the prescription
step can look them up directly.

    python3 tools/diagnose.py data/games/blitz_60.pgn data/games/rapid_60.pgn
    -> data/diagnosis.json
"""
import json, math, os, sys
from collections import Counter
import chess, chess.pgn, chess.engine

ENGINE = os.environ.get("ENGINE", "/usr/games/stockfish")
USER = os.environ.get("USER_NAME", "jbensamo")
SCAN_DEPTH = int(os.environ.get("SCAN_DEPTH", 12))
CLASS_DEPTH = int(os.environ.get("CLASS_DEPTH", 14))
DROP = float(os.environ.get("DROP", 12))          # win% lost to count as an error
OUT = os.environ.get("OUT", "data/diagnosis.json")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

VAL = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}

def winpct(cp): return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)

def phase_of(board):
    npm = sum(VAL[p.piece_type] for p in board.piece_map().values()
              if p.piece_type not in (chess.PAWN, chess.KING))
    if board.fullmove_number <= 12: return "opening"
    return "endgame" if npm <= 16 else "middlegame"

def endgame_type(board):
    """Material signature, using Lichess's endgame tag names."""
    kinds = set()
    for p in board.piece_map().values():
        if p.piece_type in (chess.PAWN, chess.KING): continue
        kinds.add(p.piece_type)
    if kinds == {chess.ROOK}:   return "rookEndgame"
    if not kinds:               return "pawnEndgame"
    if kinds == {chess.QUEEN}:  return "queenEndgame"
    if kinds <= {chess.BISHOP}: return "bishopEndgame"
    if kinds <= {chess.KNIGHT}: return "knightEndgame"
    if kinds <= {chess.BISHOP, chess.KNIGHT}: return "minorEndgame"
    return None

def attacked_valuable(board, sq, by_color):
    """Enemy pieces (>= knight, or the king) the piece on `sq` now hits."""
    out = []
    for t in board.attacks(sq):
        pc = board.piece_at(t)
        if pc and pc.color != by_color and (VAL[pc.piece_type] >= 3 or pc.piece_type == chess.KING):
            out.append(pc.piece_type)
    return out

def defended(board, sq, by_color):
    """Is the piece on sq defended by its own side?"""
    return bool(board.attackers(by_color, sq))

def classify(board, move):
    """Name the tactical theme of `move` in `board`, using Lichess tag vocabulary."""
    themes = []
    mover = board.turn
    victim = board.piece_at(move.to_square)
    b2 = board.copy(); b2.push(move)

    # Mate dominates: if it's mate, that IS the theme. Collecting extra tags here
    # skewed the counts (Qxf7# was also being logged as a fork and a skewer).
    if b2.is_checkmate():
        return ["mate"]
    # promotion
    if move.promotion or (board.piece_at(move.from_square)
                          and board.piece_at(move.from_square).piece_type == chess.PAWN
                          and chess.square_rank(move.to_square) in (6, 1)):
        themes.append("advancedPawn")
    # a free piece just sitting there
    if victim and VAL[victim.piece_type] >= 3 and not defended(board, move.to_square, not mover):
        themes.append("hangingPiece")
    # fork: the piece that moved now hits two valuable things
    hits = attacked_valuable(b2, move.to_square, mover)
    if len(hits) >= 2:
        themes.append("fork")
    # discovered attack: a friendly slider gained a target through the vacated square
    for sq, pc in b2.piece_map().items():
        if pc.color != mover or pc.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
            continue
        if sq == move.to_square:
            continue
        before = set(board.attacks(sq)) if board.piece_at(sq) else set()
        gained = set(b2.attacks(sq)) - before
        for t in gained:
            tp = b2.piece_at(t)
            if tp and tp.color != mover and (VAL[tp.piece_type] >= 3 or tp.piece_type == chess.KING):
                themes.append("discoveredAttack"); break
        if "discoveredAttack" in themes: break
    # pin / skewer: a slider lines up two enemy pieces
    if board.piece_at(move.from_square) and board.piece_at(move.from_square).piece_type in (
            chess.BISHOP, chess.ROOK, chess.QUEEN):
        for t in b2.attacks(move.to_square):
            tp = b2.piece_at(t)
            if not tp or tp.color == mover: continue
            between = chess.SquareSet(chess.ray(move.to_square, t)) - chess.SquareSet(
                chess.between(move.to_square, t)) - {move.to_square, t}
            for beyond in between:
                bp = b2.piece_at(beyond)
                if bp and bp.color != mover:
                    themes.append("skewer" if VAL[tp.piece_type] >= VAL[bp.piece_type] else "pin")
                    break
            if "pin" in themes or "skewer" in themes: break
    # sacrifice that still wins -> deflection family
    if victim is None and board.is_capture(move) is False:
        moved = board.piece_at(move.from_square)
        if moved and b2.attackers(not mover, move.to_square) and VAL[moved.piece_type] >= 3:
            themes.append("sacrifice")
    if not themes:
        if board.gives_check(move):     themes.append("check")
        elif board.is_capture(move):    themes.append("capture")
        else:                           themes.append("quietMove")
    # Keep the two most specific tags; more than that just dilutes the diagnosis.
    return themes[:2]

def main(paths):
    eng = chess.engine.SimpleEngine.popen_uci(ENGINE)
    eng.configure({"Threads": 2, "Hash": 256})
    missed, allowed, phases, endtypes = Counter(), Counter(), Counter(), Counter()
    errors = 0; moves_seen = 0; examples = []

    for path in paths:
        fh = open(path, encoding="utf-8", errors="replace")
        while True:
            g = chess.pgn.read_game(fh)
            if not g: break
            w = g.headers.get("White", "").lower(); b = g.headers.get("Black", "").lower()
            if USER == w:   uc = chess.WHITE
            elif USER == b: uc = chess.BLACK
            else: continue
            url = g.headers.get("Site", "")
            board = g.board()
            prev = eng.analyse(board, chess.engine.Limit(depth=SCAN_DEPTH))
            prev_w = prev["score"].white().score(mate_score=100000)
            for mv in g.mainline_moves():
                mover = board.turn; fen = board.fen(); movno = board.fullmove_number
                pos = board.copy()
                board.push(mv)
                cur = eng.analyse(board, chess.engine.Limit(depth=SCAN_DEPTH))
                cur_w = cur["score"].white().score(mate_score=100000)
                if mover == uc:
                    moves_seen += 1
                    before = prev_w if uc == chess.WHITE else -prev_w
                    after  = cur_w  if uc == chess.WHITE else -cur_w
                    lost = winpct(before) - winpct(after)
                    if lost >= DROP:
                        errors += 1
                        ph = phase_of(pos); phases[ph] += 1
                        if ph == "endgame":
                            et = endgame_type(pos)
                            if et: endtypes[et] += 1
                        # what he should have played
                        try:
                            best = eng.analyse(pos, chess.engine.Limit(depth=CLASS_DEPTH))["pv"][0]
                            for t in classify(pos, best): missed[t] += 1
                        except Exception: pass
                        # what the opponent got to play in reply
                        try:
                            punish = eng.analyse(board, chess.engine.Limit(depth=CLASS_DEPTH))["pv"][0]
                            for t in classify(board, punish): allowed[t] += 1
                        except Exception: pass
                        if len(examples) < 25:
                            examples.append({"fen": fen, "url": url, "move": movno,
                                             "lost": round(lost, 1), "phase": ph})
                prev_w = cur_w
    eng.quit()

    out = {
        "generated": None,
        "gamesFrom": paths,
        "movesByHim": moves_seen,
        "errors": errors,
        "errorRate": round(errors / max(1, moves_seen), 4),
        "missed": dict(missed.most_common()),
        "allowed": dict(allowed.most_common()),
        "phases": dict(phases.most_common()),
        "endgameTypes": dict(endtypes.most_common()),
        "examples": examples,
    }
    json.dump(out, open(OUT, "w"), indent=1)
    print(f"{errors} errors across {moves_seen} of his moves ({100*errors/max(1,moves_seen):.1f}%)\n")
    print("MISSED (the wins he didn't see):")
    for t, c in missed.most_common(12): print(f"   {c:4d}  {t}")
    print("\nALLOWED (what punished him — the C.C.T. failures):")
    for t, c in allowed.most_common(12): print(f"   {c:4d}  {t}")
    print("\nPHASE:", dict(phases), "\nENDGAME TYPES:", dict(endtypes))
    print(f"\n-> {OUT}")

if __name__ == "__main__":
    main(sys.argv[1:] or ["data/games/blitz_60.pgn", "data/games/rapid_60.pgn"])

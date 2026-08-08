#!/usr/bin/env python3
"""Build the "Endgame theory" module: king-and-pawn positions with an ONLY move.

Rather than typing famous FENs from memory (and risking shipping wrong chess), this
searches the K+P vs K space and keeps positions where the result actually hinges on
the move — best move wins and every alternative draws, or best move draws and every
alternative loses. Those are precisely the opposition / key-square / square-of-the-pawn
lessons, and every one is certified by the engine rather than by recall.

With three pieces Stockfish is effectively exact, so "winning" vs "drawn" is reliable.

    python3 tools/gen_endgame_theory.py        # writes build/sets/endtheory.json
"""
import json, os, random, sys
import chess, chess.engine

ENGINE = os.environ.get("ENGINE", "/usr/games/stockfish")
OUT = os.environ.get("OUT", "build/sets/endtheory.json")
ID_PREFIX = os.environ.get("ID_PREFIX", "et")
MAX_ITEMS = int(os.environ.get("MAX_ITEMS", 12))
DEPTH = int(os.environ.get("DEPTH", 24))
SEED = int(os.environ.get("SEED", 7))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
random.seed(SEED)

WIN, DRAW = "win", "draw"

def klass(cp, mate):
    """Coarse result class from White's point of view."""
    if mate is not None:
        return WIN if mate > 0 else "loss"
    if cp >= 150:  return WIN
    if cp <= -150: return "loss"
    return DRAW

def describe(board, move):
    """Name the lesson from the position itself, never from memory."""
    b = board.copy(); b.push(move)
    wk, bk = b.king(chess.WHITE), b.king(chess.BLACK)
    pawn = [s for s, p in b.piece_map().items() if p.piece_type == chess.PAWN]
    fd = abs(chess.square_file(wk) - chess.square_file(bk))
    rd = abs(chess.square_rank(wk) - chess.square_rank(bk))
    if (fd, rd) in ((0, 2), (2, 0), (2, 2)):
        return "Opposition", "Kings facing each other with one square between: whoever must move gives way."
    # Only claim "square of the pawn" when the move actually pushed the pawn — the
    # label must be true, not merely plausible.
    if pawn and b.piece_at(pawn[0]) and move.to_square == pawn[0]:
        ps = pawn[0]
        prank = chess.square_rank(ps)
        defender = bk if b.piece_at(ps).color == chess.WHITE else wk
        promo_rank = 7 if b.piece_at(ps).color == chess.WHITE else 0
        dist = max(abs(chess.square_file(defender) - chess.square_file(ps)),
                   abs(chess.square_rank(defender) - promo_rank))
        if dist >= abs(promo_rank - prank):
            return "Square of the pawn", "Can the king catch the runner? Count the square, don't guess."
    return "Only move", "Everything else here throws the result away — find the one that doesn't."

def random_kpk():
    """A legal K+P vs K position, White to move, pawn advanced enough to matter."""
    for _ in range(400):
        pf = random.randint(0, 7); pr = random.randint(2, 5)      # ranks 3-6
        ps = chess.square(pf, pr)
        wk = chess.square(random.randint(0, 7), random.randint(0, 7))
        bk = chess.square(random.randint(0, 7), random.randint(0, 7))
        if len({ps, wk, bk}) < 3: continue
        if chess.square_distance(wk, bk) < 2: continue
        b = chess.Board(None)
        b.set_piece_at(wk, chess.Piece(chess.KING, chess.WHITE))
        b.set_piece_at(bk, chess.Piece(chess.KING, chess.BLACK))
        b.set_piece_at(ps, chess.Piece(chess.PAWN, chess.WHITE))
        b.turn = chess.WHITE
        b.fullmove_number = 40
        if not b.is_valid(): continue
        if b.is_check(): continue
        if len(list(b.legal_moves)) < 3: continue
        return b
    return None

eng = chess.engine.SimpleEngine.popen_uci(ENGINE)
eng.configure({"Threads": 2, "Hash": 128})

items, tried, seen = [], 0, set()
while len(items) < MAX_ITEMS and tried < 4000:
    tried += 1
    b = random_kpk()
    if b is None or b.fen() in seen: continue
    seen.add(b.fen())

    infos = eng.analyse(b, chess.engine.Limit(depth=DEPTH), multipv=3)
    if isinstance(infos, dict): infos = [infos]
    if len(infos) < 2: continue
    best = infos[0]["pv"][0]
    k1 = klass(infos[0]["score"].white().score(), infos[0]["score"].white().mate())
    k2 = klass(infos[1]["score"].white().score(), infos[1]["score"].white().mate())
    # The lesson only exists if the SECOND-best move throws the result away.
    if not ((k1 == WIN and k2 == DRAW) or (k1 == DRAW and k2 == "loss")):
        continue

    name, note = describe(b, best)
    # Build a short line: user move, engine reply, user move.
    line, cur, user_moves = [], b.copy(), 0
    while user_moves < 2 and len(line) < 4:
        inf = eng.analyse(cur, chess.engine.Limit(depth=DEPTH), multipv=2)
        if isinstance(inf, dict): inf = [inf]
        mv = inf[0]["pv"][0]
        is_user = (cur.turn == chess.WHITE)
        if is_user and user_moves >= 1:
            # only continue if this second user move is also forced
            a = klass(inf[0]["score"].white().score(), inf[0]["score"].white().mate())
            c = klass(inf[1]["score"].white().score(), inf[1]["score"].white().mate()) if len(inf) > 1 else None
            if not (c and a != c): break
        san = cur.san(mv)
        frm, to = chess.square_name(mv.from_square), chess.square_name(mv.to_square)
        cur.push(mv)
        line.append({"uci": mv.uci(), "from": frm, "to": to, "san": san, "fen": cur.fen(),
                     "user": is_user, "promo": (mv.promotion and chess.piece_symbol(mv.promotion)) or None})
        if is_user: user_moves += 1
        if cur.is_game_over(): break
    while line and not line[-1]["user"]:
        line.pop()
    if not line or not line[0]["user"]:
        continue

    verdict = "wins" if k1 == WIN else "holds the draw"
    items.append({
        "id": f"{ID_PREFIX}{len(items)+1}",
        "kind": "line", "cat": "endtheory", "phase": "endgame",
        "fen": b.fen(), "sideToMove": "w", "userColor": "w",
        "line": line,
        "motif": name,
        "youPlayed": "—",
        "sourceUrl": "",
        "moveNo": b.fullmove_number,
        "explain": f"{note} {line[0]['san']} {verdict}; every other move throws it away.",
    })
    print(f"  {items[-1]['id']}: {name:20s} {line[0]['san']:6s} {verdict}  ({b.fen()})", flush=True)

eng.quit()
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(items, open(OUT, "w"), indent=1)
print(f"\nBUILT {len(items)} endgame-theory positions from {tried} tried -> {OUT}")

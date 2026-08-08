#!/usr/bin/env python3
"""Build the "Your repertoire" module from the owner's own most-played openings.

Not book theory — his actual lines, so the drill reinforces what he already reaches
over the board. Each of HIS moves in the line is engine-checked; a line is cut short
at the first move that loses more than MAX_LOSS centipawns, so he never drills a
mistake. Stops at move ~8, as the plan says.

    python3 tools/gen_openings.py data/games/blitz_60.pgn data/games/rapid_60.pgn
"""
import json, os, sys
from collections import defaultdict
import chess, chess.pgn, chess.engine

ENGINE = os.environ.get("ENGINE", "/usr/games/stockfish")
USER = os.environ.get("USER_NAME", "jbensamo")
OUT = os.environ.get("OUT", "build/sets/openings.json")
ID_PREFIX = os.environ.get("ID_PREFIX", "o")
MAX_PLY = int(os.environ.get("MAX_PLY", 16))     # 16 plies = through move 8
MIN_GAMES = int(os.environ.get("MIN_GAMES", 3))  # a "line" needs this many games
MAX_LOSS = int(os.environ.get("MAX_LOSS", 70))   # cp; cut the line before a real mistake
DEPTH = int(os.environ.get("DEPTH", 16))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

# ---- collect his games, keyed by the colour he had -------------------------------
games = {chess.WHITE: [], chess.BLACK: []}
names = {chess.WHITE: defaultdict(int), chess.BLACK: defaultdict(int)}
for path in sys.argv[1:] or ["data/games/blitz_60.pgn", "data/games/rapid_60.pgn"]:
    fh = open(path, encoding="utf-8", errors="replace")
    while True:
        g = chess.pgn.read_game(fh)
        if not g: break
        w = g.headers.get("White", "").lower(); b = g.headers.get("Black", "").lower()
        if USER == w:   uc = chess.WHITE
        elif USER == b: uc = chess.BLACK
        else: continue
        plies = [m.uci() for m in g.mainline_moves()][:MAX_PLY]
        if len(plies) < 6: continue
        games[uc].append(plies)
        names[uc][g.headers.get("Opening", "?")] += 1

def most_travelled(seqs):
    """Walk the most common path while at least MIN_GAMES games still follow it."""
    line, pool = [], list(seqs)
    while len(line) < MAX_PLY:
        nxt = defaultdict(int)
        for s in pool:
            if len(s) > len(line): nxt[s[len(line)]] += 1
        if not nxt: break
        mv, n = max(nxt.items(), key=lambda kv: kv[1])
        if n < MIN_GAMES: break
        line.append(mv)
        pool = [s for s in pool if len(s) > len(line) - 1 and s[len(line) - 1] == mv]
    return line, len(pool)

eng = chess.engine.SimpleEngine.popen_uci(ENGINE)
eng.configure({"Threads": 2, "Hash": 128})

items = []
for uc in (chess.WHITE, chess.BLACK):
    seqs = games[uc]
    if not seqs:
        print(f"no games as {'White' if uc==chess.WHITE else 'Black'}");  continue
    ucis, n = most_travelled(seqs)
    if len(ucis) < 4:
        print(f"no line with >= {MIN_GAMES} games as {'White' if uc==chess.WHITE else 'Black'}");  continue
    label = max(names[uc].items(), key=lambda kv: kv[1])[0]

    board = chess.Board(); line = []; cut = None
    for i, u in enumerate(ucis):
        mv = chess.Move.from_uci(u)
        if mv not in board.legal_moves: cut = "illegal"; break
        is_user = (board.turn == uc)
        if is_user:
            # engine-check HIS move only; a bad one ends the line rather than being drilled
            info = eng.analyse(board, chess.engine.Limit(depth=DEPTH))
            best_cp = info["score"].pov(board.turn).score(mate_score=100000)
            after = board.copy(); after.push(mv)
            info2 = eng.analyse(after, chess.engine.Limit(depth=DEPTH))
            got_cp = info2["score"].pov(board.turn).score(mate_score=100000)
            if best_cp is not None and got_cp is not None and (best_cp - got_cp) > MAX_LOSS:
                cut = f"his move {board.san(mv)} loses {best_cp-got_cp}cp"
                break
        san = board.san(mv)
        frm, to = chess.square_name(mv.from_square), chess.square_name(mv.to_square)
        board.push(mv)
        line.append({"uci": u, "from": frm, "to": to, "san": san, "fen": board.fen(),
                     "user": is_user, "promo": (mv.promotion and chess.piece_symbol(mv.promotion)) or None})
    while line and not line[-1]["user"]:
        line.pop()
    # The trainer asks the user to play line[0], so the line MUST open on his move.
    # As Black the sequence starts with White's move, so replay the leading opponent
    # plies into the starting position instead of asking him to play them.
    start_fen = chess.Board().fen()
    lead = 0
    while lead < len(line) and not line[lead]["user"]:
        start_fen = line[lead]["fen"]; lead += 1
    line = line[lead:]
    if len(line) < 4:
        print(f"line too short as {'White' if uc==chess.WHITE else 'Black'} ({cut})");  continue

    colour = "White" if uc == chess.WHITE else "Black"
    moves_txt = " ".join(s["san"] for s in line)
    items.append({
        "id": f"{ID_PREFIX}{len(items)+1}",
        "kind": "line", "cat": "opening", "phase": "opening",
        "fen": start_fen,
        "sideToMove": "w" if chess.Board(start_fen).turn == chess.WHITE else "b",
        "userColor": "w" if uc == chess.WHITE else "b",
        "line": line,
        "motif": f"{colour}: {label}",
        "youPlayed": "—", "sourceUrl": "", "moveNo": 1,
        "explain": (f"Your most-played line as {colour} ({label}), from {n} of your games — "
                    f"every move engine-checked to within {MAX_LOSS}cp. {moves_txt}"
                    + (f" (Line stops here: {cut}.)" if cut else "")),
    })
    print(f"  {items[-1]['id']}: {colour:5s} {label:42s} {len(line)} plies, {n} games"
          + (f"  [cut: {cut}]" if cut else ""))

eng.quit()
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(items, open(OUT, "w"), indent=1)
print(f"\nBUILT {len(items)} repertoire lines -> {OUT}")

#!/usr/bin/env python3
"""Build engine-verified tactics puzzles from jbensamo's own games.
A puzzle = a position where the user was to move, had a clearly-best winning move,
and played something worse. Solution line verified with Stockfish multipv."""
import sys, math, json, time
from collections import defaultdict
import chess, chess.pgn, chess.engine

import os
# All tunables are env-overridable so one script can build several sets
# (tactics / endgames, blitz / rapid) without forking it.
ENGINE=os.environ.get("ENGINE","/usr/games/stockfish"); USER="jbensamo"
SCAN_DEPTH=int(os.environ.get("SCAN_DEPTH",12))     # candidate detection
VERIFY_DEPTH=int(os.environ.get("VERIFY_DEPTH",15)) # solution verification
MAX_PUZZLES=int(os.environ.get("MAX_PUZZLES",18))
MAX_PER_GAME=int(os.environ.get("MAX_PER_GAME",3))
WALL=int(os.environ.get("WALL",470))
OUT=os.environ.get("OUT","puzzles.json")
CACHE=os.environ.get("CACHE","candidates.json")
ID_PREFIX=os.environ.get("ID_PREFIX","p")
CAT=os.environ.get("CAT","tactics")                 # puzzle set the app groups by
PHASE_ONLY=os.environ.get("PHASE_ONLY","")          # "" = any, or "endgame"/"middlegame"/"opening"
QUIET_ONLY=os.environ.get("QUIET_ONLY","")          # keep only positions whose best move is
                                                    # neither a capture nor a check (strategy)
EXCLUDE=os.environ.get("EXCLUDE","")                # a puzzles.json whose FENs to skip, so a
                                                    # new set is guaranteed new positions

def phase(board):
    """Same definition analyze.py uses, so 'endgame' here matches the baseline stats."""
    npm=sum({chess.PAWN:1,chess.KNIGHT:3,chess.BISHOP:3,chess.ROOK:5,chess.QUEEN:9,chess.KING:0}[p.piece_type]
            for p in board.piece_map().values() if p.piece_type not in (chess.PAWN,chess.KING))
    if board.fullmove_number<=12: return "opening"
    return "endgame" if npm<=16 else "middlegame"

def winpct(cp): return 50+50*(2/(1+math.exp(-0.00368208*cp))-1)
def povcp(info, pov):   # side-to-move-agnostic: return cp from `pov` color
    sc=info["score"].pov(pov)
    return sc.score(mate_score=100000)

def motif(board_before, sol_line):
    """Rough label from the first solution move & outcome."""
    first=sol_line[0]
    b=board_before.copy()
    fm=chess.Move.from_uci(first["uci"])
    is_cap = board_before.is_capture(fm)
    tmp=board_before.copy()
    matein=None
    for i,ply in enumerate(sol_line):
        tmp.push(chess.Move.from_uci(ply["uci"]))
        if tmp.is_checkmate():
            matein=(i//2)+1; break
    if matein: return f"Mate in {matein}"
    if is_cap: return "Win material"
    if board_before.gives_check(fm): return "Forcing tactic"
    return "Best move"

def main(path):
    games=[]
    with open(path,encoding="utf-8",errors="replace") as fh:
        while True:
            g=chess.pgn.read_game(fh)
            if not g: break
            games.append(g)
    eng=chess.engine.SimpleEngine.popen_uci(ENGINE)
    eng.configure({"Threads":2,"Hash":256})
    t0=time.time()

    if os.path.exists(CACHE):
        candidates=[tuple(c) for c in json.load(open(CACHE))]
        print(f"loaded {len(candidates)} cached candidates", flush=True)
    else:
        candidates=[]  # (drop, gi, fen, uc 'w'/'b', played_uci, url, movno, phase)
        for gi,g in enumerate(games):
            w=g.headers.get("White","").lower(); b=g.headers.get("Black","").lower()
            if USER==w: uc=chess.WHITE
            elif USER==b: uc=chess.BLACK
            else: continue
            url=g.headers.get("Site",""); board=g.board()
            prev=eng.analyse(board, chess.engine.Limit(depth=SCAN_DEPTH))
            prev_w=prev["score"].white().score(mate_score=100000)
            for mv in g.mainline_moves():
                mover=board.turn; movno=board.fullmove_number; fen=board.fen(); played=mv
                board.push(mv)
                cur=eng.analyse(board, chess.engine.Limit(depth=SCAN_DEPTH))
                cur_w=cur["score"].white().score(mate_score=100000)
                if mover==uc:
                    before = prev_w if uc==chess.WHITE else -prev_w
                    after  = cur_w  if uc==chess.WHITE else -cur_w
                    drop=winpct(before)-winpct(after)
                    if drop>=18 and before>=60:
                        ph=phase(chess.Board(fen))
                        if not PHASE_ONLY or ph==PHASE_ONLY:
                            candidates.append([drop, gi, fen, "w" if uc==chess.WHITE else "b", played.uci(), url, movno, ph])
                prev_w=cur_w
        json.dump(candidates, open(CACHE,"w"))
        print(f"candidates: {len(candidates)} ({int(time.time()-t0)}s) [cached]", flush=True)

    skip_fens=set()
    if EXCLUDE and os.path.exists(EXCLUDE):
        skip_fens={q["fen"] for q in json.load(open(EXCLUDE))}
        print(f"excluding {len(skip_fens)} positions already in {EXCLUDE}", flush=True)

    candidates.sort(reverse=True, key=lambda c:c[0])
    puzzles=[]; per_game=defaultdict(int)
    for drop, gi, fen, uc_s, played_uci, url, movno, ph in candidates:
        uc = chess.WHITE if uc_s=="w" else chess.BLACK
        played = chess.Move.from_uci(played_uci)
        if len(puzzles)>=MAX_PUZZLES: break
        if per_game[gi]>=MAX_PER_GAME: continue
        if fen in skip_fens: continue
        if time.time()-t0>WALL: break
        board=chess.Board(fen)
        # verify + build solution line (<=2 user moves)
        line=[]; cur=board.copy(); user_moves=0; ok=True; plies=0
        first_gain=None
        while user_moves<2 and plies<5:
            infos=eng.analyse(cur, chess.engine.Limit(depth=VERIFY_DEPTH), multipv=2)
            if isinstance(infos,dict): infos=[infos]
            best=infos[0]["pv"][0]
            e1=povcp(infos[0], cur.turn)
            e2=povcp(infos[1], cur.turn) if len(infos)>1 else -100000
            is_user = (cur.turn==uc)
            if is_user:
                gap=e1-e2
                unique = gap>=120 or (abs(e1)>=90000 and abs(e2)<90000)
                if user_moves==0:
                    # first move must be clearly winning to make a satisfying puzzle
                    if not (e1>=150 or e1>=90000): ok=False; break
                    first_gain=e1
                if not unique:
                    break  # truncate line here (still valid if we already have >=1 user move)
            frm=chess.square_name(best.from_square); to=chess.square_name(best.to_square)
            san=cur.san(best)
            cur.push(best)
            line.append({"uci":best.uci(),"from":frm,"to":to,"san":san,
                         "fen":cur.fen(),"user":is_user,
                         "promo":(best.promotion and chess.piece_symbol(best.promotion)) or None})
            if is_user: user_moves+=1
            plies+=1
            if cur.is_game_over(): break
        # need at least one user move and a good first move
        if not ok or user_moves<1 or not line or not line[0]["user"]:
            continue
        # trim trailing opponent move (line should end after a user move for clean solve)
        while line and not line[-1]["user"]:
            line.pop()
        if not line: continue
        # Strategy set: the lesson is a quiet improving move, so drop anything that
        # wins by force — those belong in the tactics set.
        if QUIET_ONLY:
            b0=chess.Board(fen); fm=chess.Move.from_uci(line[0]["uci"])
            if b0.is_capture(fm) or b0.gives_check(fm): continue
        played_san = chess.Board(fen).san(played)
        mtf = motif(chess.Board(fen), line)
        gain_txt = ("forces mate" if first_gain and first_gain>=90000
                    else f"gains about +{first_gain/100:.1f}")
        puzzles.append({
            "id": f"{ID_PREFIX}{len(puzzles)+1}",
            "fen": fen,
            "sideToMove": "w" if board.turn==chess.WHITE else "b",
            "userColor": "w" if uc==chess.WHITE else "b",
            "line": line,
            "motif": mtf,
            "cat": CAT,
            "phase": ph,
            "youPlayed": played_san,
            "sourceUrl": url,
            "moveNo": movno,
            "explain": f"You played {played_san}. The engine's {line[0]['san']} {gain_txt}."
        })
        per_game[gi]+=1
    eng.quit()
    with open(OUT,"w") as f:
        json.dump(puzzles, f, indent=1)
    print(f"\nBUILT {len(puzzles)} {CAT} puzzles -> {OUT} in {int(time.time()-t0)}s")
    for p in puzzles:
        umoves=[s['san'] for s in p['line'] if s['user']]
        print(f"  {p['id']}: {p['sideToMove']} to move | {p['motif']:16s} | sol {umoves} | you played {p['youPlayed']} | {p['sourceUrl']} m{p['moveNo']}")

if __name__=="__main__":
    main(sys.argv[1])

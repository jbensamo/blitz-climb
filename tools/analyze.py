#!/usr/bin/env python3
import sys, time, math, json
from collections import Counter, defaultdict
import chess, chess.pgn, chess.engine

ENGINE="/usr/games/stockfish"
USER="jbensamo"
DEPTH=12
WALL_BUDGET=520  # seconds hard cap

def winpct(cp):  # from side-to-move POV, Lichess formula
    return 50 + 50*(2/(1+math.exp(-0.00368208*cp)) - 1)

def phase(board):
    npm=sum({chess.PAWN:1,chess.KNIGHT:3,chess.BISHOP:3,chess.ROOK:5,chess.QUEEN:9,chess.KING:0}[p.piece_type]
            for p in board.piece_map().values() if p.piece_type not in (chess.PAWN,chess.KING))
    if board.fullmove_number<=12: return "opening"
    return "endgame" if npm<=16 else "middlegame"

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
    per_move_losses=[]          # capped cp losses (player moves)
    cat=Counter()               # inaccuracy/mistake/blunder
    blunder_phase=Counter()
    by_color_loss=defaultdict(list)
    blunders=[]                 # (wpdrop, url, movno, phase, played, best, result, color)
    games_done=0
    for g in games:
        w=g.headers.get("White",""); b=g.headers.get("Black","")
        if w.lower()==USER: color=chess.WHITE
        elif b.lower()==USER: color=chess.BLACK
        else: continue
        url=g.headers.get("Site",""); r=g.headers.get("Result")
        out = "win" if ((r=="1-0")==(color==chess.WHITE) and r in("1-0","0-1")) else ("draw" if r=="1/2-1/2" else "loss")

        board=g.board()
        # eval every position (before each move) from white POV, plus best move for side to move
        moves=list(g.mainline_moves())
        # analyse position, return (white_cp, bestmove)
        def ev(bd):
            info=eng.analyse(bd, chess.engine.Limit(depth=DEPTH))
            sc=info["score"].white().score(mate_score=100000)
            bm=info["pv"][0] if info.get("pv") else None
            return sc, bm
        prev_cp, prev_best = ev(board)
        for mv in moves:
            mover=board.turn
            played_san=board.san(mv)
            best_san=board.san(prev_best) if prev_best else "?"
            movno=board.fullmove_number
            ph=phase(board)
            board.push(mv)
            cur_cp, cur_best = ev(board)
            if mover==color:
                # win% from mover POV before vs after
                before_cp = prev_cp if color==chess.WHITE else -prev_cp
                after_cp  = cur_cp  if color==chess.WHITE else -cur_cp
                wp_before=winpct(before_cp); wp_after=winpct(after_cp)
                drop=max(0.0, wp_before-wp_after)          # win% points lost
                cploss=max(0, min(1000, before_cp-after_cp))  # capped cp
                per_move_losses.append(cploss)
                by_color_loss["White" if color==chess.WHITE else "Black"].append(cploss)
                if drop>=30: cat["blunder"]+=1; blunder_phase[ph]+=1
                elif drop>=20: cat["mistake"]+=1
                elif drop>=10: cat["inaccuracy"]+=1
                if drop>=25:
                    blunders.append((round(drop,1),url,movno,ph,played_san,best_san,out,
                                     "W" if color==chess.WHITE else "B"))
            prev_cp, prev_best = cur_cp, cur_best
        games_done+=1
        if games_done%5==0 or time.time()-t0>WALL_BUDGET:
            print(f"...{games_done} games, {int(time.time()-t0)}s", flush=True)
        if time.time()-t0>WALL_BUDGET:
            print("WALL BUDGET hit, stopping early", flush=True); break
    eng.quit()

    n=games_done
    acpl=sum(per_move_losses)/len(per_move_losses) if per_move_losses else 0
    print("\n===== ENGINE ANALYSIS (Stockfish 16, depth %d) =====" % DEPTH)
    print(f"Games analyzed: {n}   | player moves scored: {len(per_move_losses)}")
    print(f"AVERAGE CENTIPAWN LOSS (ACPL): {acpl:.0f} cp")
    for c in ("White","Black"):
        L=by_color_loss[c]
        if L: print(f"   {c}: ACPL {sum(L)/len(L):.0f} over {len(L)} moves")
    tot=len(per_move_losses) or 1
    print(f"Inaccuracies: {cat['inaccuracy']}  ({cat['inaccuracy']/n:.1f}/game)")
    print(f"Mistakes:     {cat['mistake']}  ({cat['mistake']/n:.1f}/game)")
    print(f"BLUNDERS:     {cat['blunder']}  ({cat['blunder']/n:.2f}/game)")
    tb=sum(blunder_phase.values()) or 1
    print("Blunder phase: "+", ".join(f"{p} {blunder_phase[p]} ({100*blunder_phase[p]/tb:.0f}%)"
                                      for p in ('opening','middlegame','endgame')))
    blunders.sort(reverse=True)
    print("\nTOP 10 ENGINE BLUNDERS (win% lost | game | move | played -> best):")
    for drop,url,mn,ph,played,best,out,col in blunders[:10]:
        print(f"  -{drop:>4}%  {url}  move {mn} ({col},{ph},{out})  played {played}, best {best}")
    # save json
    with open("engine_results.json","w") as f:
        json.dump({"n":n,"acpl":acpl,"cat":dict(cat),"blunder_phase":dict(blunder_phase),
                   "blunders":blunders[:15]}, f, indent=2)
    print("\nsaved engine_results.json")

if __name__=="__main__":
    main(sys.argv[1])

# Working on this repo (agent notes)

- The app is ONE self-contained `index.html`. Do not add a framework/bundler.
- After editing `index.html`, run `python3 build.py` to re-inline it into `worker.js`,
  then `npx wrangler deploy`.
- Puzzles are engine-verified positions from the user's own games. Schema per puzzle:
  `{id, fen, sideToMove, userColor, line:[{uci,from,to,san,fen,user,promo}], motif,
   youPlayed, sourceUrl, moveNo, explain}`. Only the engine's move is accepted.
- Progress schema (KV `state:<code>` / localStorage `chessTrainer_v5`):
  `{version, player, checks, habitDays, sessions:[{date,acpl,blunders,note}],
    puzzles:{solved,attempts,firstTry,byDay}, updated}`.
- Baseline (Stockfish 16, 60 blitz games, 2026-08): ACPL 55, blunders 0.65/game,
  mistakes 0.7, inaccuracies 2.3; blunders 59% middlegame / 26% endgame / 15% opening.
- Keep the C.C.T. (Checks-Captures-Threats) habit central; endgames are a real 2nd front.

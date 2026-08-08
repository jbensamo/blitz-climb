#!/usr/bin/env bash
# Build the puzzle sets the Train tab groups by. Each set gets its own id prefix so
# progress keys never collide, and its own candidate cache so runs don't poison
# each other. Stockfish path is overridable (brew puts it somewhere else than apt).
set -u
cd "$(dirname "$0")/.."
ENGINE="${ENGINE:-$(command -v stockfish || echo /usr/games/stockfish)}"
export ENGINE
OUTDIR=build/sets
mkdir -p "$OUTDIR"

echo "engine: $ENGINE"

# 1) Endgame drills — 26% of the owner's blunders, and the weakest front after tactics.
#    Scans both blitz and rapid so there's a big enough endgame pool to draw from.
for src in blitz rapid; do
  echo "=== endgame candidates from ${src}_60.pgn ==="
  CACHE="$OUTDIR/cand_end_${src}.json" OUT="$OUTDIR/end_${src}.json" \
  ID_PREFIX="e${src:0:1}" CAT=endgame PHASE_ONLY=endgame \
  MAX_PUZZLES=12 MAX_PER_GAME=2 WALL=900 \
  python3 tools/generate_puzzles.py "data/games/${src}_60.pgn" || echo "  (failed: $src endgames)"
done

# 2) Extra tactics from the rapid games — same leak, positions not yet seen.
echo "=== tactics candidates from rapid_60.pgn ==="
CACHE="$OUTDIR/cand_tac_rapid.json" OUT="$OUTDIR/tac_rapid.json" \
ID_PREFIX=r CAT=tactics \
MAX_PUZZLES=20 MAX_PER_GAME=2 WALL=900 \
python3 tools/generate_puzzles.py data/games/rapid_60.pgn || echo "  (failed: rapid tactics)"

echo "=== done ==="
ls -la "$OUTDIR"

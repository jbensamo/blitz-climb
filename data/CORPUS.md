# Where the graded curriculum comes from

The 648 puzzles under `puzzles/` are built from the **Lichess puzzle database**.

- Source: <https://database.lichess.org/#puzzles> (`lichess_db_puzzle.csv.zst`)
- Dump used: `last-modified: Sun, 02 Aug 2026 07:23:55 GMT` (~305 MB compressed, ~5M puzzles)
- Licence: **CC0 1.0 Universal (public domain dedication)** — no attribution required.
  Credited here anyway, because knowing the provenance of the data matters.
- Rebuild: `zstd -dc build/corpus/lichess_db_puzzle.csv.zst | python3 tools/build_corpus.py`
  (the `.zst` dump lives under gitignored `build/`; only the derived `puzzles/*.json` is committed)

Each Lichess puzzle carries a **rating**, a **rating deviation**, a **popularity** score,
a **play count**, and **theme tags**. That metadata is what makes a graded curriculum
possible: the modules are theme groups, and inside each one the puzzles are ordered
easiest-first across three bands (1600–1850, 1850–2100, 2100–2400).

Selection filters, all applied before anything is kept:

| filter | value | why |
|---|---|---|
| rating | 1600–2400 | the owner is ~1750 blitz aiming at 1900; Lichess puzzle ratings run harder than blitz ratings, so this is genuinely stretching |
| rating deviation | ≤ 90 | a rating nobody has confirmed is not a difficulty |
| popularity | ≥ 90 | filters out disliked / ambiguous puzzles |
| plays | ≥ 1000 | same reason |
| `oneMove` | excluded | not advanced |
| duplicate FEN | excluded | including against the owner's own puzzles |
| one module per puzzle | first matching theme group | so the same position can't appear twice |

## Why not exercises from books

Silman, Chernev, Dvoretsky and the Woodpecker Method are **copyrighted selections**. An
individual chess position is arguably a fact, but a book's curated and ordered exercise
set — and its annotations — are the author's work, and this is a public repository.
Reproducing them here would not be OK.

The Lichess corpus is a better fit regardless: it is larger than any book's exercise set,
every puzzle is machine-verified from real games, and each carries a rating and themes,
which is what allows the difficulty ramp. The books remain worth reading — they stay in
the plan as offline homework.

## Verification

`tools/build_corpus.py` converts the CSV into the app's schema, and the important detail
is the offset: in the CSV, `FEN` is the position **before** the opponent's setup move and
`Moves[0]` **is** that move — the solver plays `Moves[1]` first. Every imported puzzle is
replayed move-by-move before shipping to confirm:

- the starting FEN is legal, and `sideToMove` / `userColor` match it
- every move is legal, and its SAN and resulting FEN match what was stored
- the line starts **and** ends on a user move, with user flags strictly alternating

648/648 passed with zero problems.

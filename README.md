# Chess

engine built in python

https://isaiahcampusano-chess-engine.onrender.com/

<img width="862" height="786" alt="image" src="https://github.com/user-attachments/assets/fd68e33a-c9d0-4903-b2a0-636ed743e651" />


## Opponents

- **Rookie Randy** is a cheerful novice who thinks out loud and occasionally blunders.
- **Sandbag Sam** is a cocky novice with big talk and the same forgiving playing strength.
- **The Professor** is a dry, clinical expert who searches up to four plies deep.
- **Martin** is an expert wisecracker who also searches up to four plies deep.

Each character reacts to moves with offline, curated commentary. Generated placeholder avatars
are included under `static/avatars/` and can be replaced with final artwork later. After a match,
the final reaction remains visible while you review the board or open the opponent picker again.

## Opening play and search

Browser opponents and the terminal opponent share a bundled weighted opening book.
Experts always take an available book move. Rookie Randy and Sandbag Sam bypass the
book on 10% of book hits, using their existing one-ply move picker and 35% blunder
chance. Once a position leaves the book, each opponent resumes its usual search.
Different games can follow different opening lines; the book does not learn or
download anything during play.

Professor and Martin search up to depth 4 after leaving the book, using the existing
eight-second browser deadline and the deepest completed iteration. The live
evaluation bar stays at depth 3; game review and evaluation never use the book.
Terminal `--depth` still defaults to 3 and honors explicit values.

The selectors accept `opening_book=None` (the default, pure search) and an optional
`rng=random.Random(seed)` for reproducible opening choices. They still return a
`SearchResult`. Book moves report `depth=0`, `nodes=0`, `timed_out=False`, and a
static score after the move from the mover's perspective, rather than a searched
score. HTTP response fields are unchanged. Missing or corrupt book data logs a
warning and permits normal play. The default book is loaded once per process from
the module directory, independently of the working directory.

## Rebuilding the book

The bundled data is derived from all twelve 2013 standard rated-game archives in
the [Lichess open database](https://database.lichess.org/), released under
[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).
`opening_book.sources.json` records each archive URL, SHA-256 checksum, game counts,
build settings, and the generated book checksum. These are online games, not a
master-only or engine-certified repertoire; frequency is a diversity heuristic,
not a guarantee that every move is optimal.

Download the archives to a directory outside this repository and verify them against
[Lichess's published checksums](https://database.lichess.org/standard/sha256sums.txt).
Install the regular requirements plus `requirements-book.txt` to read `.pgn.zst`.
Uncompressed `.pgn` files require only the regular requirements. Python 3.11+ is
required for the builder. From the repository directory, rebuild in PowerShell:

```powershell
python -m pip install -r requirements.txt -r requirements-book.txt
$archives = Get-ChildItem /path/to/archives/lichess_db_standard_rated_2013-*.pgn.zst | Select-Object -ExpandProperty FullName
python build_opening_book.py @archives --source-base-url https://database.lichess.org/standard --license CC0-1.0
```

Defaults require both ratings ≥2000, base time ≥180 seconds, and a standard starting
position. Variants, custom starts, and parser-reported malformed games are skipped.
The builder counts the first 20 plies of accepted games, combines transpositions,
keeps at most five moves per position with at least three occurrences, and uses
frequency as the weight. Equal-frequency moves are ordered by UCI for reproducible
output. Four-field FEN keys exclude counters and retain castling rights and only
legally available en-passant targets. The 20-ply limit applies when extracting
games; runtime lookup is position-based and does not impose a move-counter cutoff.

Run verification with `python -m unittest discover -s tests`. Compression tests are
skipped if the optional builder dependency is absent.


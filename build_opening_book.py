"""Reproducibly aggregate a weighted JSON opening book from local PGN archives."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
import hashlib
import io
import json
from pathlib import Path

import chess
import chess.pgn

from opening_book import position_key


def eligible(headers: chess.pgn.Headers, min_rating: int, min_base_seconds: int) -> bool:
    try:
        return (
            headers.get("Variant", "Standard") == "Standard"
            and headers.get("FEN", chess.STARTING_FEN) == chess.STARTING_FEN
            and headers.get("SetUp", "0") == "0"
            and int(headers.get("WhiteElo", "0")) >= min_rating
            and int(headers.get("BlackElo", "0")) >= min_rating
            and int(headers.get("TimeControl", "-").split("+")[0]) >= min_base_seconds
        )
    except ValueError:
        return False


@contextmanager
def open_pgn(path: Path):
    if path.suffix == ".zst":
        import zstandard  # Optional builder dependency, never imported by the engine.

        with path.open("rb") as raw:
            with zstandard.ZstdDecompressor().stream_reader(raw) as reader:
                with io.TextIOWrapper(reader, encoding="utf-8-sig") as stream:
                    yield stream
    else:
        with path.open(encoding="utf-8-sig") as stream:
            yield stream


def aggregate(stream, counts, *, max_plies=20, min_rating=2000, min_base_seconds=180):
    stats = Counter(seen=0, filtered=0, malformed=0, accepted=0)

    class Visitor(chess.pgn.GameBuilder):
        def end_headers(self):
            if not eligible(self.game.headers, min_rating, min_base_seconds):
                self.filtered = True
                return chess.pgn.SKIP
            self.filtered = False
            return super().end_headers()

        def handle_error(self, error):
            self.game.errors.append(error)

        def result(self):
            return self.game, getattr(self, "filtered", False)

    while True:
        parsed = chess.pgn.read_game(stream, Visitor=Visitor)
        if parsed is None:
            break
        game, filtered = parsed
        stats["seen"] += 1
        if filtered:
            stats["filtered"] += 1
            continue
        if game.errors:
            stats["malformed"] += 1
            continue
        board = game.board()
        prefix = []
        for ply, move in enumerate(game.mainline_moves()):
            if ply >= max_plies:
                break
            if move not in board.legal_moves or board.is_game_over():
                break
            prefix.append((position_key(board), move.uci()))
            board.push(move)
        if not prefix:
            stats["malformed"] += 1
            continue
        for key, move in prefix:
            counts[key][move] += 1
        stats["accepted"] += 1
    return stats


def finalize(counts, *, top_moves=5, min_count=3):
    book = {}
    for key in sorted(counts):
        entries = sorted(counts[key].items(), key=lambda item: (-item[1], item[0]))
        kept = [{"move": move, "weight": count} for move, count in entries if count >= min_count][:top_moves]
        if kept:
            book[key] = kept
    return book


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=Path("opening_book.json"))
    parser.add_argument("--metadata", type=Path, default=Path("opening_book.sources.json"))
    parser.add_argument("--source-base-url", default="")
    parser.add_argument("--license", default="unspecified")
    for name, default in (("max-plies", 20), ("min-rating", 2000), ("min-base-seconds", 180), ("top-moves", 5), ("min-count", 3)):
        parser.add_argument("--" + name, type=int, default=default)
    args = parser.parse_args()
    settings = {name: getattr(args, name) for name in ("max_plies", "min_rating", "min_base_seconds", "top_moves", "min_count")}
    if any(value <= 0 for value in settings.values()):
        parser.error("all numeric settings must be positive")
    counts = defaultdict(Counter)
    sources = []
    for path in sorted(args.inputs):
        with path.open("rb") as raw:
            digest = hashlib.file_digest(raw, "sha256").hexdigest()
        with open_pgn(path) as stream:
            stats = aggregate(stream, counts, **{k: settings[k] for k in ("max_plies", "min_rating", "min_base_seconds")})
        sources.append({"file": path.name, "url": args.source_base_url.rstrip("/") + "/" + path.name if args.source_base_url else None, "sha256": digest, **stats})
        print(json.dumps(sources[-1]), flush=True)
    book = finalize(counts, top_moves=args.top_moves, min_count=args.min_count)
    if not book:
        parser.error("no qualifying positions; existing output was not replaced")
    args.output.write_text(json.dumps(book, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    metadata = {"license": args.license, "settings": settings, "sources": sources,
                "positions": len(book), "candidate_moves": sum(map(len, book.values())),
                "book_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}
    args.metadata.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in metadata.items() if k != "sources"}), flush=True)


if __name__ == "__main__":
    main()

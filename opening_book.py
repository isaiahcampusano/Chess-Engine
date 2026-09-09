"""Small, shared weighted opening book; no network access during gameplay."""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from threading import Lock

import chess

logger = logging.getLogger(__name__)
DEFAULT_BOOK_PATH = Path(__file__).with_name("opening_book.json")


def position_key(board: chess.Board) -> str:
    """Ignore counters and normalize en passant to legally capturable targets."""
    return " ".join(board.fen(en_passant="legal").split()[:4])


class OpeningBook:
    def __init__(self, book_path: str | Path = DEFAULT_BOOK_PATH) -> None:
        self.book: dict[str, tuple[tuple[chess.Move, int], ...]] = {}
        try:
            with Path(book_path).open(encoding="utf-8") as source:
                data = json.load(source)
            if not isinstance(data, dict):
                raise ValueError("expected a position-to-moves object")
        except (OSError, ValueError) as error:
            logger.warning("Opening book unavailable at %s: %s; using normal play.", book_path, error)
            return

        rejected = 0
        for key, entries in data.items():
            try:
                if len(key.split()) != 4 or not isinstance(entries, list):
                    raise ValueError("invalid position or entries")
                board = chess.Board(key + " 0 1")
                if not board.is_valid() or position_key(board) != key:
                    raise ValueError("invalid or noncanonical position")
            except ValueError:
                rejected += 1
                continue
            valid = []
            for entry in entries:
                try:
                    if not isinstance(entry, dict):
                        raise ValueError("invalid entry")
                    weight = entry.get("weight")
                    uci = entry.get("move")
                    if type(weight) is not int or weight <= 0 or not isinstance(uci, str):
                        raise ValueError("invalid move or weight")
                    move = chess.Move.from_uci(uci)
                    if move not in board.legal_moves:
                        raise ValueError("illegal move")
                    valid.append((move, weight))
                except ValueError:
                    rejected += 1
            if valid:
                self.book[key] = tuple(valid)
        if rejected or not self.book:
            logger.warning("Opening book loaded %s positions; rejected %s invalid records.", len(self.book), rejected)

    def get_move(self, board: chess.Board, rng: random.Random | None = None) -> chess.Move | None:
        if board.is_game_over():
            return None
        entries = self.book.get(position_key(board), ())
        legal = [(move, weight) for move, weight in entries if move in board.legal_moves]
        if not legal:
            return None
        moves, weights = zip(*legal)
        return (rng or random).choices(moves, weights=weights, k=1)[0]


_default_book: OpeningBook | None = None
_default_lock = Lock()


def get_default_opening_book() -> OpeningBook:
    """Lazily load exactly once per process, including concurrent first callers."""
    global _default_book
    with _default_lock:
        if _default_book is None:
            _default_book = OpeningBook()
        return _default_book

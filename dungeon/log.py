"""Simple log buffer for debugging adventurer behavior."""

from __future__ import annotations

_lines: list[str] = []


def clear() -> None:
    _lines.clear()


def log(msg: str) -> None:
    _lines.append(msg)


def dump(path: str = "dungeon.log") -> None:
    with open(path, "w") as f:
        f.write("\n".join(_lines))

"""Structured logger for Dungeon Symbiosis.

Levels: DEBUG < INFO < WARNING < ERROR
Default level is INFO. Set to DEBUG with --debug flag or DUNGEON_DEBUG=1 env var.

Usage (game logic):
    from dungeon.log import get_logger
    log = get_logger(__name__)

    log.debug("path recomputed", entity="adv_1", goal=(5, 3))
    log.info("adventurer exited", entity="adv_1", mana_earned=42)
    log.warning("belief conflict", tile=(4, 3), held="CHEST", seen="EMPTY")
    log.error("entity stuck in solid tile", entity="adv_1", pos=(2, 2))

Old-style module-level log() calls are preserved for backwards compatibility.
"""

from __future__ import annotations

import os
import sys
import time
from enum import IntEnum
from typing import Any


class Level(IntEnum):
    DEBUG   = 10
    INFO    = 20
    WARNING = 30
    ERROR   = 40


# ---------------------------------------------------------------------------
# Global configuration
# ---------------------------------------------------------------------------

_level: Level = Level.INFO
_sink: list[str] = []          # in-memory ring buffer for dump()
_sink_max: int = 10_000        # max entries kept in memory
_stderr_enabled: bool = True   # print to stderr in real time


def configure(
    level: Level | None = None,
    stderr: bool | None = None,
    sink_max: int | None = None,
) -> None:
    global _level, _stderr_enabled, _sink_max
    if level is not None:
        _level = level
    if stderr is not None:
        _stderr_enabled = stderr
    if sink_max is not None:
        _sink_max = sink_max


def set_debug(enabled: bool = True) -> None:
    """Enable or disable DEBUG-level logging."""
    configure(level=Level.DEBUG if enabled else Level.INFO)


def is_debug() -> bool:
    return _level <= Level.DEBUG


# Auto-enable debug if env var set
if os.environ.get("DUNGEON_DEBUG", "").strip() not in ("", "0"):
    set_debug(True)


# ---------------------------------------------------------------------------
# Core emit
# ---------------------------------------------------------------------------

_LEVEL_LABELS = {
    Level.DEBUG:   "DEBUG",
    Level.INFO:    "INFO ",
    Level.WARNING: "WARN ",
    Level.ERROR:   "ERROR",
}

_LEVEL_COLORS = {
    Level.DEBUG:   "\033[90m",   # dark grey
    Level.INFO:    "\033[0m",    # default
    Level.WARNING: "\033[33m",   # yellow
    Level.ERROR:   "\033[31m",   # red
}
_RESET = "\033[0m"
_USE_COLOR = sys.stderr.isatty()


def _emit(level: Level, msg: str, **fields: Any) -> None:
    if level < _level:
        return

    label = _LEVEL_LABELS[level]
    ts = f"{time.monotonic():.3f}"

    parts = [f"{label} {ts} {msg}"]
    if fields:
        kv = " ".join(f"{k}={v!r}" for k, v in fields.items())
        parts.append(kv)
    line = "  ".join(parts)

    if _sink is not None:
        _sink.append(line)
        if len(_sink) > _sink_max:
            _sink.pop(0)

    if _stderr_enabled:
        if _USE_COLOR:
            color = _LEVEL_COLORS.get(level, "")
            print(f"{color}{line}{_RESET}", file=sys.stderr)
        else:
            print(line, file=sys.stderr)


# ---------------------------------------------------------------------------
# Logger class (per-module)
# ---------------------------------------------------------------------------

class Logger:
    """Per-module logger. Created via get_logger(__name__)."""

    def __init__(self, name: str) -> None:
        self.name = name

    def debug(self, msg: str, **fields: Any) -> None:
        _emit(Level.DEBUG, f"[{self.name}] {msg}", **fields)

    def info(self, msg: str, **fields: Any) -> None:
        _emit(Level.INFO, f"[{self.name}] {msg}", **fields)

    def warning(self, msg: str, **fields: Any) -> None:
        _emit(Level.WARNING, f"[{self.name}] {msg}", **fields)

    def error(self, msg: str, **fields: Any) -> None:
        _emit(Level.ERROR, f"[{self.name}] {msg}", **fields)


_loggers: dict[str, Logger] = {}


def get_logger(name: str) -> Logger:
    if name not in _loggers:
        _loggers[name] = Logger(name)
    return _loggers[name]


# ---------------------------------------------------------------------------
# Sink management
# ---------------------------------------------------------------------------

def clear() -> None:
    """Clear the in-memory log buffer."""
    _sink.clear()


def dump(path: str = "dungeon.log") -> None:
    """Write in-memory buffer to a file."""
    with open(path, "w") as f:
        f.write("\n".join(_sink))
    if _sink:
        _emit(Level.INFO, f"log dumped to {path}", entries=len(_sink))


def get_lines(
    level: Level | None = None,
    contains: str | None = None,
    limit: int | None = None,
) -> list[str]:
    """Query the in-memory buffer. Useful in tests and the debug overlay."""
    result = _sink
    if level is not None:
        label = _LEVEL_LABELS[level].strip()
        result = [l for l in result if l.startswith(label)]
    if contains is not None:
        result = [l for l in result if contains in l]
    if limit is not None:
        result = result[-limit:]
    return list(result)


# ---------------------------------------------------------------------------
# Backwards compatibility: old module-level log() call
# ---------------------------------------------------------------------------

_compat_logger = get_logger("dungeon")


def log(msg: str) -> None:
    """Deprecated: use get_logger(__name__).debug() instead."""
    _compat_logger.debug(msg)

"""Shared helpers: filename de-duplication (ADR-3), output dirs, logging."""

from __future__ import annotations

import logging
from pathlib import Path

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def next_available_path(path: str | Path) -> Path:
    """Return ``path`` if it does not exist, else append ``-2``, ``-3``, … to the stem.

    Implements ADR-3 (numeric-suffix-on-conflict). Examples::

        frame_001.png exists                       -> frame_001-2.png
        frame_001.png and frame_001-2.png exist    -> frame_001-3.png
        idle_sheet.png exists                      -> idle_sheet-2.png

    Args:
        path: Target output path.

    Returns:
        First non-existing path in the ``{stem}, {stem}-2, {stem}-3, …`` sequence.
    """
    candidate = Path(path)
    if not candidate.exists():
        return candidate

    parent = candidate.parent
    stem = candidate.stem
    suffix = candidate.suffix

    counter = 2
    while True:
        next_candidate = parent / f"{stem}-{counter}{suffix}"
        if not next_candidate.exists():
            return next_candidate
        counter += 1


def ensure_output_dir(output_dir: str | Path) -> Path:
    """Create ``output_dir`` if missing; return its resolved Path.

    Args:
        output_dir: Directory path.

    Returns:
        Resolved Path object.

    Raises:
        OSError: If the path exists but is not a directory.
    """
    path = Path(output_dir)
    if path.exists() and not path.is_dir():
        raise OSError(f"Output path exists but is not a directory: {path}")
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def get_logger(name: str = "sprite_kit") -> logging.Logger:
    """Return a configured stdlib Logger (idempotent).

    First call configures a single console StreamHandler at INFO level;
    subsequent calls return the same logger without adding duplicate
    handlers.
    """
    logger = logging.getLogger(name)
    if not getattr(logger, "_sprite_kit_configured", False):
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(_LOG_FORMAT))
            logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger._sprite_kit_configured = True  # type: ignore[attr-defined]
    return logger

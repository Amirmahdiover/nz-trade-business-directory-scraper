"""Shared utility helpers."""

import logging
from pathlib import Path

from app.config import LOG_FORMAT, LOG_LEVEL


def setup_logging() -> None:
    """Configure simple console logging for scripts."""

    logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def ensure_directory(path: Path) -> None:
    """Create a directory if it does not already exist."""

    path.mkdir(parents=True, exist_ok=True)


def model_to_dict(record) -> dict:
    """Return a dict for Pydantic v1 or v2 models."""

    if hasattr(record, "model_dump"):
        return record.model_dump()
    return record.dict()

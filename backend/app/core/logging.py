"""Structured-ish logging setup kept intentionally small and dependency-free."""

from __future__ import annotations

import logging
import sys

from app.core.config import settings

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def configure_logging() -> None:
    """Configure root logging once, at application start-up."""
    root = logging.getLogger()
    if root.handlers:  # already configured (e.g. by uvicorn or a test run)
        root.setLevel(settings.log_level.upper())
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())

    # Uvicorn duplicates access logs through its own handlers.
    logging.getLogger("uvicorn.access").propagate = False


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

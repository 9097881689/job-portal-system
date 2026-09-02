from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import ROOT_DIR, settings


def configure_logging() -> None:
    """Configure console and rotating-file logging for cron-friendly execution."""

    log_dir = ROOT_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = RotatingFileHandler(log_dir / "job_portal.log", maxBytes=2_000_000, backupCount=5)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

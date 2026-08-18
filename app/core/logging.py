"""Logging setup using loguru with safe fallbacks."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from loguru import logger

from app.core.config import get_settings

_configured = False


def setup_logging(level: Optional[str] = None) -> None:
    """Configure loguru sinks (stderr + rotating file). Idempotent."""
    global _configured
    if _configured:
        return

    settings = get_settings()
    log_level = (level or settings.log_level).upper()
    log_file = Path(settings.log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.add(
        sys.stderr,
        level=log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}:{function}:{line}</cyan> - <level>{message}</level>"
        ),
        enqueue=False,
        backtrace=False,
        diagnose=False,
    )
    logger.add(
        str(log_file),
        level=log_level,
        rotation="10 MB",
        retention="10 days",
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )

    _configured = True
    logger.info("Logging initialised at level {}", log_level)


def get_logger():
    """Return the configured logger instance."""
    if not _configured:
        setup_logging()
    return logger

"""Setup logging berbasis Loguru.

Menyediakan logger yang siap pakai dengan format konsisten dan
kemampuan menulis ke file (opsional).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from loguru import logger as _logger

_configured = False


def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path | str] = None,
    *,
    force: bool = False,
):
    """Konfigurasi logger global (idempoten kecuali ``force=True``).

    Args:
        level: level log (DEBUG/INFO/WARNING/ERROR).
        log_file: bila diberikan, log juga ditulis ke file ini.
        force: paksa re-konfigurasi walau sudah pernah dikonfigurasi.
    """
    global _configured
    if _configured and not force:
        return _logger

    _logger.remove()
    _logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )
    if log_file is not None:
        _logger.add(
            str(Path(log_file)),
            level=level,
            rotation="10 MB",
            retention="5 days",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
        )
    _configured = True
    return _logger


logger = setup_logging()

"""Document detector - menemukan & memvalidasi file yang didukung.

Menerima path file tunggal ATAU direktori. Bila direktori, scan rekursif
dan kembalikan daftar file yang didukung (urutkan agar deterministik).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from siberrag_core.parsers.registry import is_supported
from siberrag_core.utils.logging import logger


def discover_documents(path: Path | str) -> list[Path]:
    """Temukan semua file dokumen yang didukung di ``path``.

    - Bila ``path`` adalah file: kembalikan [path] bila didukung, [] bila tidak.
    - Bila direktori: scan rekursif, urutkan berdasarkan nama.
    """
    p = Path(path)
    if not p.exists():
        logger.error(f"Path tidak ditemukan: {p}")
        return []
    if p.is_file():
        if is_supported(p):
            return [p]
        logger.warning(f"File tidak didukung, dilewati: {p.name}")
        return []
    # direktori: scan rekursif
    found: list[Path] = []
    for f in sorted(p.rglob("*")):
        if f.is_file() and is_supported(f):
            found.append(f)
    return found


def group_by_extension(paths: Iterable[Path]) -> dict[str, list[Path]]:
    """Kelompokkan path berdasarkan ekstensi (untuk statistik)."""
    groups: dict[str, list[Path]] = {}
    for p in paths:
        ext = p.suffix.lower().lstrip(".")
        groups.setdefault(ext, []).append(p)
    return groups

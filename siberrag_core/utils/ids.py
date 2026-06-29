"""Generator ID deterministik & unik."""

from __future__ import annotations

import hashlib
from pathlib import Path


def document_id(filename: str, content: str | bytes | None = None) -> str:
    """ID dokumen stabil berbasis hash SHA-256 nama + konten.

    Bila konten tidak diberikan, hanya pakai nama file (kurang stabil tapi tetap unik).
    """
    h = hashlib.sha256()
    h.update(filename.encode("utf-8"))
    if isinstance(content, str):
        h.update(content.encode("utf-8"))
    elif isinstance(content, bytes):
        h.update(content)
    return "doc_" + h.hexdigest()[:16]


def chunk_id(document_id: str, chunk_index: int) -> str:
    """ID chunk dari document_id + index."""
    return f"{document_id}_c{chunk_index:04d}"


def file_signature(path: Path) -> str:
    """Signature file dari path+size+mtime (untuk dedup)."""
    stat = path.stat()
    raw = f"{path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

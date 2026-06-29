"""Implementasi check validasi chunk.

Setiap check adalah fungsi yang menerima (chunk, config) dan menambahkan
finding ke objek ChunkValidation. Quality score dihitung dari akumulasi finding.
"""

from __future__ import annotations

import re
from typing import Optional

from siberrag_core.config import ValidationConfig
from siberrag_core.models.chunk import Chunk
from siberrag_core.models.validation import ChunkValidation, Severity

# tanda kalimat terpotong: diakhiri tanpa tanda baca & diawali huruf kecil,
# atau diawali dengan kata sambung yang biasanya di tengah kalimat.
_TRAILING_OPEN = re.compile(r"[,;:({\[>]$")
_LEADING_LOWER = re.compile(r"^[a-z]")
_INCOMPLETE_END = re.compile(r"\w$")  # diakhiri huruf tanpa tanda baca


def check_token_bounds(chunk: Chunk, validation: ChunkValidation,
                       cfg: ValidationConfig) -> None:
    """Token dalam batas ideal (target 450-550, min 250, max 700)."""
    tokens = chunk.metadata.token_count
    if tokens > 700:
        if cfg.flag_oversized:
            validation.add("OVERSIZED", f"Chunk {tokens} token (>700 maksimum).",
                           Severity.WARNING)
            validation.quality_score -= 15
    elif tokens < 250:
        if cfg.flag_undersized:
            validation.add("UNDERSIZED", f"Chunk {tokens} token (<250 minimum).",
                           Severity.WARNING)
            validation.quality_score -= 8
    elif not (450 <= tokens <= 550):
        # dalam rentang min-max tapi di luar target ideal -> info ringan
        validation.add("NON_IDEAL_SIZE", f"Chunk {tokens} token (target ideal 450-550).",
                       Severity.INFO)
        validation.quality_score -= 3


def check_no_truncated_sentence(chunk: Chunk, validation: ChunkValidation,
                                cfg: ValidationConfig) -> None:
    """Tidak ada kalimat terpotong di awal/akhir chunk."""
    text = chunk.text.strip()
    if not text:
        return
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return
    first = lines[0].strip()
    last = lines[-1].strip()

    # diawali huruf kecil -> kemungkinan kelanjutan (terpotong di awal)
    if _LEADING_LOWER.match(first) and not first.startswith(("- ", "1.", "* ")):
        # pengecualian: item list / awal wajar
        validation.add("POSSIBLE_TRUNC_START",
                       "Chunk diawali huruf kecil; mungkin kelanjutan kalimat.",
                       Severity.WARNING)
        validation.quality_score -= 10

    # diakhiri tanpa tanda baca penutup -> kemungkinan terpotong di akhir
    if _INCOMPLETE_END.search(last) and not _TRAILING_OPEN.search(last) \
            and not last.endswith((".", "?", "!", ":", ";", "|", ")", "]",
                                  '"', "'", "”", "’", "%")):
        # pengecualian: heading/list/table baris
        if not last.startswith(("#", "|", "-")):
            validation.add("POSSIBLE_TRUNC_END",
                           "Chunk tidak diakhiri tanda baca; mungkin terpotong.",
                           Severity.WARNING)
            validation.quality_score -= 10


def check_no_empty_heading(chunk: Chunk, validation: ChunkValidation,
                           cfg: ValidationConfig) -> None:
    """Tidak ada heading kosong."""
    # heading biasanya muncul sebagai baris pendek di awal chunk
    lines = [l.strip() for l in chunk.text.splitlines() if l.strip()]
    for i, line in enumerate(lines[:3]):  # periksa 3 baris pertama
        if line.startswith("#"):
            heading_text = line.lstrip("# ").strip()
            if not heading_text:
                validation.add("EMPTY_HEADING", "Terdapat heading kosong.",
                               Severity.ERROR)
                validation.quality_score -= 20
                break


def check_metadata_complete(chunk: Chunk, validation: ChunkValidation,
                            cfg: ValidationConfig) -> None:
    """Metadata lengkap (semua field wajib terisi)."""
    m = chunk.metadata
    required = {
        "id": m.id, "document_id": m.document_id, "filename": m.filename,
        "chapter": m.chapter, "section": m.section, "language": m.language,
    }
    missing = [k for k, v in required.items() if not v]
    if m.token_count <= 0:
        missing.append("token_count")
    if m.total_chunk <= 0:
        missing.append("total_chunk")
    if missing:
        validation.add("INCOMPLETE_METADATA",
                       f"Field metadata kosong: {', '.join(missing)}.",
                       Severity.WARNING)
        validation.quality_score -= 5


def check_not_duplicate(chunk: Chunk, validation: ChunkValidation,
                        cfg: ValidationConfig, *, seen: Optional[set[str]] = None,
                        duplicates: Optional[set[str]] = None) -> None:
    """Bukan duplikat (signature berbasis normalized text)."""
    if not cfg.flag_duplicate:
        return
    sig = _signature(chunk.text)
    if seen is not None and duplicates is not None:
        if sig in seen and sig not in duplicates:
            duplicates.add(sig)
            validation.add("DUPLICATE", "Chunk kemungkinan duplikat chunk lain.",
                           Severity.WARNING)
            validation.quality_score -= 12
        seen.add(sig)


def _signature(text: str) -> str:
    """Signature normalisasi untuk deteksi duplikat."""
    import re as _re
    return _re.sub(r"\s+", " ", text or "").strip().lower()[:500]

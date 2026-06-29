"""Validator - mengorkestrasi check validasi & menghasilkan quality score.

Setiap chunk mendapat:
- Quality Score (0-100, 100 = sempurna)
- Warnings (temuan yang menurunkan skor)
- Recommendations (info ringan,Severity.INFO)

Validator menjalankan seluruh chunk agar deteksi duplikat lintas-chunk akurat.
"""

from __future__ import annotations

from typing import Optional

from siberrag_core.config import AppConfig, ValidationConfig
from siberrag_core.models.chunk import Chunk
from siberrag_core.models.validation import ChunkValidation
from siberrag_core.utils.logging import logger
from siberrag_core.validator.checks import (
    check_metadata_complete,
    check_no_empty_heading,
    check_no_truncated_sentence,
    check_not_duplicate,
    check_token_bounds,
)


class ChunkValidator:
    """Validasi kualitas chunk."""

    def __init__(self, config: Optional[ValidationConfig | AppConfig] = None) -> None:
        self.cfg: ValidationConfig = (
            config.validation if isinstance(config, AppConfig) else (config or ValidationConfig())
        )

    def validate_all(self, chunks: list[Chunk]) -> list[ChunkValidation]:
        """Validasi seluruh chunk. Deteksi duplikat butuh konteks lintas-chunk."""
        if not self.cfg.enabled:
            return [
                ChunkValidation(chunk_id=c.id, quality_score=100) for c in chunks
            ]

        seen: set[str] = set()
        duplicates: set[str] = set()
        results: list[ChunkValidation] = []

        for chunk in chunks:
            v = ChunkValidation(chunk_id=chunk.id, quality_score=100)
            check_token_bounds(chunk, v, self.cfg)
            check_no_truncated_sentence(chunk, v, self.cfg)
            check_no_empty_heading(chunk, v, self.cfg)
            check_metadata_complete(chunk, v, self.cfg)
            check_not_duplicate(chunk, v, self.cfg, seen=seen, duplicates=duplicates)
            # clamp skor
            v.quality_score = max(0, min(100, v.quality_score))
            results.append(v)

        n_warn = sum(1 for r in results for _ in r.warnings)
        logger.debug(f"Validator: {len(results)} chunk divalidasi, {n_warn} warning.")
        return results

    def validate(self, chunk: Chunk) -> ChunkValidation:
        """Validasi satu chunk (tanpa konteks duplikat lintas-chunk)."""
        return self.validate_all([chunk])[0]

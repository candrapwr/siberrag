"""Metadata Builder - memastikan metadata setiap chunk lengkap & akurat.

Tanggung jawab:
- Deteksi bahasa dokumen (sekali, dipakai untuk semua chunk).
- Hitung ulang token_count & word_count agar konsisten.
- Isi field yang masih kosong.
- Setel page range konsisten.
"""

from __future__ import annotations

from typing import Optional

from siberrag_core.config import AppConfig, MetadataConfig
from siberrag_core.models.chunk import Chunk
from siberrag_core.utils.language import detect_language
from siberrag_core.utils.logging import logger
from siberrag_core.utils.tokens import TokenCounter, get_counter
from siberrag_core.utils.text import count_words


class MetadataBuilder:
    """Melengkapi metadata chunk."""

    def __init__(
        self,
        config: Optional[MetadataConfig | AppConfig] = None,
        *,
        encoding: str = "cl100k_base",
    ) -> None:
        self.cfg: MetadataConfig = (
            config.metadata if isinstance(config, AppConfig) else (config or MetadataConfig())
        )
        self.counter: TokenCounter = get_counter(encoding)

    def enrich(self, chunks: list[Chunk], *, sample_text: str = "") -> list[Chunk]:
        """Lengkapi metadata seluruh chunk.

        Args:
            chunks: daftar chunk yang akan diperkaya.
            sample_text: teks representatif untuk deteksi bahasa (mis. gabungan beberapa chunk).
        """
        language = ""
        if self.cfg.detect_language:
            sample = sample_text or " ".join(c.text[:200] for c in chunks[:5])
            if sample.strip():
                language = detect_language(sample)
            logger.debug(f"Deteksi bahasa: {language or '(default)'}")

        for chunk in chunks:
            # hitung ulang agar konsisten
            chunk.metadata.token_count = self.counter(chunk.text)
            chunk.metadata.word_count = count_words(chunk.text)
            if not chunk.metadata.language:
                chunk.metadata.language = language
            # validasi page range
            if chunk.metadata.page_end < chunk.metadata.page_start:
                chunk.metadata.page_end = chunk.metadata.page_start
        return chunks

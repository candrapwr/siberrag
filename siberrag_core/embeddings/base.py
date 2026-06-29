"""Base class untuk embedding provider.

Kontrak: ``embed(text) -> list[float]`` dan ``embed_batch(texts) -> list[list[float]]``.
Setiap provider wajib implement & ekspos ``is_available()`` agar registry bisa
fallback bila library opsional tidak terpasang.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from siberrag_core.config import AppConfig, EmbeddingConfig


class EmbeddingError(Exception):
    """Dilempar ketika embedding provider gagal."""


class BaseEmbedder(ABC):
    """Kontrak embedding provider."""

    name: str = "base"

    def __init__(self, config: Optional[EmbeddingConfig | AppConfig] = None) -> None:
        self.config: EmbeddingConfig = (
            config.embedding if isinstance(config, AppConfig) else (config or EmbeddingConfig())
        )

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Embed satu teks -> vektor."""
        raise NotImplementedError

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed banyak teks sekaligus (batch)."""
        raise NotImplementedError

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Dimensi vektor yang dihasilkan."""
        raise NotImplementedError

"""Base class untuk vector store backend."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from siberrag_core.config import AppConfig, VectorDBConfig
from siberrag_core.models.chunk import Chunk


@dataclass
class SearchHit:
    """Satu hasil pencarian: chunk + skor relevansi."""

    chunk: Chunk
    score: float  # similarity score (semakin tinggi semakin relevan)


@dataclass
class SearchResults:
    """Hasil pencarian vector store."""

    query: str = ""
    hits: list[SearchHit] = field(default_factory=list)

    @property
    def chunks(self) -> list[Chunk]:
        return [h.chunk for h in self.hits]

    def __len__(self) -> int:
        return len(self.hits)


class BaseVectorStore(ABC):
    """Kontrak vector store: upsert / search / delete / count."""

    name: str = "base"

    def __init__(self, config: Optional[VectorDBConfig | AppConfig] = None) -> None:
        self.config: VectorDBConfig = (
            config.vector_db if isinstance(config, AppConfig) else (config or VectorDBConfig())
        )

    @abstractmethod
    def upsert(self, chunks: list[Chunk], embeddings: list[list[float]]) -> int:
        """Simpan/perbarui chunk + embedding. Return jumlah chunk disimpan."""
        raise NotImplementedError

    @abstractmethod
    def search(self, query_embedding: list[float], top_k: int = 5,
               where: Optional[dict[str, Any]] = None) -> SearchResults:
        """Cari chunk terdekat dengan query_embedding."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, ids: list[str]) -> int:
        """Hapus chunk berdasarkan id. Return jumlah terhapus."""
        raise NotImplementedError

    @abstractmethod
    def count(self) -> int:
        """Jumlah chunk tersimpan."""
        raise NotImplementedError

    @abstractmethod
    def list_collections(self) -> list[str]:
        """Daftar collection tersedia."""
        raise NotImplementedError

"""Registry vector store - factory berdasarkan konfigurasi."""

from __future__ import annotations

from typing import Optional

from siberrag_core.config import AppConfig, VectorDBConfig
from siberrag_core.vectorstore.base import BaseVectorStore
from siberrag_core.vectorstore.chroma_store import ChromaVectorStore

_BACKENDS: dict[str, type[BaseVectorStore]] = {
    "chroma": ChromaVectorStore,
}


def get_vectorstore(config: Optional[VectorDBConfig | AppConfig] = None,
                    *, backend: Optional[str] = None) -> BaseVectorStore:
    """Factory vector store dari konfigurasi."""
    cfg: VectorDBConfig = (
        config.vector_db if isinstance(config, AppConfig) else (config or VectorDBConfig())
    )
    name = backend or cfg.backend
    cls = _BACKENDS.get(name)
    if cls is None:
        raise ValueError(f"Backend vector store tidak dikenal: {name}. "
                         f"Tersedia: {list(_BACKENDS)}")
    return cls(cfg)

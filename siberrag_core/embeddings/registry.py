"""Registry embedding - memilih provider berdasarkan konfigurasi.

Pola sama dengan exporters/registry.py & parsers/registry.py.
Provider tidak terpasang -> raise EmbeddingError yang jelas saat dipakai.
"""

from __future__ import annotations

from typing import Optional

from siberrag_core.config import AppConfig, EmbeddingConfig
from siberrag_core.embeddings.base import BaseEmbedder, EmbeddingError
from siberrag_core.embeddings.local import LocalEmbedder
from siberrag_core.embeddings.openai_emb import OpenAIEmbedder
from siberrag_core.utils.logging import logger

_PROVIDERS: dict[str, type[BaseEmbedder]] = {
    "local": LocalEmbedder,
    "openai": OpenAIEmbedder,
    "custom": OpenAIEmbedder,  # alias: OpenAI-compatible endpoint (Jina/Cohere/Ollama/dll)
}


def get_embedder(config: Optional[EmbeddingConfig | AppConfig] = None,
                 *, provider: Optional[str] = None) -> BaseEmbedder:
    """Factory embedder dari konfigurasi.

    Args:
        config: AppConfig atau EmbeddingConfig.
        provider: override provider (bila tidak None, abaikan config).
    """
    emb_cfg: EmbeddingConfig = (
        config.embedding if isinstance(config, AppConfig) else (config or EmbeddingConfig())
    )
    name = provider or emb_cfg.provider
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise EmbeddingError(f"Provider embedding tidak dikenal: {name}. "
                             f"Tersedia: {list(_PROVIDERS)}")
    logger.debug(f"Embedder provider: {name}")
    return cls(emb_cfg)

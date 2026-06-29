"""Embedding provider lokal berbasis sentence-transformers.

Default model: BAAI/bge-m3 (multilingual, akurat untuk Bahasa Indonesia).
Bila sentence-transformers tidak terpasang, ``is_available()`` False dan
registry akan raise error yang jelas saat dipakai.
"""

from __future__ import annotations

from typing import Optional

from siberrag_core.config import AppConfig, EmbeddingConfig
from siberrag_core.embeddings.base import BaseEmbedder, EmbeddingError
from siberrag_core.utils.logging import logger

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
    _HAS_ST = True
except Exception:  # pragma: no cover - opsional
    _HAS_ST = False


def is_available() -> bool:
    """True bila sentence-transformers terpasang."""
    return _HAS_ST


class LocalEmbedder(BaseEmbedder):
    """Embedding lokal via sentence-transformers."""

    name = "local"

    def __init__(self, config: Optional[EmbeddingConfig | AppConfig] = None) -> None:
        super().__init__(config)
        if not _HAS_ST:
            raise EmbeddingError(
                "sentence-transformers tidak terpasang. Install dengan: pip install -e '.[rag]'"
            )
        self._model: Optional[SentenceTransformer] = None

    def _get_model(self) -> "SentenceTransformer":
        if self._model is None:
            logger.info(f"Memuat model embedding lokal: {self.config.model}...")
            self._model = SentenceTransformer(self.config.model)
            logger.info(f"Model {self.config.model} siap (dim={self._get_dim()}).")
        return self._model

    def _get_dim(self) -> int:
        """Ambil dimensi embedding (handle rename API di versi baru)."""
        model = self._get_model()
        for method in ("get_embedding_dimension", "get_sentence_embedding_dimension"):
            fn = getattr(model, method, None)
            if callable(fn):
                try:
                    return int(fn())
                except Exception:
                    pass
        return self.config.dim

    def embed(self, text: str) -> list[float]:
        model = self._get_model()
        vec = model.encode(text, normalize_embeddings=True, convert_to_numpy=True)
        return vec.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._get_model()
        # batch processing sesuai config
        results: list[list[float]] = []
        batch_size = max(1, self.config.batch_size)
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            vecs = model.encode(batch, normalize_embeddings=True, convert_to_numpy=True)
            results.extend(v.tolist() for v in vecs)
        return results

    @property
    def dimension(self) -> int:
        return self._get_dim()

"""Embedding provider via OpenAI-compatible API.

Mendukung provider APA SAJA yang OpenAI-compatible:
- OpenAI resmi (text-embedding-3-small/large)
- Jina, Cohere, Together, Gemini OpenAI-mode, dll
- Endpoint lokal: Ollama (dengan OpenAI shim), LM Studio, vLLM, dll

Konfigurasi via:
- api_base: URL endpoint (mis. https://api.openai.com/v1, http://localhost:11434/v1)
- api_key: key (boleh kosong untuk endpoint lokal tanpa auth)
- model: nama model embedding di provider tersebut
"""

from __future__ import annotations

import os
from typing import Optional

from siberrag_core.config import AppConfig, EmbeddingConfig
from siberrag_core.embeddings.base import BaseEmbedder, EmbeddingError
from siberrag_core.utils.logging import logger

try:
    from openai import OpenAI  # type: ignore
    _HAS_OPENAI = True
except Exception:  # pragma: no cover - opsional
    _HAS_OPENAI = False


def is_available() -> bool:
    """True bila openai SDK terpasang."""
    return _HAS_OPENAI


class OpenAIEmbedder(BaseEmbedder):
    """Embedding via OpenAI-compatible API (provider mana saja).

    Bekerja untuk dua alias provider: ``openai`` (resmi) dan ``custom``
    (endpoint OpenAI-compatible lain). Perbedaannya hanya dokumentasi -
    logikanya identik karena semua pakai OpenAI SDK.
    """

    name = "openai"

    def __init__(self, config: Optional[EmbeddingConfig | AppConfig] = None) -> None:
        super().__init__(config)
        if not _HAS_OPENAI:
            raise EmbeddingError(
                "openai SDK tidak terpasang. Install dengan: pip install -e '.[rag-openai]'"
            )
        # API key: dari config, lalu fallback env. Boleh kosong utk endpoint lokal.
        api_key = self.config.api_key or os.getenv("OPENAI_API_KEY", "")
        # Beberapa endpoint lokal (Ollama/LM Studio) tidak butuh auth -> pakai dummy key.
        if not api_key:
            if self._is_local_endpoint():
                logger.info("Endpoint lokal terdeteksi (tanpa API key) - menggunakan dummy key.")
                api_key = "ollama"  # OpenAI SDK butuh non-empty string
            else:
                raise EmbeddingError(
                    "API key tidak ditemukan. Set OPENAI_API_KEY atau isi config.embedding.api_key. "
                    "(Untuk endpoint lokal tanpa auth, tetap bisa - isi api_key bebas.)"
                )
        base_url = self.config.api_base or None
        logger.debug(f"OpenAI-compatible embedder: base_url={base_url or 'default'}, model={self.config.model}")
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._dim: Optional[int] = None

    def _is_local_endpoint(self) -> bool:
        """True bila api_base menunjuk ke localhost/127.0.0.1 (umumnya tanpa auth)."""
        base = (self.config.api_base or "").lower()
        return any(host in base for host in ("localhost", "127.0.0.1", "0.0.0.0", "::1"))

    def _embed_api(self, texts: list[str]) -> list[list[float]]:
        try:
            resp = self._client.embeddings.create(model=self.config.model, input=texts)
        except Exception as exc:
            raise EmbeddingError(
                f"Gagal memanggil endpoint embedding ({self.config.api_base}): {exc}"
            ) from exc
        if not resp.data:
            raise EmbeddingError("Endpoint embedding mengembalikan response kosong.")
        self._dim = len(resp.data[0].embedding)
        return [d.embedding for d in sorted(resp.data, key=lambda x: x.index)]

    def embed(self, text: str) -> list[float]:
        return self._embed_api([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        results: list[list[float]] = []
        batch_size = max(1, self.config.batch_size)
        for i in range(0, len(texts), batch_size):
            results.extend(self._embed_api(texts[i:i + batch_size]))
        return results

    @property
    def dimension(self) -> int:
        if self._dim is None:
            # embed teks pendek untuk dapat dimensi
            self._dim = len(self.embed("dimension probe"))
        return self._dim

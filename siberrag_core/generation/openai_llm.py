"""LLM generator via OpenAI API (atau OpenAI-compatible endpoint).

Bisa dipakai untuk OpenAI resmi (GPT-4o) atau endpoint compatible lain
(LM Studio, vLLM, Ollama dengan OpenAI shim) via api_base.
"""

from __future__ import annotations

import os
from typing import Optional

from siberrag_core.config import AppConfig, LLMConfig
from siberrag_core.generation.base import BaseLLM
from siberrag_core.utils.logging import logger

try:
    from openai import OpenAI  # type: ignore
    _HAS_OPENAI = True
except Exception:  # pragma: no cover - opsional
    _HAS_OPENAI = False


def is_available() -> bool:
    return _HAS_OPENAI


class OpenAILLM(BaseLLM):
    """LLM via OpenAI-compatible API."""

    name = "openai"

    def __init__(self, config: Optional[LLMConfig | AppConfig] = None) -> None:
        super().__init__(config)
        if not _HAS_OPENAI:
            raise RuntimeError(
                "openai SDK tidak terpasang. Install dengan: pip install -e '.[rag-openai]'"
            )
        api_key = self.config.api_key or os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            if self._is_local_endpoint():
                logger.info("Endpoint LLM lokal terdeteksi (tanpa API key) - menggunakan dummy key.")
                api_key = "local"
            else:
                raise RuntimeError(
                    "OPENAI_API_KEY tidak ditemukan. Set env var atau isi config.llm.api_key."
                )
        self._client = OpenAI(api_key=api_key, base_url=self.config.api_base or None)

    def _is_local_endpoint(self) -> bool:
        """True bila api_base menunjuk ke endpoint lokal yang umumnya tanpa auth."""
        base = (self.config.api_base or "").lower()
        return any(host in base for host in ("localhost", "127.0.0.1", "0.0.0.0", "::1"))

    def generate(self, messages: list[dict[str, str]]) -> str:
        logger.debug(f"LLM generate: model={self.config.model}, messages={len(messages)}")
        resp = self._client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        return resp.choices[0].message.content or ""

"""Registry LLM - factory berdasarkan konfigurasi."""

from __future__ import annotations

from typing import Optional

from siberrag_core.config import AppConfig, LLMConfig
from siberrag_core.generation.base import BaseLLM
from siberrag_core.generation.openai_llm import OpenAILLM

_PROVIDERS: dict[str, type[BaseLLM]] = {
    "openai": OpenAILLM,
}


def get_llm(config: Optional[LLMConfig | AppConfig] = None,
            *, provider: Optional[str] = None) -> BaseLLM:
    """Factory LLM dari konfigurasi."""
    cfg: LLMConfig = (
        config.llm if isinstance(config, AppConfig) else (config or LLMConfig())
    )
    name = provider or cfg.provider
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise ValueError(f"Provider LLM tidak dikenal: {name}. Tersedia: {list(_PROVIDERS)}")
    return cls(cfg)

"""Base class LLM generator + Answer model."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from siberrag_core.config import AppConfig, LLMConfig
from siberrag_core.vectorstore.base import SearchResults


@dataclass
class Answer:
    """Hasil jawaban RAG: teks jawaban + sumber context."""

    question: str = ""
    text: str = ""
    sources: SearchResults = field(default_factory=SearchResults)
    model: str = ""
    error: Optional[str] = None
    # token usage (bila tersedia)
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def is_error(self) -> bool:
        return self.error is not None

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "answer": self.text,
            "sources": [
                {
                    "chunk_id": h.chunk.id,
                    "score": round(h.score, 4),
                    "text": h.chunk.text[:300],
                    "metadata": {
                        "filename": h.chunk.metadata.filename,
                        "chapter": h.chunk.metadata.chapter,
                        "section": h.chunk.metadata.section,
                        "page_start": h.chunk.metadata.page_start,
                        "page_end": h.chunk.metadata.page_end,
                    },
                }
                for h in self.sources.hits
            ],
            "model": self.model,
            "error": self.error,
        }


class BaseLLM(ABC):
    """Kontrak LLM generator."""

    name: str = "base"

    def __init__(self, config: Optional[LLMConfig | AppConfig] = None) -> None:
        self.config: LLMConfig = (
            config.llm if isinstance(config, AppConfig) else (config or LLMConfig())
        )

    @abstractmethod
    def generate(self, messages: list[dict[str, str]]) -> str:
        """Generate jawaban dari list pesan chat. Return teks jawaban."""
        raise NotImplementedError

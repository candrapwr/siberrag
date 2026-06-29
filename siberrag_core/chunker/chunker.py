"""Re-export chunker API (module wrapper agar tidak bentrok nama)."""

from siberrag_core.chunker.tokenizer import Chunker

__all__ = ["Chunker"]

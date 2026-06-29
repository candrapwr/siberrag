"""Model chunk beserta metadata-nya."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ChunkMetadata(BaseModel):
    """Metadata minimal setiap chunk (sesuai PRD)."""

    id: str = ""
    document_id: str = ""
    filename: str = ""
    page_start: int = 1
    page_end: int = 1
    chapter: str = ""
    section: str = ""
    chunk_index: int = 1
    total_chunk: int = 1
    token_count: int = 0
    word_count: int = 0
    language: str = ""

    # tambahan opsional (tidak melanggar PRD, memperkaya tanpa menghapus)
    block_type: str = "paragraph"
    source_block_index: Optional[int] = None
    extra: dict[str, Any] = Field(default_factory=dict)


class Chunk(BaseModel):
    """Satu chunk hasil chunking semantic block."""

    id: str
    text: str
    metadata: ChunkMetadata

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "metadata": self.metadata.model_dump(),
        }

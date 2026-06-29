"""Base class exporter."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from siberrag_core.config import ExportConfig
from siberrag_core.models.chunk import Chunk
from siberrag_core.models.validation import ChunkValidation


class BaseExporter(ABC):
    """Kontrak exporter: ``export(chunks, validations) -> Path``."""

    #: ekstensi file output (tanpa titik)
    extension: str = "txt"

    def __init__(self, config: Optional[ExportConfig] = None) -> None:
        self.config = config or ExportConfig()

    @abstractmethod
    def export(
        self,
        chunks: list[Chunk],
        validations: list[ChunkValidation],
        output_path: Path,
    ) -> Path:
        """Tulis chunks+validations ke ``output_path``, return path file."""
        raise NotImplementedError

    @staticmethod
    def ensure_parent(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

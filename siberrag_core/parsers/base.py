"""Base class & kontrak untuk semua parser.

Setiap parser mengkonversi file mentah menjadi :class:`DocumentElement` tree
yang seragam, terlepas dari format asli.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from siberrag_core.models.elements import Document


class ParseError(Exception):
    """Dilempar ketika parser gagal memproses dokumen."""


class BaseParser(ABC):
    """Kontrak parser: ``parse(path) -> Document``."""

    #: ekstensi file (tanpa titik) yang didukung parser ini, lowercase
    extensions: tuple[str, ...] = ()
    #: nama parser (untuk logging)
    name: str = "base"

    def __init__(self, config: Optional[Any] = None) -> None:
        self.config = config

    def supports(self, path: Path) -> bool:
        """True bila ekstensi file didukung parser ini."""
        return path.suffix.lower().lstrip(".") in self.extensions

    @abstractmethod
    def parse(self, path: Path, *, filename: Optional[str] = None) -> Document:
        """Parse file menjadi :class:`Document`.

        Wajib diimplementasikan subclass.
        """
        raise NotImplementedError

    # helper bersama
    def _make_document(
        self, root_element: Any, *, path: Path, filename: Optional[str] = None
    ) -> Document:
        from siberrag_core.utils.ids import document_id

        fname = filename or path.name
        return Document(
            root=root_element,
            filename=fname,
            source_path=str(path),
            document_id=document_id(fname),
        )

"""Model elemen dokumen (intermediate representation).

DocumentElement adalah struktur pohon seragam yang dihasilkan oleh semua parser,
sehingga tahap pipeline selanjutnya tidak perlu tahu format asal dokumen.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ElementType(str, Enum):
    """Tipe elemen dokumen yang dikenal pipeline."""

    DOCUMENT = "document"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    BULLET_LIST = "bullet_list"
    NUMBERED_LIST = "numbered_list"
    LIST_ITEM = "list_item"
    TABLE = "table"
    TABLE_ROW = "table_row"
    TABLE_CELL = "table_cell"
    CAPTION = "caption"
    PAGE_BREAK = "page_break"
    IMAGE_CAPTION = "image_caption"


class DocumentElement(BaseModel):
    """Node tunggal dalam tree representasi dokumen.

    Attributes:
        type: tipe elemen (lihat :class:`ElementType`).
        content: teks utama elemen (kosong untuk container seperti DOCUMENT/TABLE).
        level: level heading (1 = H1, 2 = H2, ...). ``None`` untuk non-heading.
        page_start: halaman awal elemen (1-based).
        page_end: halaman akhir elemen (1-based).
        order: urutan kemunculan elemen dalam dokumen (global, 0-based).
        children: elemen turunan (untuk node container).
        extra: metadata tambahan format-spesifik (mis. row/col index, image ref).
    """

    type: ElementType
    content: str = ""
    level: Optional[int] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    order: int = 0
    children: list[DocumentElement] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = {"use_enum_values": False}

    # ----- factory helpers -----
    @classmethod
    def document(cls, *, order: int = 0, **extra: Any) -> DocumentElement:
        return cls(type=ElementType.DOCUMENT, order=order, extra=dict(extra))

    @classmethod
    def heading(
        cls, content: str, *, level: int = 1, page: Optional[int] = None, order: int = 0
    ) -> DocumentElement:
        return cls(
            type=ElementType.HEADING,
            content=content,
            level=level,
            page_start=page,
            page_end=page,
            order=order,
        )

    @classmethod
    def paragraph(
        cls, content: str, *, page: Optional[int] = None, order: int = 0
    ) -> DocumentElement:
        return cls(
            type=ElementType.PARAGRAPH, content=content, page_start=page, page_end=page, order=order
        )

    # ----- traversal -----
    def walk(self) -> list[DocumentElement]:
        """Traverse pre-order: diri sendiri lalu semua turunan (rekursif)."""
        result: list[DocumentElement] = [self]
        for child in self.children:
            result.extend(child.walk())
        return result

    def flat_children(self) -> list[DocumentElement]:
        """Hanya turunan langsung + rekursif (tanpa diri sendiri)."""
        result: list[DocumentElement] = []
        for child in self.children:
            result.extend(child.walk())
        return result

    def add(self, child: DocumentElement) -> DocumentElement:
        """Tambah turunan dan kembalikan self agar bisa di-chain."""
        self.children.append(child)
        return self

    # ----- text -----
    def text(self) -> str:
        """Gabungan seluruh teks elemen ini beserta turunannya."""
        parts: list[str] = []
        if self.content:
            parts.append(self.content)
        for child in self.children:
            parts.append(child.text())
        return "\n".join(p for p in parts if p)

    @property
    def is_heading(self) -> bool:
        return self.type == ElementType.HEADING

    @property
    def is_list(self) -> bool:
        return self.type in (ElementType.BULLET_LIST, ElementType.NUMBERED_LIST)

    @property
    def is_table(self) -> bool:
        return self.type == ElementType.TABLE


class Document(BaseModel):
    """Akar representasi dokumen + metadata level dokumen."""

    root: DocumentElement
    filename: str = ""
    document_id: str = ""
    source_path: str = ""
    total_pages: Optional[int] = None
    language: Optional[str] = None

    def elements(self) -> list[DocumentElement]:
        """Semua elemen dalam dokumen (pre-order)."""
        return self.root.walk()

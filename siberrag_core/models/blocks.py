"""Semantic block - unit dokumen yang utuh secara semantik.

Semantic block adalah hasil pengelompokan elemen mentah: sebuah heading
beserta seluruh isinya menjadi satu block; table/list tetap satu block utuh.
Semantic block adalah dasar pembentukan chunk.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from siberrag_core.models.elements import DocumentElement, ElementType


class SemanticBlock(BaseModel):
    """Satu unit semantik yang utuh.

    Attributes:
        block_type: tipe dominan block (heading, paragraph, list, table, caption).
        title: judul block (heading terdekat), ``None`` bila tanpa heading.
        level: level heading terdekat.
        elements: daftar elemen yang menyusun block ini (berurutan).
        chapter: nama chapter (heading level tertinggi yang melingkupi).
        section: nama section (heading level terdekat sebelum block).
        page_start / page_end: rentang halaman block.
    """

    block_type: str = "paragraph"
    title: Optional[str] = None
    level: Optional[int] = None
    elements: list[DocumentElement] = Field(default_factory=list)
    chapter: Optional[str] = None
    section: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    extra: dict[str, Any] = Field(default_factory=dict)

    def text(self) -> str:
        """Representasi teks rapi dari seluruh elemen block."""
        parts: list[str] = []
        if self.title:
            parts.append(self.title)
        for el in self.elements:
            rendered = _render_element(el)
            if rendered:
                parts.append(rendered)
        return "\n".join(parts)

    def token_count(self, counter) -> int:  # type: ignore[no-untyped-def]
        """Hitung token menggunakan callable ``counter(text) -> int``."""
        return counter(self.text())


def _render_element(el: DocumentElement) -> str:
    """Render satu elemen menjadi string sesuai tipenya."""
    if el.type == ElementType.HEADING:
        return el.content
    if el.type == ElementType.PARAGRAPH:
        return el.content
    if el.type in (ElementType.BULLET_LIST, ElementType.NUMBERED_LIST):
        items: list[str] = []
        for idx, c in enumerate(el.children, start=1):
            if el.type == ElementType.NUMBERED_LIST:
                items.append(f"{idx}. {c.content}")
            else:
                items.append(f"- {c.content}")
        return "\n".join(items)
    if el.type == ElementType.LIST_ITEM:
        return f"- {el.content}"
    if el.type == ElementType.TABLE:
        rows: list[str] = []
        for row in el.children:
            cells = [
                c.content.strip() for c in row.children if c.type == ElementType.TABLE_CELL
            ]
            if cells:
                rows.append("| " + " | ".join(cells) + " |")
        return "\n".join(rows)
    if el.type in (ElementType.CAPTION, ElementType.IMAGE_CAPTION):
        return el.content
    return el.content

"""Helper bersama untuk membangun DocumentElement tree secara konsisten."""

from __future__ import annotations

import re
from typing import Iterable

from siberrag_core.models.elements import DocumentElement, ElementType

# Pola heading markdown: # H1, ## H2, dst. atau heading HTML ringan
_MD_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def heading_level_from_text(text: str) -> int | None:
    """Taksir level heading dari teks (1-6) atau ``None`` bila bukan heading."""
    if not text:
        return None
    m = _MD_HEADING.match(text.strip())
    if m:
        return min(len(m.group(1)), 6)
    return None


def detect_list_type(line: str) -> tuple[ElementType | None, str]:
    """Deteksi apakah baris adalah item list, kembalikan (tipe_list, teks_item)."""
    stripped = line.lstrip()
    # bullet: -, *, +
    if re.match(r"^[-*+]\s+", stripped):
        return ElementType.BULLET_LIST, re.sub(r"^[-*+]\s+", "", stripped)
    # numbered: 1. / 1) / (1)
    if re.match(r"^\d+[.)]\s+", stripped):
        return ElementType.NUMBERED_LIST, re.sub(r"^\d+[.)]\s+", "", stripped)
    return None, line


def group_list_items(lines: Iterable[str]) -> list[DocumentElement]:
    """Kelompokkan baris list berurutan menjadi satu node list."""
    elements: list[DocumentElement] = []
    current_list: DocumentElement | None = None

    def flush() -> None:
        nonlocal current_list
        if current_list is not None and current_list.children:
            elements.append(current_list)
        current_list = None

    for line in lines:
        ltype, item_text = detect_list_type(line)
        if ltype is None:
            flush()
            elements.append(DocumentElement(type=ElementType.PARAGRAPH, content=line.strip()))
            continue
        # lanjut / mulai list baru
        if current_list is None or current_list.type != ltype:
            flush()
            current_list = DocumentElement(type=ltype)
        current_list.children.append(
            DocumentElement(type=ElementType.LIST_ITEM, content=item_text.strip())
        )
    flush()
    return elements

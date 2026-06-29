"""Parser untuk file teks pola (.txt).

Mendeteksi heading (baris KAPITAL / singkat) dan list secara heuristik.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from siberrag_core.models.elements import Document, DocumentElement, ElementType
from siberrag_core.parsers._helpers import detect_list_type, heading_level_from_text
from siberrag_core.parsers.base import BaseParser

_ALL_CAPS_LINE = re.compile(r"^[A-Z0-9 \-\u2013\(\)\.\,:/]{3,}$")


class TxtParser(BaseParser):
    extensions = ("txt",)
    name = "txt"

    def parse(self, path: Path, *, filename: Optional[str] = None) -> Document:
        text = path.read_text(encoding="utf-8", errors="replace")
        root = self._build_tree(text)
        return self._make_document(root, path=path, filename=filename)

    def _build_tree(self, text: str) -> DocumentElement:
        root = DocumentElement.document(order=0)
        lines = text.splitlines()
        order = 0
        page = 1  # TXT tidak punya halaman; asumsikan 1 halaman
        i = 0
        pending_paragraph: list[str] = []

        def flush_paragraph() -> None:
            nonlocal order, pending_paragraph
            if pending_paragraph:
                content = "\n".join(pending_paragraph).strip()
                if content:
                    root.add(
                        DocumentElement.paragraph(content, page=page, order=order)
                    )
                    order += 1
            pending_paragraph = []

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # heading: markdown-style ATX dianggap heading kuat
            level = heading_level_from_text(stripped)
            if level is not None:
                flush_paragraph()
                root.add(DocumentElement.heading(stripped.lstrip("# ").strip(),
                                                 level=level, page=page, order=order))
                order += 1
                i += 1
                continue

            # heading heuristik: baris semua kapital & pendek
            if stripped and len(stripped) <= 80 and _ALL_CAPS_LINE.match(stripped):
                flush_paragraph()
                root.add(DocumentElement.heading(stripped, level=2, page=page, order=order))
                order += 1
                i += 1
                continue

            # list
            ltype, item_text = detect_list_type(stripped)
            if ltype is not None:
                flush_paragraph()
                list_node = DocumentElement(type=ltype, page_start=page, page_end=page, order=order)
                order += 1
                # kumpulkan item berurutan
                while i < len(lines):
                    lt2, it2 = detect_list_type(lines[i].strip())
                    if lt2 is None or lt2 != ltype:
                        break
                    list_node.children.append(
                        DocumentElement(type=ElementType.LIST_ITEM, content=it2.strip())
                    )
                    i += 1
                root.add(list_node)
                continue

            # baris kosong -> akhiri paragraf
            if not stripped:
                flush_paragraph()
                i += 1
                continue

            pending_paragraph.append(stripped)
            i += 1

        flush_paragraph()
        return root

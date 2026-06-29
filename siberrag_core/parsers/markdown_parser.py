"""Parser untuk Markdown (.md/.markdown).

Mempertahankan heading, paragraf, list, tabel pipe, dan caption.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from siberrag_core.models.elements import Document, DocumentElement, ElementType
from siberrag_core.parsers.base import BaseParser

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET = re.compile(r"^\s*[-*+]\s+(.*)$")
_NUMBERED = re.compile(r"^\s*\d+[.)]\s+(.*)$")
_TABLE_ROW = re.compile(r"^\s*\|(.+)\|\s*$")
_TABLE_SEP = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$")
_CAPTION = re.compile(r"^\s*[*_]\s*(Figura|Figure|Tabel|Table|Gambar)\s.*[:：]?\s*[*_]?\s*(.*)$",
                      re.IGNORECASE)


class MarkdownParser(BaseParser):
    extensions = ("md", "markdown")
    name = "markdown"

    def parse(self, path: Path, *, filename: Optional[str] = None) -> Document:
        text = path.read_text(encoding="utf-8", errors="replace")
        root = self._build_tree(text)
        return self._make_document(root, path=path, filename=filename)

    def _build_tree(self, text: str) -> DocumentElement:
        root = DocumentElement.document(order=0)
        lines = text.splitlines()
        order = 0
        page = 1
        i = 0
        para: list[str] = []

        def flush_para() -> None:
            nonlocal order, para
            if para:
                content = "\n".join(para).strip()
                if content:
                    root.add(DocumentElement.paragraph(content, page=page, order=order))
                    order += 1
            para = []

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # heading
            m = _HEADING.match(stripped)
            if m:
                flush_para()
                level = min(len(m.group(1)), 6)
                root.add(DocumentElement.heading(m.group(2).strip(), level=level,
                                                 page=page, order=order))
                order += 1
                i += 1
                continue

            # table
            if _TABLE_ROW.match(line):
                flush_para()
                table = self._parse_table(lines, i, page, order)
                i = table["next"]
                if table["rows"]:
                    root.add(table["element"])
                    order += 1
                continue

            # caption
            cm = _CAPTION.match(stripped)
            if cm:
                flush_para()
                root.add(DocumentElement(type=ElementType.CAPTION, content=stripped,
                                         page_start=page, page_end=page, order=order))
                order += 1
                i += 1
                continue

            # list
            if _BULLET.match(line) or _NUMBERED.match(line):
                flush_para()
                is_bullet = bool(_BULLET.match(line))
                ltype = ElementType.BULLET_LIST if is_bullet else ElementType.NUMBERED_LIST
                list_node = DocumentElement(type=ltype, page_start=page, page_end=page, order=order)
                order += 1
                pat = _BULLET if is_bullet else _NUMBERED
                while i < len(lines) and pat.match(lines[i]):
                    item = pat.match(lines[i]).group(1).strip()
                    list_node.children.append(
                        DocumentElement(type=ElementType.LIST_ITEM, content=item)
                    )
                    i += 1
                root.add(list_node)
                continue

            if not stripped:
                flush_para()
                i += 1
                continue

            para.append(stripped)
            i += 1

        flush_para()
        return root

    def _parse_table(self, lines: list[str], start: int, page: int, order: int) -> dict:
        table = DocumentElement(type=ElementType.TABLE, page_start=page, page_end=page, order=order)
        i = start
        rows = 0
        while i < len(lines):
            line = lines[i]
            if not _TABLE_ROW.match(line):
                break
            # lewati baris pemisah (---|---)
            if _TABLE_SEP.match(line):
                i += 1
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            row = DocumentElement(type=ElementType.TABLE_ROW)
            for c in cells:
                row.children.append(DocumentElement(type=ElementType.TABLE_CELL, content=c))
            table.children.append(row)
            rows += 1
            i += 1
        return {"element": table, "next": i, "rows": rows}

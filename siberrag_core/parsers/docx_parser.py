"""Parser untuk DOCX (.docx) berbasis python-docx.

Mempertahankan heading (Heading 1-6), paragraf, list (numbering/bullet
terdeteksi via style), dan tabel.

Catatan: kita tidak mengandalkan ``CT_P``/``CT_Tbl`` untuk ``isinstance``
karena API internal python-docx berubah-ubah antar versi (namespace prefix).
Sebagai gantinya kita deteksi tipe blok lewat tag XML (``w:p`` / ``w:tbl``)
menggunakan ``docx.oxml.ns.qn``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from siberrag_core.models.elements import Document, DocumentElement, ElementType
from siberrag_core.parsers.base import BaseParser, ParseError

try:
    from docx import Document as DocxDocument  # type: ignore
    from docx.oxml.ns import qn  # type: ignore
    from docx.table import Table as DocxTable  # type: ignore
    from docx.text.paragraph import Paragraph as DocxParagraph  # type: ignore
    _HAS_DOCX = True
except Exception:  # pragma: no cover
    _HAS_DOCX = False


class DocxParser(BaseParser):
    extensions = ("docx",)
    name = "docx"

    def parse(self, path: Path, *, filename: Optional[str] = None) -> Document:
        if not _HAS_DOCX:
            raise ParseError("python-docx tidak tersedia untuk parse DOCX.")
        try:
            docx = DocxDocument(str(path))
        except Exception as exc:
            raise ParseError(f"Gagal parse DOCX {path.name}: {exc}") from exc

        root = DocumentElement.document(order=0)
        order = [0]

        # Iterasi blok (paragraph + table) sesuai urutan dokumen via tag XML.
        for block in self._iter_blocks(docx):
            if isinstance(block, DocxParagraph):
                self._handle_paragraph(block, root, order)
            elif isinstance(block, DocxTable):
                self._handle_table(block, root, order)
        return self._make_document(root, path=path, filename=filename)

    def _handle_paragraph(self, para, parent: DocumentElement, order: list[int]) -> None:
        text = (para.text or "").strip()
        style = (para.style.name or "").lower() if para.style else ""

        # heading
        if style.startswith("heading"):
            level = self._heading_level(style)
            if text:
                parent.add(DocumentElement.heading(text, level=level, page=1, order=order[0]))
                order[0] += 1
            return

        # list (terdeteksi via style 'List' / numbering xml)
        is_list = "list" in style or bool(para._p.find(qn('w:numPr')))
        if is_list and text:
            ltype = ElementType.NUMBERED_LIST if "number" in style else ElementType.BULLET_LIST
            list_node = DocumentElement(type=ltype, page_start=1, page_end=1, order=order[0])
            order[0] += 1
            list_node.children.append(DocumentElement(type=ElementType.LIST_ITEM, content=text))
            parent.add(list_node)
            return

        if text:
            parent.add(DocumentElement.paragraph(text, page=1, order=order[0]))
            order[0] += 1

    def _handle_table(self, table, parent: DocumentElement, order: list[int]) -> None:
        el = DocumentElement(type=ElementType.TABLE, page_start=1, page_end=1, order=order[0])
        order[0] += 1
        for row in table.rows:
            row_el = DocumentElement(type=ElementType.TABLE_ROW)
            for cell in row.cells:
                row_el.children.append(
                    DocumentElement(type=ElementType.TABLE_CELL,
                                    content=(cell.text or "").strip())
                )
            if row_el.children:
                el.children.append(row_el)
        if el.children:
            parent.add(el)

    @staticmethod
    def _heading_level(style: str) -> int:
        digits = "".join(ch for ch in style if ch.isdigit())
        return int(digits) if digits else 1

    @staticmethod
    def _iter_blocks(parent):
        """Iterasi paragraph & table sesuai urutan dalam dokumen (tag-based)."""
        if not _HAS_DOCX:
            return []
        body = parent.element.body
        p_tag = qn('w:p')
        tbl_tag = qn('w:tbl')
        blocks = []
        for child in body.iterchildren():
            if child.tag == p_tag:
                blocks.append(DocxParagraph(child, parent))
            elif child.tag == tbl_tag:
                blocks.append(DocxTable(child, parent))
        return blocks

"""Parser utama berbasis Docling.

Docling adalah parser utama untuk semua format yang didukungnya.
Bila Docling tidak terinstal, registry otomatis fallback ke parser native.

Docling menghasilkan dokumen terstruktur sendiri; kami memetakannya ke
DocumentElement tree yang seragam.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from siberrag_core.models.elements import Document, DocumentElement, ElementType
from siberrag_core.parsers.base import BaseParser, ParseError
from siberrag_core.utils.logging import logger

try:
    from docling.document_converter import DocumentConverter  # type: ignore
    _HAS_DOCLING = True
except Exception:  # pragma: no cover - opsional
    _HAS_DOCLING = False

# ekstensi yang Docling kuasai menurut dokumennya
_DOCLING_EXTENSIONS = ("pdf", "docx", "pptx", "html", "htm", "md", "markdown", "txt",
                       "png", "jpg", "jpeg")


def is_available() -> bool:
    """True bila Docling terinstal dan bisa dipakai."""
    return _HAS_DOCLING


class DoclingParser(BaseParser):
    """Parser berbasis Docling - meng-cover semua format yang didukungnya."""

    extensions = tuple(_DOCLING_EXTENSIONS)
    name = "docling"

    def __init__(self, config: Optional[Any] = None) -> None:
        super().__init__(config)
        self._converter: Optional[Any] = None

    def _get_converter(self):
        if not _HAS_DOCLING:
            raise ParseError("Docling tidak terinstal.")
        if self._converter is None:
            logger.debug("Inisialisasi Docling DocumentConverter...")
            self._converter = DocumentConverter()
        return self._converter

    def parse(self, path: Path, *, filename: Optional[str] = None) -> Document:
        try:
            converter = self._get_converter()
            result = converter.convert(str(path))
            dl_doc = result.document
        except ParseError:
            raise
        except Exception as exc:
            raise ParseError(f"Docling gagal parse {path.name}: {exc}") from exc

        root = self._map_document(dl_doc, path)
        doc = self._make_document(root, path=path, filename=filename)
        if hasattr(dl_doc, "num_pages"):
            try:
                doc.total_pages = int(dl_doc.num_pages())  # type: ignore[misc]
            except Exception:
                pass
        return doc

    def _map_document(self, dl_doc: Any, path: Path) -> DocumentElement:
        """Petakan DoclingDocument ke DocumentElement tree."""
        root = DocumentElement.document(order=0)
        order = [0]

        # Strategi: iterasi elemen dari texts/tables/lists Docling jika ada.
        # Docling menyediakan .texts (list DocItem) dan .tables.
        try:
            items = list(dl_doc.texts)  # type: ignore[attr-defined]
        except Exception:
            items = []
        try:
            tables = list(dl_doc.tables)  # type: ignore[attr-defined]
        except Exception:
            tables = []

        # gabungkan & urutkan sesuai prov order bila tersedia
        combined: list[Any] = []
        for it in items + tables:
            combined.append(it)
        combined.sort(key=lambda x: self._item_order(x))

        for item in combined:
            self._map_item(item, root, order)

        # fallback: bila Docling menghasilkan kosong, gunakan export markdown
        if not root.children:
            md_text = self._safe_export_markdown(dl_doc)
            if md_text:
                root.add(DocumentElement.paragraph(md_text, page=1, order=order[0]))
                order[0] += 1
        return root

    def _item_order(self, item: Any) -> int:
        try:
            prov = item.prov[0] if getattr(item, "prov", None) else None
            if prov is not None:
                return int(getattr(prov, "page_no", 1)) * 100000 + int(
                    getattr(prov, "order", 0))
        except Exception:
            pass
        return 0

    def _map_item(self, item: Any, parent: DocumentElement, order: list[int]) -> None:
        label = getattr(item, "label", "") or ""
        label = str(label).lower()

        # heading
        if "title" in label or "heading" in label or "section" in label:
            text = self._item_text(item)
            level = 1 if "title" == label else self._heading_level_from_label(label)
            if text:
                parent.add(DocumentElement.heading(text, level=level, page=1, order=order[0]))
                order[0] += 1
            return
        # table
        if "table" in label:
            table_el = self._map_table(item, order)
            if table_el is not None:
                parent.add(table_el)
            return
        # list
        if "list" in label:
            ltype = ElementType.NUMBERED_LIST if "ordered" in label else ElementType.BULLET_LIST
            list_node = DocumentElement(type=ltype, page_start=1, page_end=1, order=order[0])
            order[0] += 1
            # item-list di Docling bisa berupa children berlabel list_item
            for child in getattr(item, "children", []) or []:
                t = self._item_text(child)
                if t:
                    list_node.children.append(
                        DocumentElement(type=ElementType.LIST_ITEM, content=t))
            if list_node.children:
                parent.add(list_node)
            return
        if "list_item" in label:
            text = self._item_text(item)
            if text:
                parent.add(DocumentElement.paragraph(f"- {text}", page=1, order=order[0]))
                order[0] += 1
            return
        # caption
        if "caption" in label:
            text = self._item_text(item)
            if text:
                parent.add(DocumentElement(type=ElementType.CAPTION, content=text,
                                           page_start=1, page_end=1, order=order[0]))
                order[0] += 1
            return
        # paragraph default
        text = self._item_text(item)
        if text:
            parent.add(DocumentElement.paragraph(text, page=1, order=order[0]))
            order[0] += 1

    def _map_table(self, item: Any, order: list[int]) -> Optional[DocumentElement]:
        table = DocumentElement(type=ElementType.TABLE, page_start=1, page_end=1, order=order[0])
        order[0] += 1
        try:
            # Docling TableItem.data punya .grid (list of list Cell)
            data = getattr(item, "data", None)
            grid = getattr(data, "grid", None) if data is not None else None
            if grid:
                for row in grid:
                    row_el = DocumentElement(type=ElementType.TABLE_ROW)
                    for cell in row:
                        text = getattr(cell, "text", "") or str(cell)
                        row_el.children.append(
                            DocumentElement(type=ElementType.TABLE_CELL, content=text.strip()))
                    if row_el.children:
                        table.children.append(row_el)
        except Exception:
            pass
        if not table.children:
            text = self._item_text(item)
            if text:
                # fallback: jadikan satu sel
                row = DocumentElement(type=ElementType.TABLE_ROW)
                row.children.append(DocumentElement(type=ElementType.TABLE_CELL, content=text))
                table.children.append(row)
        return table if table.children else None

    @staticmethod
    def _item_text(item: Any) -> str:
        # Docling: text bisa di .text atau .orig
        for attr in ("text", "orig", "body"):
            val = getattr(item, attr, None)
            if isinstance(val, str) and val.strip():
                return val.strip()
        # beberapa item punya method export_text
        for meth in ("export_to_markdown",):
            fn = getattr(item, meth, None)
            if callable(fn):
                try:
                    out = fn()
                    if isinstance(out, str) and out.strip():
                        return out.strip()
                except Exception:
                    pass
        return ""

    @staticmethod
    def _heading_level_from_label(label: str) -> int:
        import re as _re
        digits = _re.findall(r"\d+", label)
        return int(digits[0]) if digits else 2

    @staticmethod
    def _safe_export_markdown(dl_doc: Any) -> str:
        for meth in ("export_to_markdown",):
            fn = getattr(dl_doc, meth, None)
            if callable(fn):
                try:
                    out = fn()
                    if isinstance(out, str):
                        return out.strip()
                except Exception:
                    pass
        return ""

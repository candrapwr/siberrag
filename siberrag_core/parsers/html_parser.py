"""Parser untuk HTML (.html/.htm) berbasis BeautifulSoup4.

Mempertahankan heading (h1-h6), paragraf, list (ul/ol/li), table (tr/td),
caption (figcaption, <caption>), dan image caption (alt).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup, NavigableString, Tag

from siberrag_core.models.elements import Document, DocumentElement, ElementType
from siberrag_core.parsers.base import BaseParser, ParseError


class HtmlParser(BaseParser):
    extensions = ("html", "htm")
    name = "html"

    def parse(self, path: Path, *, filename: Optional[str] = None) -> Document:
        html = path.read_text(encoding="utf-8", errors="replace")
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception as exc:  # pragma: no cover
            raise ParseError(f"Gagal parse HTML {path.name}: {exc}") from exc

        # buang script/style/nav/footer boilerplate
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        root = DocumentElement.document(order=0)
        body = soup.body or soup
        order = [0]  # mutable counter

        for child in body.children:
            self._walk(child, root, order)

        return self._make_document(root, path=path, filename=filename)

    def _walk(self, node, parent: DocumentElement, order: list[int]) -> None:
        if isinstance(node, NavigableString):
            text = str(node).strip()
            if text:
                parent.add(DocumentElement.paragraph(text, page=1, order=order[0]))
                order[0] += 1
            return
        if not isinstance(node, Tag):
            return

        name = node.name.lower()
        # heading
        if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(name[1])
            parent.add(DocumentElement.heading(node.get_text(" ", strip=True), level=level,
                                               page=1, order=order[0]))
            order[0] += 1
            return
        # paragraph
        if name == "p":
            text = node.get_text(" ", strip=True)
            if text:
                parent.add(DocumentElement.paragraph(text, page=1, order=order[0]))
                order[0] += 1
            return
        # lists
        if name in {"ul", "ol"}:
            ltype = ElementType.BULLET_LIST if name == "ul" else ElementType.NUMBERED_LIST
            list_node = DocumentElement(type=ltype, page_start=1, page_end=1, order=order[0])
            order[0] += 1
            for li in node.find_all("li", recursive=False):
                list_node.children.append(
                    DocumentElement(type=ElementType.LIST_ITEM,
                                    content=li.get_text(" ", strip=True))
                )
            if list_node.children:
                parent.add(list_node)
            return
        # table
        if name == "table":
            parent.add(self._parse_table(node, order))
            return
        # caption / figcaption
        if name in {"caption", "figcaption"}:
            parent.add(DocumentElement(type=ElementType.CAPTION,
                                       content=node.get_text(" ", strip=True),
                                       page_start=1, page_end=1, order=order[0]))
            order[0] += 1
            return
        # image caption via alt
        if name == "img":
            alt = (node.get("alt") or "").strip()
            if alt:
                parent.add(DocumentElement(type=ElementType.IMAGE_CAPTION, content=alt,
                                           page_start=1, page_end=1, order=order[0]))
                order[0] += 1
            return
        # lainnya: rekursi ke children
        for child in node.children:
            self._walk(child, parent, order)

    def _parse_table(self, table_tag: Tag, order: list[int]) -> DocumentElement:
        table = DocumentElement(type=ElementType.TABLE, page_start=1, page_end=1, order=order[0])
        order[0] += 1
        for tr in table_tag.find_all("tr"):
            row = DocumentElement(type=ElementType.TABLE_ROW)
            cells = tr.find_all(["td", "th"])
            for cell in cells:
                row.children.append(
                    DocumentElement(type=ElementType.TABLE_CELL,
                                    content=cell.get_text(" ", strip=True))
                )
            if row.children:
                table.children.append(row)
        return table

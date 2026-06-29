"""Hierarchy Builder - bangun tree parent-child dari elemen datar.

Heading menjadi node container; elemen setelah heading (paragraf/list/table)
menjadi children dari heading level terdekat. Contoh:

    Document
    ├── Heading "Bab I" (level 1)
    │   ├── Heading "Pasal 1" (level 2)
    │   │   └── Paragraph ...
    │   └── List ...
    └── Heading "Bab II" (level 1)

Aturan:
- Heading level lebih dalam menjadi child dari heading level lebih dangkal sebelumnya.
- Bila tidak ada heading container, elemen tetap child dari root.
- Struktur tree disimpan kembali ke document.root (children direstrukturisasi).
"""

from __future__ import annotations

from siberrag_core.models.elements import Document, DocumentElement, ElementType
from siberrag_core.utils.logging import logger

# tipe yang menjadi "isi" (bukan container)
_CONTENT_TYPES = {ElementType.PARAGRAPH, ElementType.BULLET_LIST, ElementType.NUMBERED_LIST,
                  ElementType.TABLE, ElementType.CAPTION, ElementType.IMAGE_CAPTION}


class HierarchyBuilder:
    """Bangun struktur tree dari urutan elemen datar."""

    def build(self, document: Document) -> Document:
        root = document.root
        flat = list(root.children)
        if not flat:
            return document

        # root baru: hanya berisi struktur yang sudah di-nest
        new_root = DocumentElement.document(order=0)
        # stack: list (level, node) - node heading terbuka per level
        stack: list[tuple[int, DocumentElement]] = []

        def current_parent(level: int) -> DocumentElement:
            """Parent untuk heading dengan level tertentu."""
            while stack and stack[-1][0] >= level:
                stack.pop()
            if stack:
                return stack[-1][1]
            return new_root

        for el in flat:
            if el.type == ElementType.HEADING and el.level is not None:
                level = el.level
                # parent = heading level lebih dangkal terakhir
                parent = current_parent(level)
                # bersihkan children heading (heading murni container)
                el.children = []
                parent.add(el)
                stack.append((level, el))
            else:
                # elemen isi -> attach ke heading terdekat atau root
                if stack:
                    stack[-1][1].add(el)
                else:
                    new_root.add(el)

        document.root = new_root
        logger.debug(f"Hierarchy: {self._count_headings(new_root)} heading, "
                     f"{len(new_root.walk())} elemen total.")
        return document

    @staticmethod
    def _count_headings(node: DocumentElement) -> int:
        return sum(1 for el in node.walk() if el.type == ElementType.HEADING)

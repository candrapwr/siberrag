"""Semantic Block Builder - kelompokkan elemen menjadi block utuh.

Aturan (sesuai PRD):
- Heading beserta isinya tetap satu block (heading + content langsung).
- Table tetap utuh (satu block = satu table, tidak pernah dipecah).
- Bullet list / numbered list tetap utuh.
- Caption tetap bersama objeknya.
- Tidak pernah memotong kalimat.

Catatan: bila sebuah heading punya banyak sub-heading, kita buat satu block
PER heading leaf + isinya, agar block tidak terlalu besar dan chunking tetap
fleksibel. Heading level tinggi (chapter) disimpan sebagai metadata (chapter)
di setiap block turunannya, tidak dipecah menjadi block terpisah.

Output: list[SemanticBlock] berurutan sesuai posisi dokumen.
"""

from __future__ import annotations

from siberrag_core.models.blocks import SemanticBlock
from siberrag_core.models.elements import Document, DocumentElement, ElementType
from siberrag_core.utils.logging import logger

# tipe elemen yang menjadi "objek utuh" tersendiri
_ATOMIC_TYPES = {ElementType.TABLE, ElementType.BULLET_LIST, ElementType.NUMBERED_LIST,
                 ElementType.CAPTION, ElementType.IMAGE_CAPTION}


class SemanticBuilder:
    """Bangun semantic block dari tree dokumen (hasil HierarchyBuilder)."""

    def build(self, document: Document) -> list[SemanticBlock]:
        blocks: list[SemanticBlock] = []
        # chapter/section context saat traverse
        context: dict[str, str | None] = {"chapter": None, "section": None}

        for top in document.root.children:
            self._walk(top, blocks, context)

        logger.debug(f"Semantic: {len(blocks)} block dibuat dari {document.filename}.")
        return blocks

    def _walk(
        self,
        element: DocumentElement,
        blocks: list[SemanticBlock],
        context: dict[str, str | None],
    ) -> None:
        if element.type == ElementType.HEADING and element.level is not None:
            # update context
            title = element.content.strip()
            if element.level <= 1:
                context["chapter"] = title
                context["section"] = title
            else:
                context["section"] = title

            # heading + isi langsung (non-heading) jadi satu block
            own_content: list[DocumentElement] = []
            sub_headings: list[DocumentElement] = []
            for child in element.children:
                if child.type == ElementType.HEADING:
                    sub_headings.append(child)
                else:
                    own_content.append(child)

            block = SemanticBlock(
                block_type="heading",
                title=title,
                level=element.level,
                elements=own_content,
                chapter=context.get("chapter"),
                section=title,
                page_start=element.page_start,
                page_end=element.page_end,
            )
            # bila heading tanpa content & ada sub-heading, jangan buat block kosong
            if own_content or not sub_headings:
                blocks.append(block)

            # rekursi ke sub-heading (context sudah di-update)
            for sub in sub_headings:
                self._walk(sub, blocks, context)
            return

        # elemen non-heading di level top -> block sendiri
        if element.type in _ATOMIC_TYPES:
            blocks.append(SemanticBlock(
                block_type=element.type.value,
                elements=[element],
                chapter=context.get("chapter"),
                section=context.get("section"),
                page_start=element.page_start,
                page_end=element.page_end,
            ))
            return

        # paragraf lepas
        if element.content.strip():
            blocks.append(SemanticBlock(
                block_type="paragraph",
                elements=[element],
                chapter=context.get("chapter"),
                section=context.get("section"),
                page_start=element.page_start,
                page_end=element.page_end,
            ))

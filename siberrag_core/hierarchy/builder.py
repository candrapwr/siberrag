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

Selain itu, builder mendeteksi heading berbasis POLA TEKS untuk dokumen regulasi
Indonesia (BAB / Pasal / Bagian / Bab / Lampiran) yang mungkin tidak terdeteksi
oleh parser berbasis font-size. Ini penting agar chunker bisa memisahkan konten
lintas-pasal/bab.
"""

from __future__ import annotations

import re

from siberrag_core.models.elements import Document, DocumentElement, ElementType
from siberrag_core.utils.logging import logger

# tipe yang menjadi "isi" (bukan container)
_CONTENT_TYPES = {ElementType.PARAGRAPH, ElementType.BULLET_LIST, ElementType.NUMBERED_LIST,
                  ElementType.TABLE, ElementType.CAPTION, ElementType.IMAGE_CAPTION}

# Pola heading regulasi Indonesia.
# Setiap tuple: (regex, level). Pertama yang match dipakai.
_HEADING_PATTERNS: list[tuple[re.Pattern[str], int]] = [
    # BAB (level 1) - "BAB I", "BAB XIV", "BAB XVI"
    (re.compile(r"^\s*BAB\s+([IVXLCDM]+)\b", re.IGNORECASE), 1),
    # Lampiran / Aturan Peralihan (level 1)
    (re.compile(r"^\s*(LAMPIRAN|ATURAN\s+PERALIHAN)\b", re.IGNORECASE), 1),
    # Bagian (level 2) - "Bagian Kedua", "Bagian Ke-3"
    (re.compile(r"^\s*BAGIAN\b", re.IGNORECASE), 2),
    # Pasal angka (level 2) - "Pasal 1", "Pasal 27", "Pasal 33 ayat 2"
    (re.compile(r"^\s*PASAL\s+(\d+)\b", re.IGNORECASE), 2),
    # Pasal romawi (level 2) - "Pasal I", "Pasal II" (aturan peralihan)
    (re.compile(r"^\s*PASAL\s+([IVXLCDM]+)\b", re.IGNORECASE), 2),
    # Bab biasa (level 1) - "Bab I", "Bab II" (lowercase style)
    (re.compile(r"^\s*BAB\s+([IVXLCDM]+)\b"), 1),
]


def _detect_heading_from_text(text: str) -> tuple[bool, int]:
    """Cek apakah teks merupakan heading regulasi. Return (is_heading, level).

    Hanya baris/baris pertama yang diperiksa. Bila teks multi-baris, hanya
    baris pertama yang relevan (heading biasanya satu baris).
    """
    if not text or not text.strip():
        return False, 0
    # ambil baris pertama non-kosong
    first_line = text.strip().split("\n", 1)[0].strip()
    # heading regulasi biasanya pendek (<= 80 char pada baris pertama)
    if len(first_line) > 80:
        return False, 0
    for pattern, level in _HEADING_PATTERNS:
        if pattern.match(first_line):
            return True, level
    return False, 0


class HierarchyBuilder:
    """Bangun struktur tree dari urutan elemen datar."""

    def build(self, document: Document) -> Document:
        root = document.root
        flat = list(root.children)
        if not flat:
            return document

        # Tahap 1: deteksi heading berbasis pola teks untuk paragraf yang
        # sebenarnya adalah heading regulasi (BAB/Pasal) tapi tidak terdeteksi
        # parser. Ini penting untuk dokumen regulasi Indonesia.
        flat = self._promote_pattern_headings(flat)

        # Tahap 2: bangun tree dari elemen yang sudah diperbaiki
        new_root = DocumentElement.document(order=0)
        stack: list[tuple[int, DocumentElement]] = []

        def current_parent(level: int) -> DocumentElement:
            while stack and stack[-1][0] >= level:
                stack.pop()
            if stack:
                return stack[-1][1]
            return new_root

        for el in flat:
            if el.type == ElementType.HEADING and el.level is not None:
                level = el.level
                parent = current_parent(level)
                el.children = []
                parent.add(el)
                stack.append((level, el))
            else:
                if stack:
                    stack[-1][1].add(el)
                else:
                    new_root.add(el)

        document.root = new_root
        logger.debug(f"Hierarchy: {self._count_headings(new_root)} heading, "
                     f"{len(new_root.walk())} elemen total.")
        return document

    @staticmethod
    def _promote_pattern_headings(elements: list[DocumentElement]) -> list[DocumentElement]:
        """Ubah paragraf yang mengandung baris heading regulasi menjadi HEADING.

        Penting: paragraf PDF seringkali menggabung banyak pasal/bab dalam
        satu elemen panjang (mis. "Pasal 29\\n(1)... \\nBAB XII\\n..."). Method
        ini MEMECAH paragraf tersebut di setiap baris yang match pola heading,
        lalu mempromosikan baris tsb menjadi HEADING.

        Hasilnya: setiap BAB/Pasal menjadi heading terpisah + isi mengikuti.
        """
        result: list[DocumentElement] = []
        for el in elements:
            if el.type != ElementType.PARAGRAPH or not el.content:
                result.append(el)
                continue
            # pecah paragraf di baris-baris yang match pola heading
            split_els = HierarchyBuilder._split_paragraph_by_headings(el)
            result.extend(split_els)
        return result

    @staticmethod
    def _split_paragraph_by_headings(el: DocumentElement) -> list[DocumentElement]:
        """Pecah satu paragraf menjadi heading + paragraf sesuai pola baris."""
        lines = el.content.split("\n")
        out: list[DocumentElement] = []
        buf: list[str] = []  # akumulator baris non-heading
        page = el.page_start

        def flush_buf() -> None:
            if buf:
                text = "\n".join(buf).strip()
                if text:
                    out.append(DocumentElement(
                        type=ElementType.PARAGRAPH, content=text,
                        page_start=page, page_end=el.page_end, order=el.order,
                    ))
                buf.clear()

        for line in lines:
            stripped = line.strip()
            is_heading, level = _detect_heading_from_text(stripped)
            if is_heading:
                flush_buf()
                out.append(DocumentElement(
                    type=ElementType.HEADING, content=stripped, level=level,
                    page_start=page, page_end=el.page_end, order=el.order,
                ))
            else:
                buf.append(line)
        flush_buf()
        return out if out else [el]


    @staticmethod
    def _count_headings(node: DocumentElement) -> int:
        return sum(1 for el in node.walk() if el.type == ElementType.HEADING)


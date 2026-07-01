"""Parser untuk PDF (.pdf) berbasis PyMuPDF (fitz).

Mempertahankan struktur per halaman: heading (font-size besar/bold), paragraf,
list, dan table dasar (via heuristik kolom). Setiap halaman ditandai dengan
PAGE_BREAK agar metadata page_start/page_end akurat.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from siberrag_core.models.elements import Document, DocumentElement, ElementType
from siberrag_core.parsers._helpers import detect_list_type
from siberrag_core.parsers.base import BaseParser, ParseError

try:
    import fitz  # PyMuPDF  # type: ignore
    _HAS_PYMUPDF = True
except Exception:  # pragma: no cover
    _HAS_PYMUPDF = False


class PdfParser(BaseParser):
    extensions = ("pdf",)
    name = "pdf"

    def parse(self, path: Path, *, filename: Optional[str] = None) -> Document:
        if not _HAS_PYMUPDF:
            raise ParseError("PyMuPDF (fitz) tidak tersedia untuk parse PDF.")
        try:
            doc = fitz.open(str(path))  # type: ignore[union-attr]
        except Exception as exc:
            raise ParseError(f"Gagal parse PDF {path.name}: {exc}") from exc

        root = DocumentElement.document(order=0)
        total_pages = doc.page_count
        order = [0]

        # progress reporter (bila ada, dari pipeline) untuk progress bar per halaman
        progress = getattr(self, "_progress", None)

        # kumpulkan info font untuk threshold heading
        for page_index in range(total_pages):
            page = doc.load_page(page_index)
            page_no = page_index + 1
            self._process_page(page, page_no, root, order)
            if progress is not None:
                progress.update(page_no, total_pages, f"Parsing halaman {page_no}/{total_pages}")

        doc.close()

        result = self._make_document(root, path=path, filename=filename)
        result.total_pages = total_pages
        return result

    def _process_page(self, page, page_no: int, root: DocumentElement, order: list[int]) -> None:
        """Ekstrak blok teks dari satu halaman."""
        blocks = page.get_text("dict", sort=True).get("blocks", [])
        # hitung median font-size untuk deteksi heading
        sizes: list[float] = []
        for b in blocks:
            for line in b.get("lines", []):
                for span in line.get("spans", []):
                    sizes.append(float(span.get("size", 0)))
        median_size = sorted(sizes)[len(sizes) // 2] if sizes else 12.0

        para_buf: list[str] = []

        def flush() -> None:
            nonlocal para_buf
            if para_buf:
                text = "\n".join(para_buf).strip()
                if text:
                    root.add(DocumentElement.paragraph(text, page=page_no, order=order[0]))
                    order[0] += 1
            para_buf = []

        for block in blocks:
            if block.get("type", 0) != 0:  # 0 = text block
                continue
            block_text_parts: list[tuple[str, float, int]] = []
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                line_text = "".join(s.get("text", "") for s in spans).strip()
                if not line_text:
                    continue
                max_size = max(float(s.get("size", 0)) for s in spans)
                bold = any("bold" in str(s.get("font", "")).lower() for s in spans)
                block_text_parts.append((line_text, max_size, 1 if bold else 0))

            for line_text, size, bold in block_text_parts:
                # heading: font jelas lebih besar atau bold+kapital.
                # PENTING: baris yang berisi HANYA angka (mis. "249") adalah
                # nomor halaman jurnal, BUKAN heading -> lewati sebagai page number.
                if size >= median_size * 1.25 and len(line_text) <= 120 \
                        and not _is_pure_page_number(line_text):
                    flush()
                    level = 1 if size >= median_size * 1.6 else 2
                    root.add(DocumentElement.heading(line_text, level=level,
                                                     page=page_no, order=order[0]))
                    order[0] += 1
                    continue
                # nomor halaman murni -> bukan konten, lewati (jangan jadi paragraf)
                if _is_pure_page_number(line_text):
                    continue
                # list
                ltype, item_text = detect_list_type(line_text)
                if ltype is not None:
                    flush()
                    list_node = DocumentElement(type=ltype, page_start=page_no,
                                                page_end=page_no, order=order[0])
                    order[0] += 1
                    list_node.children.append(
                        DocumentElement(type=ElementType.LIST_ITEM, content=item_text.strip())
                    )
                    root.add(list_node)
                    continue
                para_buf.append(line_text)

        flush()
        # PAGE_BREAK setelah tiap halaman (kecuali halaman terakhir)
        root.add(DocumentElement(type=ElementType.PAGE_BREAK, page_start=page_no,
                                 page_end=page_no, order=order[0]))
        order[0] += 1


def _is_pure_page_number(text: str) -> bool:
    """True bila teks hanyalah nomor halaman (angka murni, mungkin dgn dash/spasi).

    Dipakai untuk menghindari false-positive heading dari nomor halaman jurnal
    seperti '249', '- 250 -', yang ter-extract dengan font besar.
    """
    import re
    stripped = text.strip()
    if not stripped:
        return False
    # angka murni, opsional dengan dash/titik/spasi di sekelilingnya
    return bool(re.fullmatch(r"[-–—\s.\d]*\d+[-–—\s.]*", stripped))


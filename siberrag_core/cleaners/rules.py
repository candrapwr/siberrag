"""Implementasi 6 cleaning rule (sesuai PRD).

1. RepeatedHeaderRule   - hapus header berulang lintas halaman
2. RepeatedFooterRule   - hapus footer berulang lintas halaman
3. PageNumberRule       - hapus nomor halaman
4. WhitespaceRule       - collapse whitespace berlebih
5. EmptyLineRule        - batasi baris kosong berlebih
6. BrokenOCRRule        - perbaiki artifact OCR + invalid unicode

Semua rule mempertahankan struktur: tidak menyentuh tipe elemen, hanya
membersihkan teks konten, dan menghapus elemen yang jadi kosong SETELAH
pembersihan (kecuali container).
"""

from __future__ import annotations

from collections import Counter

from siberrag_core.cleaners.base import CleaningRule
from siberrag_core.models.elements import DocumentElement, ElementType
from siberrag_core.utils.text import (
    collapse_blank_lines,
    collapse_whitespace,
    fix_broken_ocr,
    is_blank,
    looks_like_page_number,
    normalize_unicode,
    strip_page_number_markers,
)

# tipe elemen yang TIDAK boleh dihapus walau kosong (container/struktural)
_KEEP_TYPES = {ElementType.DOCUMENT, ElementType.TABLE, ElementType.TABLE_ROW}


def _walk_clean(element: DocumentElement, fn) -> None:
    """Terapkan ``fn(content) -> str`` ke field ``content`` elemen + turunannya."""
    if element.content:
        element.content = fn(element.content)
    for child in element.children:
        _walk_clean(child, fn)


def _prune_empty(element: DocumentElement) -> bool:
    """Hapus turunan yang kosong (rekursif). Return True bila elemen ini juga kosong."""
    # proses children dulu
    kept: list[DocumentElement] = []
    for child in element.children:
        if _prune_empty(child):
            continue  # child kosong, buang
        kept.append(child)
    element.children = kept

    # elemen container tetap dipertahankan walau tanpa teks
    if element.type in _KEEP_TYPES:
        return False
    # page_break tetap dipertahankan (penanda halaman)
    if element.type == ElementType.PAGE_BREAK:
        return False
    # list/table dengan children ada tetap dipertahankan
    if element.children:
        return False
    return is_blank(element.content)


class NormalizeUnicodeRule(CleaningRule):
    name = "normalize_unicode"

    def apply(self, element: DocumentElement) -> DocumentElement:
        _walk_clean(element, normalize_unicode)
        _prune_empty(element)
        return element


class WhitespaceRule(CleaningRule):
    name = "collapse_whitespace"

    def apply(self, element: DocumentElement) -> DocumentElement:
        _walk_clean(element, collapse_whitespace)
        _prune_empty(element)
        return element


class EmptyLineRule(CleaningRule):
    name = "collapse_blank_lines"

    def apply(self, element: DocumentElement) -> DocumentElement:
        _walk_clean(element, collapse_blank_lines)
        _prune_empty(element)
        return element


class PageNumberRule(CleaningRule):
    """Hapus nomor halaman: baris yang berisi hanya nomor halaman & marker inline.

    PENTING: nomor halaman hanya muncul sebagai baris tersendiri dalam teks
    paragraf mengalir. Rule ini HANYA diterapkan ke elemen PARAGRAPH, tidak
    pernah ke table cell / list item / heading / caption (angka di sana adalah
    konten sah, mis. nomor baris tabel, nomor urut list).
    """

    name = "remove_page_numbers"

    def apply(self, element: DocumentElement) -> DocumentElement:
        self._remove_page_number_lines(element)
        _walk_clean(element, strip_page_number_markers)
        _walk_clean(element, lambda s: s.strip())
        _prune_empty(element)
        return element

    def _remove_page_number_lines(self, element: DocumentElement) -> None:
        # HANYA elemen PARAGRAPH yang boleh dihapus baris page-number-nya.
        # Table cell, list item, heading, caption = angka adalah konten sah.
        if element.content and element.type == ElementType.PARAGRAPH:
            lines = element.content.splitlines()
            # deteksi page number: harus baris tunggal yang isinya murni nomor halaman
            kept = [ln for ln in lines
                    if not (ln.strip() and looks_like_page_number(ln)
                            and _is_standalone_page_number_line(ln))]
            if len(kept) != len(lines):
                element.content = "\n".join(kept).strip()
        for child in element.children:
            self._remove_page_number_lines(child)


def _is_standalone_page_number_line(line: str) -> bool:
    """True bila baris SELURUHNYA adalah nomor halaman (bukan kalimat bersama).

    Mencegah false positive: baris seperti '1. Siber adalah...' adalah list item,
    BUKAN page number, walau looks_like_page_number mungkin True.
    """
    stripped = line.strip()
    # baris yang merupakan list item jangan dihapus
    import re
    if re.match(r"^\d+[.)]\s+\S", stripped):
        return False
    # baris pendek murni angka / '- 12 -' / 'Page 3 of 10'
    return looks_like_page_number(stripped)


class BrokenOCRRule(CleaningRule):
    name = "fix_broken_ocr"

    def apply(self, element: DocumentElement) -> DocumentElement:
        _walk_clean(element, fix_broken_ocr)
        _prune_empty(element)
        return element


class RepeatedHeaderFooterRule(CleaningRule):
    """Hapus header/footer berulang lintas halaman.

    Strategi: pisahkan dokumen menjadi segmen per halaman (dibatasi PAGE_BREAK).
    Baris yang muncul di >50% halaman DAN berada di 2 baris pertama/terakhir
    segmen dianggap header/footer boilerplate dan dihapus.
    """

    name = "remove_repeated_header_footer"

    def __init__(self, *, is_header: bool = True, threshold: float = 0.5) -> None:
        self.is_header = is_header
        self.threshold = threshold

    def apply(self, element: DocumentElement) -> DocumentElement:
        segments = self._split_by_pages(element)
        if len(segments) < 2:
            return element  # tidak ada multi-halaman, lewati

        boilerplate = self._find_boilerplate(segments)
        if not boilerplate:
            return element

        # hapus baris boilerplate dari seluruh elemen paragraf
        self._strip_boilerplate(element, boilerplate)
        _prune_empty(element)
        return element

    def _split_by_pages(self, element: DocumentElement) -> list[list[str]]:
        """Kumpulkan baris teks per halaman (dipisah PAGE_BREAK)."""
        flat = element.flat_children()
        segments: list[list[str]] = []
        current: list[str] = []
        for el in flat:
            if el.type == ElementType.PAGE_BREAK:
                if current:
                    segments.append(current)
                current = []
                continue
            if el.content:
                current.extend(el.content.splitlines())
        if current:
            segments.append(current)
        return segments

    def _find_boilerplate(self, segments: list[list[str]]) -> set[str]:
        from collections import Counter
        counter: Counter[str] = Counter()
        for seg in segments:
            if not seg:
                continue
            # ambil 2 baris pertama (header) atau 2 baris terakhir (footer)
            lines = seg[:2] if self.is_header else seg[-2:]
            for ln in lines:
                ln = ln.strip()
                if ln and len(ln) < 200:  # abaikan teks panjang (bukan boilerplate)
                    counter[ln] += 1
        threshold_count = max(2, int(len(segments) * self.threshold))
        return {ln for ln, cnt in counter.items() if cnt >= threshold_count}

    def _strip_boilerplate(self, element: DocumentElement, boilerplate: set[str]) -> None:
        if element.content and element.type not in _KEEP_TYPES:
            lines = element.content.splitlines()
            kept = [ln for ln in lines if ln.strip() not in boilerplate]
            element.content = "\n".join(kept).strip()
        for child in element.children:
            self._strip_boilerplate(child, boilerplate)


class RepeatedHeadingRule(CleaningRule):
    """Hapus heading duplikat berulang lintas halaman (running header/footer jurnal).

    Pada jurnal/dokumen multi-halaman, sering ada header berulang seperti
    "Volume 10 Nomor 2, Agustus 2021" yang muncul di tiap halaman dan salah
    terdeteksi sebagai heading. Rule ini mendeteksi heading yang muncul berulang
    (>= threshold halaman) dan menghapus SEMUA kemunculannya kecuali yang pertama,
    karena heading asli seharusnya unik per dokumen.
    """

    name = "remove_repeated_heading"

    def __init__(self, threshold: int = 3) -> None:
        # heading dianggap boilerplate bila muncul di >= threshold halaman
        self.threshold = threshold

    def apply(self, element: DocumentElement) -> DocumentElement:
        headings = [e for e in element.walk() if e.type == ElementType.HEADING]
        if len(headings) < self.threshold:
            return element

        # hitung frekuensi tiap heading (normalisasi spasi)
        from collections import Counter
        import re as _re
        counter: Counter[str] = Counter()
        for h in headings:
            norm = _re.sub(r"\s+", " ", h.content.strip()).lower()
            if norm:
                counter[norm] += 1

        # boilerplate = heading yang muncul berulang >= threshold
        boilerplate = {norm for norm, cnt in counter.items() if cnt >= self.threshold}
        if not boilerplate:
            return element

        # tandai heading boilerplate untuk dihapus (kecuali kemunculan pertamanya)
        seen: set[str] = set()
        to_remove: list[DocumentElement] = []
        for h in headings:
            norm = _re.sub(r"\s+", " ", h.content.strip()).lower()
            if norm in boilerplate:
                if norm in seen:
                    to_remove.append(h)
                else:
                    seen.add(norm)

        # hapus dari tree
        for h in to_remove:
            _remove_from_tree(element, h)
        _prune_empty(element)
        return element


def _remove_from_tree(root: DocumentElement, target: DocumentElement) -> bool:
    """Hapus ``target`` dari tree mulai dari ``root``. Return True bila ditemukan."""
    for i, child in enumerate(root.children):
        if child is target:
            del root.children[i]
            return True
        if _remove_from_tree(child, target):
            return True
    return False

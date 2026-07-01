"""Helper pemrosesan teks: sentence split, whitespace, normalisasi unicode."""

from __future__ import annotations

import re
import unicodedata

# Pola akhir kalimat yang umum (titik, ?, !, diikuti spasi/kapital/akhir).
# Dipakai untuk split kalimat tanpa memotong di singkatan umum.
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'\(])")
_WHITESPACE = re.compile(r"[ \t]+")
_MULTI_NEWLINE = re.compile(r"\n{3,}")
# Pola nomor halaman: HARUS ada prefix "page"/"halaman"/"hal." agar tidak
# false-positive pada teks valid seperti "15 dari 15" atau "baris 1-15 dari 15".
_PAGE_NUM = re.compile(
    r"\b(?:halaman|hal\.?|page)\s+\d+\s*(?:dari|of)\s*\d+\b",
    re.IGNORECASE,
)
_BROKEN_OCR = re.compile(r"[ \t][\uFFFD\u25A1\u2610]")  # replacement/empty box setelah spasi


def normalize_unicode(text: str) -> str:
    """Normalisasi NFC + hapus karakter kontrol tak terlihat."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    # hapus karakter kontrol kecuali newline/tab
    text = "".join(
        ch for ch in text
        if ch in ("\n", "\t") or unicodedata.category(ch) != "Cc"
    )
    return text


def collapse_whitespace(text: str) -> str:
    """Sederhanakan spasi/tab berlebih menjadi satu spasi."""
    if not text:
        return ""
    text = _WHITESPACE.sub(" ", text)
    return text


def collapse_blank_lines(text: str, max_consecutive: int = 2) -> str:
    """Batasi jumlah baris kosong berurutan."""
    if not text:
        return ""
    # baris kosong = hanya whitespace
    text = re.sub(r"(?:[ \t]*\n){%d,}" % (max_consecutive + 1), "\n" * max_consecutive, text)
    return text.strip("\n")


def looks_like_page_number(line: str) -> bool:
    """Deteksi apakah sebuah baris kemungkinan nomor halaman."""
    stripped = line.strip()
    if not stripped:
        return False
    # hanya angka / "Page X" / "Hal X" / "- X -" / "x of y"
    if stripped.isdigit():
        return True
    if re.fullmatch(r"[-–—\s]*\d+[-–—\s]*", stripped):
        return True
    if _PAGE_NUM.fullmatch(stripped):
        return True
    return False


def strip_page_number_markers(text: str) -> str:
    """Hapus marker nomor halaman inline seperti 'Page 3 of 12'."""
    return _PAGE_NUM.sub("", text)


def fix_broken_ocr(text: str) -> str:
    """Hapus karakter replacement/box OCR yang muncul di tengah kata."""
    if not text:
        return ""
    # hapus replacement char
    text = text.replace("\uFFFD", "")
    # ganti empty box dengan spasi
    text = text.replace("\u25A1", " ").replace("\u2610", " ")
    # hapus artifact OCR umum: huruf terulang sangat banyak (>=7 kali) akibat scan
    # (tetap mempertahankan kata normal seperti "aaaaaaa" yang sah pendek)
    text = re.sub(r"([a-zA-Z])\1{6,}", r"\1", text)
    return text


def split_sentences(text: str) -> list[str]:
    """Pecah teks menjadi kalimat tanpa memotong singkatan umum."""
    if not text or not text.strip():
        return []
    # lindungi singkatan umum dari split salah
    protected = text
    placeholders: dict[str, str] = {}
    for i, abbr in enumerate(["Mr.", "Mrs.", "Dr.", "No.", "Ps.", "Vs.", "Inc.",
                              "Ltd.", "dll.", "dsb.", "dst.", "hlm.", "tgl."]):
        token = f" __ABBR{i}__ "
        if abbr in protected:
            placeholders[token] = abbr
            protected = protected.replace(abbr, token)
    parts = _SENTENCE_BOUNDARY.split(protected)
    sentences: list[str] = []
    for p in parts:
        for token, abbr in placeholders.items():
            p = p.replace(token, abbr)
        p = p.strip()
        if p:
            sentences.append(p)
    return sentences


def count_words(text: str) -> int:
    """Jumlah kata."""
    if not text:
        return 0
    return len(text.split())


def is_blank(text: str) -> bool:
    """True bila teks hanya whitespace."""
    return not text or not text.strip()

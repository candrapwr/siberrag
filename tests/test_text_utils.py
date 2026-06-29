"""Test helper teks."""

from siberrag_core.utils.text import (
    collapse_blank_lines,
    collapse_whitespace,
    fix_broken_ocr,
    is_blank,
    looks_like_page_number,
    normalize_unicode,
    split_sentences,
    strip_page_number_markers,
)


def test_collapse_whitespace():
    assert collapse_whitespace("a    b\t\tc") == "a b c"
    assert collapse_whitespace("") == ""


def test_collapse_blank_lines():
    text = "a\n\n\n\nb\n\n\nc"
    result = collapse_blank_lines(text)
    assert result.count("\n\n\n") == 0


def test_normalize_unicode():
    # control character dihilangkan, newline dipertahankan
    text = "a\x00b\x07c\nd"
    out = normalize_unicode(text)
    assert "\x00" not in out
    assert "\n" in out


def test_looks_like_page_number():
    assert looks_like_page_number("12")
    assert looks_like_page_number("- 12 -")
    assert looks_like_page_number("Page 3 of 10")
    assert looks_like_page_number("halaman 5 dari 20")
    assert not looks_like_page_number("Pasal 1 menjelaskan definisi.")


def test_strip_page_number_markers():
    assert "Page 3 of 10" not in strip_page_number_markers("Lihat Page 3 of 10 di sini")


def test_fix_broken_ocr():
    assert "\uFFFD" not in fix_broken_ocr("aaa\uFFFDbbb")
    # kata normal pendek tidak dirusak
    assert fix_broken_ocr("hello") == "hello"
    # artifact OCR (huruf terulang sangat banyak) diringankan
    assert fix_broken_ocr("aaaaaaaaaaabc") == "abc"


def test_split_sentences_basic():
    text = "Ini kalimat pertama. Ini kalimat kedua! Dan ketiga?"
    sents = split_sentences(text)
    assert len(sents) == 3


def test_split_sentences_keeps_abbreviation():
    text = "Dr. Andi bekerja di sana. Beliau baik."
    sents = split_sentences(text)
    # "Dr." tidak memicu split
    assert len(sents) == 2


def test_is_blank():
    assert is_blank("   \n\t  ")
    assert not is_blank("x")

"""Test cleaning rules."""

from siberrag_core.cleaners.rules import (
    BrokenOCRRule,
    EmptyLineRule,
    NormalizeUnicodeRule,
    PageNumberRule,
    WhitespaceRule,
)
from siberrag_core.models.elements import DocumentElement, ElementType


def test_whitespace_rule():
    root = DocumentElement.document()
    root.add(DocumentElement.paragraph("a    b\t\tc"))
    WhitespaceRule().apply(root)
    assert root.children[0].content == "a b c"


def test_page_number_rule():
    root = DocumentElement.document()
    root.add(DocumentElement.paragraph("Page 3 of 10"))
    root.add(DocumentElement.paragraph("Pasal 1 berbunyi demikian."))
    PageNumberRule().apply(root)
    # page-number-only paragraph terhapus
    assert len(root.children) == 1
    assert root.children[0].content == "Pasal 1 berbunyi demikian."


def test_page_number_rule_keeps_table_cells_with_numbers():
    """Angka di table cell (No/1/2/3) TIDAK boleh dihapus sebagai page number."""
    root = DocumentElement.document()
    table = DocumentElement(type=ElementType.TABLE)
    row = DocumentElement(type=ElementType.TABLE_ROW)
    for cell in ["No", "1", "2", "3", "Akses data"]:
        row.add(DocumentElement(type=ElementType.TABLE_CELL, content=cell))
    table.add(row)
    root.add(table)
    PageNumberRule().apply(root)
    cells = [c.content for c in table.children[0].children]
    # SEMUA cell utuh, termasuk angka 1/2/3
    assert cells == ["No", "1", "2", "3", "Akses data"]


def test_page_number_rule_keeps_list_items_with_numbers():
    """List item dengan nomor (1. Siber...) TIDAK boleh dihapus."""
    root = DocumentElement.document()
    lst = DocumentElement(type=ElementType.NUMBERED_LIST)
    lst.add(DocumentElement(type=ElementType.LIST_ITEM, content="Siber adalah ruang komunikasi."))
    lst.add(DocumentElement(type=ElementType.LIST_ITEM, content="Data adalah rekaman informasi."))
    root.add(lst)
    PageNumberRule().apply(root)
    assert len(root.children) == 1  # list tetap ada
    assert len(root.children[0].children) == 2  # kedua item utuh


def test_page_number_rule_keeps_paragraph_list_items():
    """Paragraf '1. Siber adalah...' bukan page number, tidak boleh dihapus."""
    root = DocumentElement.document()
    root.add(DocumentElement.paragraph("1. Siber adalah ruang komunikasi elektronik yang saling terhubung."))
    PageNumberRule().apply(root)
    assert root.children[0].content.startswith("1. Siber")  # tetap utuh


def test_broken_ocr_rule():
    root = DocumentElement.document()
    root.add(DocumentElement.paragraph("kata\uFFFDrusak"))
    BrokenOCRRule().apply(root)
    assert root.children[0].content == "katarusak"


def test_normalize_unicode_rule():
    root = DocumentElement.document()
    root.add(DocumentElement.paragraph("a\x00b"))
    NormalizeUnicodeRule().apply(root)
    assert "\x00" not in root.children[0].content


def test_empty_line_rule_preserves_structure():
    """Heading/table tidak boleh dihapus meski kosong setelah cleaning."""
    root = DocumentElement.document()
    table = DocumentElement(type=ElementType.TABLE)
    row = DocumentElement(type=ElementType.TABLE_ROW)
    row.add(DocumentElement(type=ElementType.TABLE_CELL, content=""))
    table.add(row)
    root.add(table)
    EmptyLineRule().apply(root)
    # table tetap ada (container)
    assert any(e.type == ElementType.TABLE for e in root.children)


def test_prune_keeps_list_with_items():
    """List dengan item tidak boleh dihapus."""
    from siberrag_core.cleaners.rules import _prune_empty
    root = DocumentElement.document()
    lst = DocumentElement(type=ElementType.BULLET_LIST)
    lst.add(DocumentElement(type=ElementType.LIST_ITEM, content="item"))
    root.add(lst)
    _prune_empty(root)
    assert root.children  # list tetap ada

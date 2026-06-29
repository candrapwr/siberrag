"""Test parser per format."""

from pathlib import Path

import pytest

from siberrag_core.models.elements import ElementType
from siberrag_core.parsers.markdown_parser import MarkdownParser
from siberrag_core.parsers.registry import ParserRegistry, is_supported
from siberrag_core.parsers.txt_parser import TxtParser


def test_is_supported():
    assert is_supported(Path("a.pdf"))
    assert is_supported(Path("a.docx"))
    assert is_supported(Path("a.md"))
    assert not is_supported(Path("a.exe"))


def test_txt_parser(sample_txt_file):
    parser = TxtParser()
    doc = parser.parse(sample_txt_file)
    types = {e.type for e in doc.root.flat_children()}
    # ada heading (ALL CAPS), list, paragraph
    assert ElementType.HEADING in types
    assert ElementType.BULLET_LIST in types
    assert ElementType.PARAGRAPH in types


def test_markdown_parser(sample_md_file):
    parser = MarkdownParser()
    doc = parser.parse(sample_md_file)
    elements = doc.root.flat_children()
    headings = [e for e in elements if e.type == ElementType.HEADING]
    tables = [e for e in elements if e.type == ElementType.TABLE]
    lists = [e for e in elements if e.type == ElementType.BULLET_LIST]
    assert len(headings) >= 4  # Bab I, Pasal 1, Pasal 2, Bab II
    assert len(tables) == 1
    assert tables[0].children  # ada row
    assert len(lists) >= 1


def test_registry_native_fallback(sample_md_file):
    """Registry strategi 'native' harus pakai parser MD native."""
    from siberrag_core.config import ParsingConfig
    cfg = ParsingConfig(parser="native")
    registry = ParserRegistry(cfg)
    doc = registry.parse(sample_md_file)
    assert doc.filename == sample_md_file.name
    assert doc.document_id


def test_registry_unsupported_extension(tmp_path):
    from siberrag_core.parsers.base import ParseError
    p = tmp_path / "a.xyz"
    p.write_text("data", encoding="utf-8")
    registry = ParserRegistry()
    with pytest.raises(ParseError):
        registry.parse(p)

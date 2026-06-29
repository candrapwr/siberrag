"""Test hierarchy & semantic builder."""

from siberrag_core.hierarchy.builder import HierarchyBuilder
from siberrag_core.models.elements import Document, DocumentElement, ElementType
from siberrag_core.semantic.builder import SemanticBuilder


def test_hierarchy_nests_headings(simple_document):
    doc = HierarchyBuilder().build(simple_document)
    root = doc.root
    # Top-level hanya heading level 1 (Bab I, Bab II)
    top_headings = [e for e in root.children if e.type == ElementType.HEADING]
    assert len(top_headings) == 2
    assert all(e.level == 1 for e in top_headings)

    # Bab I berisi paragraf + heading Pasal 1 (level 2)
    bab_i = top_headings[0]
    assert any(e.type == ElementType.PARAGRAPH for e in bab_i.children)
    assert any(e.type == ElementType.HEADING and e.level == 2 for e in bab_i.children)


def test_hierarchy_no_heading(simple_document):
    """Tanpa heading, elemen tetap child root."""
    root = DocumentElement.document()
    root.add(DocumentElement.paragraph("paragraf saja"))
    doc = Document(root=root, filename="x", document_id="d")
    result = HierarchyBuilder().build(doc)
    assert len(result.root.children) == 1
    assert result.root.children[0].type == ElementType.PARAGRAPH


def test_semantic_builder_produces_blocks(simple_document):
    doc = HierarchyBuilder().build(simple_document)
    blocks = SemanticBuilder().build(doc)
    assert len(blocks) > 0
    # setiap block punya block_type
    for b in blocks:
        assert b.block_type
    # minimal ada block heading
    assert any(b.block_type == "heading" for b in blocks)


def test_semantic_block_chapter_section(simple_document):
    doc = HierarchyBuilder().build(simple_document)
    blocks = SemanticBuilder().build(doc)
    # block di bawah Bab II harus chapter == "Bab II"
    bab_ii_blocks = [b for b in blocks if b.chapter == "Bab II"]
    assert bab_ii_blocks

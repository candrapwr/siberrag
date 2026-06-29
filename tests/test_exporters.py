"""Test exporters."""

import json
from pathlib import Path

import pytest

from siberrag_core.config import ExportConfig
from siberrag_core.exporters.json_exporter import JsonExporter
from siberrag_core.exporters.jsonl_exporter import JsonlExporter
from siberrag_core.exporters.markdown_exporter import MarkdownExporter
from siberrag_core.exporters.registry import get_exporter
from siberrag_core.models.chunk import Chunk, ChunkMetadata
from siberrag_core.models.validation import ChunkValidation, Severity, ValidationFinding


def _sample_chunks() -> list[Chunk]:
    return [
        Chunk(
            id="doc_c0000",
            text="Chunk pertama berisi teks penting.",
            metadata=ChunkMetadata(
                id="doc_c0000", document_id="doc", filename="f.md",
                page_start=1, page_end=1, chapter="Bab I", section="Pasal 1",
                chunk_index=0, total_chunk=2, token_count=10, word_count=5,
                language="id",
            ),
        ),
        Chunk(
            id="doc_c0001",
            text="Chunk kedua berisi teks lain.",
            metadata=ChunkMetadata(
                id="doc_c0001", document_id="doc", filename="f.md",
                page_start=1, page_end=2, chapter="Bab I", section="Pasal 2",
                chunk_index=1, total_chunk=2, token_count=8, word_count=4,
                language="id",
            ),
        ),
    ]


def _sample_validations() -> list[ChunkValidation]:
    return [
        ChunkValidation(chunk_id="doc_c0000", quality_score=95),
        ChunkValidation(
            chunk_id="doc_c0001", quality_score=80,
            findings=[ValidationFinding(code="UNDERSIZED", severity=Severity.WARNING,
                                        message="Chunk 8 token.")],
        ),
    ]


def test_json_exporter(tmp_path):
    out = tmp_path / "out.json"
    JsonExporter().export(_sample_chunks(), _sample_validations(), out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data) == 2
    assert data[0]["id"] == "doc_c0000"
    assert "metadata" in data[0]
    assert "validation" in data[0]
    assert data[1]["validation"]["quality_score"] == 80


def test_jsonl_exporter(tmp_path):
    out = tmp_path / "out.jsonl"
    JsonlExporter().export(_sample_chunks(), _sample_validations(), out)
    lines = [l for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["id"] == "doc_c0000"


def test_markdown_exporter(tmp_path):
    out = tmp_path / "out.md"
    MarkdownExporter().export(_sample_chunks(), _sample_validations(), out)
    md = out.read_text(encoding="utf-8")
    assert "# SiberRAG" in md
    assert "Chunk 1" in md
    assert "doc_c0000" not in md or "Bab I" in md  # konten atau metadata muncul


def test_registry_get_exporter():
    assert get_exporter(format="json").__class__.__name__ == "JsonExporter"
    assert get_exporter(format="jsonl").__class__.__name__ == "JsonlExporter"
    assert get_exporter(format="markdown").__class__.__name__ == "MarkdownExporter"
    with pytest.raises(ValueError):
        get_exporter(format="xml")

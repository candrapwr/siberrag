"""Test validator & metadata builder."""

from siberrag_core.chunker.tokenizer import Chunker
from siberrag_core.config import ChunkingConfig, ValidationConfig
from siberrag_core.metadata.builder import MetadataBuilder
from siberrag_core.models.blocks import SemanticBlock
from siberrag_core.models.elements import DocumentElement, ElementType
from siberrag_core.models.chunk import Chunk, ChunkMetadata
from siberrag_core.validator.validator import ChunkValidator


def _chunk(text: str, tokens: int = 500) -> Chunk:
    return Chunk(
        id="doc_c0000",
        text=text,
        metadata=ChunkMetadata(
            id="doc_c0000", document_id="doc", filename="f.txt",
            page_start=1, page_end=1, chapter="C", section="S",
            chunk_index=0, total_chunk=1, token_count=tokens,
            word_count=len(text.split()), language="id",
        ),
    )


def test_validator_ideal_size_no_warning():
    cfg = ValidationConfig()
    v = ChunkValidator(cfg)
    chunk = _chunk("Kalimat lengkap dengan titik akhir.", tokens=500)
    result = v.validate(chunk)
    assert result.quality_score >= 90
    assert not result.warnings


def test_validator_oversized_warning():
    cfg = ValidationConfig()
    v = ChunkValidator(cfg)
    chunk = _chunk("Teks panjang.", tokens=800)
    result = v.validate(chunk)
    codes = [f.code for f in result.findings]
    assert "OVERSIZED" in codes
    assert result.quality_score < 100


def test_validator_undersized_warning():
    cfg = ValidationConfig()
    v = ChunkValidator(cfg)
    chunk = _chunk("Pendek.", tokens=100)
    result = v.validate(chunk)
    codes = [f.code for f in result.findings]
    assert "UNDERSIZED" in codes


def test_validator_duplicate_detection():
    cfg = ValidationConfig(flag_duplicate=True)
    v = ChunkValidator(cfg)
    text = "Teks duplikat yang sama persis untuk diuji."
    c1 = _chunk(text)
    c2 = _chunk(text)
    results = v.validate_all([c1, c2])
    # c2 harus ditandai duplicate
    codes2 = [f.code for f in results[1].findings]
    assert "DUPLICATE" in codes2


def test_metadata_builder_fills_language():
    builder = MetadataBuilder()
    chunk = Chunk(
        id="x", text="Ini teks Indonesia untuk uji deteksi bahasa yang sederhana.",
        metadata=ChunkMetadata(id="x", document_id="d", filename="f.txt",
                               chunk_index=0, total_chunk=1, token_count=10),
    )
    out = builder.enrich([chunk], sample_text=chunk.text)
    # token_count dihitung ulang > 0
    assert out[0].metadata.token_count > 0
    assert out[0].metadata.word_count > 0


def test_validator_disabled_returns_perfect():
    cfg = ValidationConfig(enabled=False)
    v = ChunkValidator(cfg)
    result = v.validate(_chunk("apa saja", tokens=10))
    assert result.quality_score == 100
    assert result.findings == []

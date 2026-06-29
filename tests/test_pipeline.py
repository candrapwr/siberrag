"""Test pipeline end-to-end."""

from pathlib import Path

from siberrag_core.config import AppConfig, ChunkingConfig, ExportConfig
from siberrag_core.pipeline import Pipeline


def test_pipeline_md_file(sample_md_file, tmp_path):
    cfg = AppConfig()
    cfg.chunking = ChunkingConfig(target_tokens=50, min_tokens=10, max_tokens=120,
                                  overlap_tokens=15)
    cfg.export = ExportConfig(format="jsonl", output_dir=str(tmp_path))
    pipeline = Pipeline(cfg)
    result = pipeline.run(sample_md_file)

    assert result.files
    fr = result.files[0]
    assert fr.error is None
    assert fr.chunks
    assert fr.output_path.exists()
    assert fr.output_path.suffix == ".jsonl"
    assert result.total_chunks == len(fr.chunks)

    # setiap chunk punya metadata lengkap
    for c in fr.chunks:
        assert c.metadata.document_id
        assert c.metadata.filename == sample_md_file.name
        assert c.metadata.total_chunk == len(fr.chunks)


def test_pipeline_directory(sample_md_file, sample_txt_file, tmp_path):
    """Direktori dengan beberapa file."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "a.md").write_text(sample_md_file.read_text(encoding="utf-8"),
                                   encoding="utf-8")
    (docs_dir / "b.txt").write_text(sample_txt_file.read_text(encoding="utf-8"),
                                    encoding="utf-8")
    out_dir = tmp_path / "out"

    cfg = AppConfig()
    cfg.chunking = ChunkingConfig(target_tokens=40, min_tokens=5, max_tokens=100,
                                  overlap_tokens=10)
    cfg.export = ExportConfig(format="json", output_dir=str(out_dir), pretty_json=False)
    pipeline = Pipeline(cfg)
    result = pipeline.run(docs_dir)

    assert len(result.files) == 2
    assert all(fr.error is None for fr in result.files)
    assert result.total_chunks > 0
    # file output untuk masing-masing
    outputs = {fr.output_path.name for fr in result.files}
    assert "a.json" in outputs
    assert "b.json" in outputs


def test_pipeline_markdown_export(sample_md_file, tmp_path):
    cfg = AppConfig()
    cfg.chunking = ChunkingConfig(target_tokens=60, min_tokens=10, max_tokens=150,
                                  overlap_tokens=20)
    cfg.export = ExportConfig(format="markdown", output_dir=str(tmp_path))
    pipeline = Pipeline(cfg)
    result = pipeline.run(sample_md_file)
    fr = result.files[0]
    assert fr.output_path.suffix == ".md"
    content = fr.output_path.read_text(encoding="utf-8")
    assert "SiberRAG" in content


def test_pipeline_empty_dir(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    pipeline = Pipeline()
    result = pipeline.run(empty)
    assert result.files == []
    assert result.total_chunks == 0

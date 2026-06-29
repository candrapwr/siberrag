"""Test IndexPipeline + QueryPipeline end-to-end (dengan mock embedder/LLM).

Ini test integrasi paling penting: verifikasi seluruh RAG flow bekerja
dari dokumen mentah -> chunk -> embed -> store -> query -> retrieve -> generate,
semua tanpa API/model asli (pakai mock).
"""

import pytest

from siberrag_core.config import AppConfig

try:
    import chromadb  # noqa: F401
    _HAS_CHROMA = True
except Exception:
    _HAS_CHROMA = False

skip_no_chroma = pytest.mark.skipif(not _HAS_CHROMA, reason="chromadb tidak terpasang")


def _make_config(tmp_path) -> AppConfig:
    """Config test dengan vectorstore di tmp_path + chunk target kecil."""
    cfg = AppConfig()
    cfg.vector_db = cfg.vector_db.model_copy(update={
        "collection": "test_pipeline", "path": str(tmp_path / "vs"),
    })
    cfg.chunking = cfg.chunking.model_copy(update={
        "target_tokens": 30, "min_tokens": 5, "max_tokens": 80,
        "respect_heading_boundary": False, "prepend_context": False,
    })
    return cfg


@skip_no_chroma
def test_index_pipeline_indexes_document(tmp_path, mock_embedder):
    """IndexPipeline harus chunk dokumen -> embed -> store."""
    from siberrag_core.index_pipeline import IndexPipeline

    # buat dokumen sample
    doc_path = tmp_path / "sample.txt"
    doc_path.write_text(
        "Kucing adalah hewan mamalia. Kucing suka makan ikan dan tidur sepanjang hari.\n"
        "Anjing adalah hewan setia. Anjing bisa diajak bermain dan berburu.\n",
        encoding="utf-8",
    )

    cfg = _make_config(tmp_path)
    pipeline = IndexPipeline(cfg)
    # inject mock embedder
    pipeline.embedder = mock_embedder

    result = pipeline.index(doc_path)
    assert result.total_indexed > 0
    assert pipeline.store.count() > 0


@skip_no_chroma
def test_index_pipeline_stats(tmp_path, mock_embedder):
    """stats() harus return info collection & jumlah chunk."""
    from siberrag_core.index_pipeline import IndexPipeline

    doc_path = tmp_path / "s.txt"
    doc_path.write_text("Teks pendek untuk diuji indexing pipeline.", encoding="utf-8")
    cfg = _make_config(tmp_path)
    pipeline = IndexPipeline(cfg)
    pipeline.embedder = mock_embedder
    pipeline.index(doc_path)

    stats = pipeline.stats()
    assert stats["collection"] == "test_pipeline"
    assert stats["total_chunks"] > 0
    assert "collections" in stats


@skip_no_chroma
def test_query_pipeline_end_to_end(tmp_path, mock_embedder, mock_llm):
    """QueryPipeline penuh: index -> query -> answer + sources."""
    from siberrag_core.index_pipeline import IndexPipeline
    from siberrag_core.query_pipeline import QueryPipeline

    # index dokumen tentang hewan
    doc_path = tmp_path / "hewan.txt"
    doc_path.write_text(
        "Kucing adalah hewan mamalia yang suka memakan ikan.\n"
        "Anjing adalah hewan peliharaan yang setia pada tuannya.\n",
        encoding="utf-8",
    )
    cfg = _make_config(tmp_path)
    # index dulu
    ip = IndexPipeline(cfg)
    ip.embedder = mock_embedder
    ip.index(doc_path)
    assert ip.store.count() >= 1

    # query
    qp = QueryPipeline(cfg, retriever=None, llm=mock_llm)
    qp.embedder = mock_embedder
    qp.store = ip.store
    qp.retriever.embedder = mock_embedder
    qp.retriever.store = ip.store

    answer = qp.query("hewan apa yang suka makan ikan?")
    assert answer.question == "hewan apa yang suka makan ikan?"
    assert len(answer.sources) > 0
    # top source harus tentang kucing
    assert "kucing" in answer.sources.hits[0].chunk.text.lower()
    # LLM dipanggil & jawaban diisi
    assert "MOCK ANSWER" in answer.text
    assert not answer.is_error


@skip_no_chroma
def test_query_pipeline_no_context_fallback(tmp_path, mock_embedder, mock_llm):
    """Query tanpa konteks relevan harus fallback gracefully."""
    from siberrag_core.index_pipeline import IndexPipeline
    from siberrag_core.query_pipeline import QueryPipeline

    doc_path = tmp_path / "teknologi.txt"
    doc_path.write_text("Python adalah bahasa pemrograman untuk data science.", encoding="utf-8")
    cfg = _make_config(tmp_path)
    # threshold tinggi agar query tak relevan return kosong
    cfg.retrieval = cfg.retrieval.model_copy(update={"score_threshold": 0.999})

    ip = IndexPipeline(cfg)
    ip.embedder = mock_embedder
    ip.index(doc_path)

    qp = QueryPipeline(cfg, llm=mock_llm)
    qp.embedder = mock_embedder
    qp.store = ip.store
    qp.retriever.embedder = mock_embedder
    qp.retriever.store = ip.store

    # query ttg kucing (tidak relevan dgn dok Python)
    answer = qp.query("cara merawat kucing persia")
    # bila tidak ada context -> fallback message, LLM tidak dipanggil
    assert "tidak ditemukan" in answer.text.lower() or len(answer.sources) == 0


@skip_no_chroma
def test_query_pipeline_retrieve_only(tmp_path, mock_embedder):
    """retrieve_only harus return context tanpa panggil LLM."""
    from siberrag_core.index_pipeline import IndexPipeline
    from siberrag_core.query_pipeline import QueryPipeline

    doc_path = tmp_path / "hewan.txt"
    doc_path.write_text("Kucing suka makan ikan. Anjing setia pada tuannya.", encoding="utf-8")
    cfg = _make_config(tmp_path)
    ip = IndexPipeline(cfg)
    ip.embedder = mock_embedder
    ip.index(doc_path)

    # QueryPipeline tanpa LLM (lazy, tapi retrieve_only tidak butuh)
    qp = QueryPipeline(cfg)
    qp.embedder = mock_embedder
    qp.store = ip.store
    qp.retriever.embedder = mock_embedder
    qp.retriever.store = ip.store

    results = qp.retrieve_only("kucing ikan")
    assert len(results) >= 1

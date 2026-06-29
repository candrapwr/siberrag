"""Test retriever + IndexPipeline + QueryPipeline (end-to-end dgn mock)."""

import pytest

from siberrag_core.config import AppConfig, RetrievalConfig
from siberrag_core.retrieval.retriever import Retriever

try:
    import chromadb  # noqa: F401
    _HAS_CHROMA = True
except Exception:
    _HAS_CHROMA = False

skip_no_chroma = pytest.mark.skipif(not _HAS_CHROMA, reason="chromadb tidak terpasang")


@skip_no_chroma
def test_retriever_returns_relevant(tmp_path, sample_chunks, mock_embedder):
    """Retriever harus embed query + search + return chunk relevan."""
    cfg = AppConfig()
    cfg.vector_db = cfg.vector_db.model_copy(update={
        "collection": "test_ret", "path": str(tmp_path / "vs")
    })
    # index manual
    from siberrag_core.vectorstore.registry import get_vectorstore
    store = get_vectorstore(cfg)
    store.upsert(sample_chunks, mock_embedder.embed_batch([c.text for c in sample_chunks]))
    retriever = Retriever(cfg, embedder=mock_embedder, store=store)
    results = retriever.retrieve("kucing makan ikan", top_k=2)
    assert len(results) >= 1
    # chunk kucing relevan
    assert results.hits[0].chunk.id == "doc_c0000"


@skip_no_chroma
def test_retriever_score_threshold_filter(tmp_path, sample_chunks, mock_embedder):
    """Score threshold tinggi harus filter chunk kurang relevan."""
    cfg = AppConfig()
    cfg.vector_db = cfg.vector_db.model_copy(update={
        "collection": "test_thresh", "path": str(tmp_path / "vs")
    })
    cfg.retrieval = RetrievalConfig(top_k=5, score_threshold=0.99)
    from siberrag_core.vectorstore.registry import get_vectorstore
    store = get_vectorstore(cfg)
    store.upsert(sample_chunks, mock_embedder.embed_batch([c.text for c in sample_chunks]))
    retriever = Retriever(cfg, embedder=mock_embedder, store=store)
    # threshold 0.99 sangat tinggi -> kemungkinan hasil sedikit/kosong
    results = retriever.retrieve("kucing", top_k=5, score_threshold=0.99)
    # semua hit harus >= 0.99
    for h in results.hits:
        assert h.score >= 0.99


@skip_no_chroma
def test_retriever_filter_by_document(tmp_path, sample_chunks, mock_embedder):
    """Filter document_id harus scope hasil."""
    cfg = AppConfig()
    cfg.vector_db = cfg.vector_db.model_copy(update={
        "collection": "test_docfilter", "path": str(tmp_path / "vs")
    })
    from siberrag_core.vectorstore.registry import get_vectorstore
    store = get_vectorstore(cfg)
    store.upsert(sample_chunks, mock_embedder.embed_batch([c.text for c in sample_chunks]))
    retriever = Retriever(cfg, embedder=mock_embedder, store=store)
    results = retriever.retrieve("hewan", document_id="doc")
    # hanya chunk document_id="doc" (kucing, anjing)
    for h in results.hits:
        assert h.chunk.metadata.document_id == "doc"

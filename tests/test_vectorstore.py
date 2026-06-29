"""Test vectorstore layer (ChromaDB)."""

import pytest

from siberrag_core.config import AppConfig, VectorDBConfig
from siberrag_core.vectorstore.base import SearchResults
from siberrag_core.vectorstore.registry import get_vectorstore, _BACKENDS

try:
    import chromadb  # noqa: F401
    _HAS_CHROMA = True
except Exception:
    _HAS_CHROMA = False

skip_no_chroma = pytest.mark.skipif(not _HAS_CHROMA, reason="chromadb tidak terpasang")


def test_registry_backends():
    assert "chroma" in _BACKENDS


def test_registry_unknown_backend_raises():
    with pytest.raises(ValueError):
        get_vectorstore(VectorDBConfig(), backend="unknown_db")


@skip_no_chroma
def test_chroma_upsert_and_count(tmp_path, sample_chunks, mock_embedder):
    """Upsert chunk harus tersimpan & count bertambah."""
    cfg = VectorDBConfig(collection="test_upsert", path=str(tmp_path / "vs"))
    store = get_vectorstore(cfg)
    embeddings = mock_embedder.embed_batch([c.text for c in sample_chunks])
    n = store.upsert(sample_chunks, embeddings)
    assert n == 3
    assert store.count() == 3


@skip_no_chroma
def test_chroma_search_returns_relevant(tmp_path, sample_chunks, mock_embedder):
    """Search harus mengembalikan chunk paling relevan di top-1."""
    cfg = VectorDBConfig(collection="test_search", path=str(tmp_path / "vs"))
    store = get_vectorstore(cfg)
    embeddings = mock_embedder.embed_batch([c.text for c in sample_chunks])
    store.upsert(sample_chunks, embeddings)
    # query tentang kucing -> chunk kucing harus di top
    q_emb = mock_embedder.embed("hewan kucing makan ikan")
    results = store.search(q_emb, top_k=2)
    assert len(results) == 2
    # top-1 harus chunk kucing (doc_c0000)
    assert results.hits[0].chunk.id == "doc_c0000"
    assert results.hits[0].score > 0


@skip_no_chroma
def test_chroma_search_empty_store(tmp_path, mock_embedder):
    """Search di store kosong harus return hasil kosong, bukan error."""
    cfg = VectorDBConfig(collection="test_empty", path=str(tmp_path / "vs"))
    store = get_vectorstore(cfg)
    q_emb = mock_embedder.embed("apa saja")
    results = store.search(q_emb, top_k=5)
    assert isinstance(results, SearchResults)
    assert len(results) == 0


@skip_no_chroma
def test_chroma_delete(tmp_path, sample_chunks, mock_embedder):
    """Delete chunk harus mengurangi count."""
    cfg = VectorDBConfig(collection="test_delete", path=str(tmp_path / "vs"))
    store = get_vectorstore(cfg)
    embeddings = mock_embedder.embed_batch([c.text for c in sample_chunks])
    store.upsert(sample_chunks, embeddings)
    assert store.count() == 3
    n = store.delete(["doc_c0000", "doc_c0001"])
    assert n == 2
    assert store.count() == 1


@skip_no_chroma
def test_chroma_list_collections(tmp_path, sample_chunks, mock_embedder):
    """List collections harus include collection yg dibuat."""
    cfg = VectorDBConfig(collection="test_list", path=str(tmp_path / "vs"))
    store = get_vectorstore(cfg)
    store.upsert(sample_chunks, mock_embedder.embed_batch([c.text for c in sample_chunks]))
    cols = store.list_collections()
    assert "test_list" in cols


@skip_no_chroma
def test_chroma_upsert_idempotent(tmp_path, sample_chunks, mock_embedder):
    """Upsert chunk yang sama dua kali tidak menggandakan count."""
    cfg = VectorDBConfig(collection="test_idem", path=str(tmp_path / "vs"))
    store = get_vectorstore(cfg)
    embeddings = mock_embedder.embed_batch([c.text for c in sample_chunks])
    store.upsert(sample_chunks, embeddings)
    store.upsert(sample_chunks, embeddings)  # kedua kali
    assert store.count() == 3  # tetap 3, bukan 6


@skip_no_chroma
def test_chroma_metadata_preserved(tmp_path, sample_chunks, mock_embedder):
    """Metadata chunk (chapter/section) harus tersimpan & bisa di-retrieve."""
    cfg = VectorDBConfig(collection="test_meta", path=str(tmp_path / "vs"))
    store = get_vectorstore(cfg)
    embeddings = mock_embedder.embed_batch([c.text for c in sample_chunks])
    store.upsert(sample_chunks, embeddings)
    q_emb = mock_embedder.embed("kucing ikan")
    results = store.search(q_emb, top_k=1)
    assert results.hits[0].chunk.metadata.chapter == "Mamalia"
    assert results.hits[0].chunk.metadata.section == "Kucing"
    assert results.hits[0].chunk.metadata.filename == "hewan.txt"


@skip_no_chroma
def test_chroma_search_with_filter(tmp_path, sample_chunks, mock_embedder):
    """Filter by document_id harus scope pencarian."""
    cfg = VectorDBConfig(collection="test_filter", path=str(tmp_path / "vs"))
    store = get_vectorstore(cfg)
    embeddings = mock_embedder.embed_batch([c.text for c in sample_chunks])
    store.upsert(sample_chunks, embeddings)
    # filter ke document_id="doc" -> chunk kucing/anjing (bukan python)
    q_emb = mock_embedder.embed("hewan peliharaan")
    results = store.search(q_emb, top_k=5, where={"document_id": "doc"})
    ids = {h.chunk.id for h in results.hits}
    assert "doc_c0002" not in ids  # python (tekno.txt) ter-filter

"""Test embeddings layer (base, registry, provider availability)."""

import pytest

from siberrag_core.config import EmbeddingConfig
from siberrag_core.embeddings.base import BaseEmbedder, EmbeddingError
from siberrag_core.embeddings.local import LocalEmbedder, is_available as local_available
from siberrag_core.embeddings.openai_emb import OpenAIEmbedder
from siberrag_core.embeddings.registry import get_embedder


def test_registry_providers():
    """Registry harus punya local, openai, custom."""
    from siberrag_core.embeddings.registry import _PROVIDERS
    assert "local" in _PROVIDERS
    assert "openai" in _PROVIDERS
    assert "custom" in _PROVIDERS


def test_registry_unknown_provider_raises():
    with pytest.raises(EmbeddingError):
        get_embedder(EmbeddingConfig(provider="local"), provider="unknown_xyz")


def test_local_embedder_availability():
    """LocalEmbedder.is_available harus konsisten dgn import."""
    # is_available boolean, tidak raise
    avail = local_available()
    assert isinstance(avail, bool)


def test_local_embedder_raises_if_not_available(monkeypatch):
    """Bila sentence-transformers tidak ada, LocalEmbedder harus raise jelas."""
    import siberrag_core.embeddings.local as local_mod
    monkeypatch.setattr(local_mod, "_HAS_ST", False)
    with pytest.raises(EmbeddingError, match="sentence-transformers"):
        LocalEmbedder()


def test_openai_embedder_raises_without_api_key(monkeypatch):
    """OpenAIEmbedder harus raise jelas bila tidak ada API key."""
    import siberrag_core.embeddings.openai_emb as oai_mod
    monkeypatch.setattr(oai_mod, "_HAS_OPENAI", True)
    # patch OpenAI client agar tidak benar2 konek
    monkeypatch.setattr(oai_mod, "OpenAI", lambda **kw: None, raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cfg = EmbeddingConfig(provider="openai", api_key="", api_base="https://api.openai.com/v1")
    with pytest.raises(EmbeddingError, match="API key"):
        OpenAIEmbedder(cfg)


def test_openai_embedder_local_endpoint_no_key_ok(monkeypatch):
    """Endpoint lokal (localhost) tanpa API key harus tetap bisa (dummy key)."""
    import siberrag_core.embeddings.openai_emb as oai_mod
    monkeypatch.setattr(oai_mod, "_HAS_OPENAI", True)
    monkeypatch.setattr(oai_mod, "OpenAI", lambda **kw: type("C", (), {})())
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cfg = EmbeddingConfig(provider="custom", api_key="", api_base="http://localhost:11434/v1")
    emb = OpenAIEmbedder(cfg)  # tidak raise
    assert emb.name == "openai"


def test_get_embedder_from_app_config():
    """get_embedder harus accept AppConfig."""
    from siberrag_core.config import AppConfig
    cfg = AppConfig()
    cfg.embedding.provider = "local"
    # bila sentence-transformers ada, ini sukses; bila tidak, raise EmbeddingError
    try:
        emb = get_embedder(cfg)
        assert isinstance(emb, BaseEmbedder)
    except EmbeddingError:
        pass  # ok bila deps tidak terpasang


def test_mock_embedder_deterministic(mock_embedder):
    """Mock embedder harus deterministik: teks sama -> vektor sama."""
    v1 = mock_embedder.embed("kucing makan ikan")
    v2 = mock_embedder.embed("kucing makan ikan")
    assert v1 == v2
    assert len(v1) == mock_embedder.dimension
    assert mock_embedder.dimension == 64


def test_mock_embedder_batch(mock_embedder):
    vecs = mock_embedder.embed_batch(["kucing", "anjing", "ikan"])
    assert len(vecs) == 3
    assert all(len(v) == 64 for v in vecs)


def test_mock_embedder_empty(mock_embedder):
    """Embed teks kosong tidak boleh crash."""
    emb = mock_embedder.__class__()
    v = emb.embed("")
    assert len(v) == 64

"""Test v2 config sections (Embedding/VectorDB/LLM/Retrieval)."""

from siberrag_core.config import (
    AppConfig,
    EmbeddingConfig,
    LLMConfig,
    RetrievalConfig,
    VectorDBConfig,
    load_config,
)


def test_v2_config_defaults():
    cfg = AppConfig()
    assert cfg.embedding.provider == "local"
    assert cfg.embedding.model == "BAAI/bge-m3"
    assert cfg.embedding.dim == 1024
    assert cfg.vector_db.backend == "chroma"
    assert cfg.vector_db.collection == "siberrag"
    assert cfg.llm.model == "gpt-4o-mini"
    assert cfg.llm.temperature == 0.3
    assert cfg.retrieval.top_k == 5
    assert cfg.retrieval.score_threshold == 0.3


def test_v2_config_from_dict():
    data = {
        "embedding": {"provider": "custom", "model": "jina-v3", "dim": 1024,
                      "api_base": "https://api.jina.ai/v1"},
        "vector_db": {"collection": "mydocs", "path": "/tmp/vs"},
        "llm": {"model": "gpt-4o", "temperature": 0.1, "max_tokens": 2048},
        "retrieval": {"top_k": 10, "score_threshold": 0.5},
    }
    cfg = AppConfig.from_dict(data)
    assert cfg.embedding.provider == "custom"
    assert cfg.embedding.api_base == "https://api.jina.ai/v1"
    assert cfg.vector_db.collection == "mydocs"
    assert cfg.llm.model == "gpt-4o"
    assert cfg.llm.max_tokens == 2048
    assert cfg.retrieval.top_k == 10


def test_v2_config_to_dict_roundtrip():
    cfg = AppConfig()
    cfg.embedding.provider = "openai"
    d = cfg.to_dict()
    assert "embedding" in d
    assert "vector_db" in d
    assert "llm" in d
    assert "retrieval" in d
    assert d["embedding"]["provider"] == "openai"
    # v1 sections tetap ada
    assert "chunking" in d
    assert "export" in d


def test_v1_config_intact_with_v2():
    """Pastikan v1 config tetap berfungsi walau v2 ditambahkan."""
    cfg = AppConfig()
    assert cfg.chunking.target_tokens == 500
    assert cfg.cleaning.remove_repeated_headers is True
    assert cfg.export.format == "jsonl"


def test_embedding_provider_validation():
    """Provider embedding hanya boleh local/openai/custom."""
    import pytest
    with pytest.raises(Exception):
        EmbeddingConfig(provider="invalid_provider")


def test_load_config_yaml_has_v2():
    """config.yaml default harus berisi section v2."""
    cfg = load_config()  # load dari config/config.yaml
    assert isinstance(cfg.embedding, EmbeddingConfig)
    assert isinstance(cfg.vector_db, VectorDBConfig)
    assert isinstance(cfg.llm, LLMConfig)
    assert isinstance(cfg.retrieval, RetrievalConfig)

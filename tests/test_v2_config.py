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
    assert cfg.llm.provider == "local"
    assert cfg.llm.model == "Qwen/Qwen2.5-0.5B-Instruct"
    assert cfg.llm.api_base == ""
    assert cfg.llm.temperature == 0.3
    assert cfg.retrieval.top_k == 5
    assert cfg.retrieval.score_threshold == 0.3


def test_v2_config_from_dict():
    data = {
        "embedding": {"provider": "custom", "model": "jina-v3", "dim": 1024,
                      "api_base": "https://api.jina.ai/v1"},
        "vector_db": {"collection": "mydocs", "path": "/tmp/vs"},
        "llm": {"provider": "custom", "model": "gpt-4o",
                "api_base": "https://api.deepinfra.com/v1",
                "temperature": 0.1, "max_tokens": 2048},
        "retrieval": {"top_k": 10, "score_threshold": 0.5},
    }
    cfg = AppConfig.from_dict(data)
    assert cfg.embedding.provider == "custom"
    assert cfg.embedding.api_base == "https://api.jina.ai/v1"
    assert cfg.vector_db.collection == "mydocs"
    assert cfg.llm.provider == "custom"
    assert cfg.llm.model == "gpt-4o"
    assert cfg.llm.api_base == "https://api.deepinfra.com/v1"
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


def test_custom_embedding_requires_api_base():
    """Provider custom embedding wajib punya endpoint OpenAI-compatible."""
    import pytest
    with pytest.raises(Exception, match="embedding.api_base"):
        EmbeddingConfig(provider="custom")


def test_llm_provider_validation():
    """Provider LLM hanya boleh local/openai/custom."""
    import pytest
    with pytest.raises(Exception):
        LLMConfig(provider="invalid_provider")


def test_custom_llm_requires_api_base():
    """Provider custom LLM wajib punya endpoint OpenAI-compatible."""
    import pytest
    with pytest.raises(Exception, match="llm.api_base"):
        LLMConfig(provider="custom", api_base="")


def test_openai_llm_uses_default_openai_base_url():
    """Provider openai resmi tidak boleh mewarisi default endpoint lokal."""
    cfg = LLMConfig(provider="openai", model="gpt-4o-mini")
    assert cfg.api_base == ""


def test_llm_registry_maps_local_to_transformers():
    """Provider local harus memakai Transformers langsung, bukan OpenAI-compatible API."""
    from siberrag_core.generation.local_llm import LocalTransformersLLM
    from siberrag_core.generation.openai_llm import OpenAILLM
    from siberrag_core.generation.registry import _PROVIDERS

    assert _PROVIDERS["local"] is LocalTransformersLLM
    assert _PROVIDERS["custom"] is OpenAILLM
    assert _PROVIDERS["openai"] is OpenAILLM


def test_load_config_yaml_has_v2():
    """config.yaml default harus berisi section v2."""
    cfg = load_config()  # load dari config/config.yaml
    assert isinstance(cfg.embedding, EmbeddingConfig)
    assert isinstance(cfg.vector_db, VectorDBConfig)
    assert isinstance(cfg.llm, LLMConfig)
    assert isinstance(cfg.retrieval, RetrievalConfig)

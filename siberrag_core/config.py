"""Konfigurasi pipeline berbasis Pydantic + YAML.

Semua parameter pipeline dapat diubah dari ``config/config.yaml``.
``load_config`` membaca file YAML (bila ada) lalu menggabungkannya dengan default.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from pydantic import BaseModel, Field

# path default relatif terhadap root proyek
_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "config.yaml"


class ParsingConfig(BaseModel):
    parser: Literal["auto", "docling", "native"] = "auto"
    enable_ocr: bool = False
    ocr_language: list[str] = Field(default_factory=lambda: ["en", "id"])
    keep_images: bool = False


class CleaningConfig(BaseModel):
    remove_repeated_headers: bool = True
    remove_repeated_footers: bool = True
    remove_page_numbers: bool = True
    collapse_whitespace: bool = True
    collapse_blank_lines: bool = True
    fix_broken_ocr: bool = True
    fix_invalid_unicode: bool = True


class ChunkingConfig(BaseModel):
    target_tokens: int = 500
    min_tokens: int = 250
    max_tokens: int = 700
    overlap_tokens: int = 90
    encoding: str = "cl100k_base"
    split_on_paragraph: bool = True
    # Prepend konteks chapter/section ke teks chunk untuk meningkatkan retrieval.
    # Konteks ditambahkan sebagai baris header di awal chunk, mis:
    #   "[Bab I - Ketentuan Umum > Pasal 1]"
    prepend_context: bool = True


class ValidationConfig(BaseModel):
    enabled: bool = True
    min_quality_score: int = 70
    flag_duplicate: bool = True
    flag_oversized: bool = True
    flag_undersized: bool = True


class MetadataConfig(BaseModel):
    detect_language: bool = True


class ExportConfig(BaseModel):
    format: Literal["json", "jsonl", "markdown"] = "jsonl"
    output_dir: str = "./output"
    pretty_json: bool = True
    include_metadata: bool = True
    overwrite: bool = True


# ============================================================
# v2 - RAG config sections
# ============================================================


class EmbeddingConfig(BaseModel):
    """Konfigurasi embedding (hybrid: local default, bisa switch ke API).

    Provider yang didukung:
    - ``local``: sentence-transformers (BGE-m3), gratis & offline
    - ``openai``: OpenAI resmi (text-embedding-3-*)
    - ``custom``: endpoint OpenAI-compatible APA SAJA (Jina/Cohere/Together/Ollama/LM Studio/dll)
    ``openai`` & ``custom`` identik logikanya; ``custom`` cuma dokumentasi bahwa
    ini bukan OpenAI resmi. Isi ``api_base`` + ``api_key`` sesuai provider.
    """

    provider: Literal["local", "openai", "custom"] = "local"
    model: str = "BAAI/bge-m3"  # multilingual, akurat untuk Bahasa Indonesia
    dim: int = 1024
    batch_size: int = 32
    # untuk provider openai/custom (OpenAI-compatible endpoint)
    api_key: str = ""  # bila kosong, ambil dari env OPENAI_API_KEY (boleh kosong utk lokal)
    api_base: str = ""  # mis. https://api.openai.com/v1 atau http://localhost:11434/v1


class VectorDBConfig(BaseModel):
    """Konfigurasi vector database (ChromaDB embedded)."""

    backend: Literal["chroma"] = "chroma"
    collection: str = "siberrag"
    path: str = "./vectorstore"  # direktori persisten ChromaDB
    distance: Literal["cosine"] = "cosine"


class LLMConfig(BaseModel):
    """Konfigurasi LLM untuk generation (OpenAI-compatible API)."""

    provider: Literal["openai"] = "openai"
    model: str = "gpt-4o-mini"
    api_key: str = ""  # bila kosong, ambil dari env OPENAI_API_KEY
    api_base: str = ""  # mis. https://api.openai.com/v1
    temperature: float = 0.3
    max_tokens: int = 1024


class RetrievalConfig(BaseModel):
    """Konfigurasi retrieval & RAG flow."""

    top_k: int = 5
    score_threshold: float = 0.3  # filter chunk dengan relevansi di bawah threshold
    filter_by_document: bool = False  # scope query ke document_id tertentu


class AppConfig(BaseModel):
    """Konfigurasi lengkap SiberRAG."""

    parsing: ParsingConfig = Field(default_factory=ParsingConfig)
    cleaning: CleaningConfig = Field(default_factory=CleaningConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    metadata: MetadataConfig = Field(default_factory=MetadataConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    # v2 RAG
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    vector_db: VectorDBConfig = Field(default_factory=VectorDBConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        return cls.model_validate(data)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


def load_config(path: Optional[Path | str] = None) -> AppConfig:
    """Muat konfigurasi dari file YAML.

    Bila ``path`` tidak diberikan, gunakan default ``config/config.yaml``.
    Bila file tidak ada, kembalikan konfigurasi default.
    """
    cfg_path = Path(path) if path else _DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        return AppConfig()
    with cfg_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return AppConfig.from_dict(raw)


def default_config_path() -> Path:
    """Path konfigurasi default."""
    return _DEFAULT_CONFIG_PATH

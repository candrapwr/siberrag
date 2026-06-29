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


class AppConfig(BaseModel):
    """Konfigurasi lengkap SiberRAG."""

    parsing: ParsingConfig = Field(default_factory=ParsingConfig)
    cleaning: CleaningConfig = Field(default_factory=CleaningConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    metadata: MetadataConfig = Field(default_factory=MetadataConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)

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

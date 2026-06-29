"""Test config."""

from pathlib import Path

from siberrag_core.config import AppConfig, ChunkingConfig, load_config


def test_default_config():
    cfg = AppConfig()
    assert cfg.chunking.target_tokens == 500
    assert cfg.chunking.min_tokens == 250
    assert cfg.chunking.max_tokens == 700
    assert cfg.chunking.overlap_tokens == 90
    assert cfg.export.format == "jsonl"


def test_load_config_from_yaml(tmp_path):
    yaml_text = """
chunking:
  target_tokens: 400
  min_tokens: 200
  max_tokens: 600
  overlap_tokens: 50
export:
  format: json
  output_dir: ./custom_out
"""
    p = tmp_path / "config.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    cfg = load_config(p)
    assert cfg.chunking.target_tokens == 400
    assert cfg.chunking.max_tokens == 600
    assert cfg.export.format == "json"
    assert cfg.export.output_dir == "./custom_out"


def test_load_config_missing_file(tmp_path):
    """File config tidak ada -> default."""
    cfg = load_config(tmp_path / "nope.yaml")
    assert isinstance(cfg, AppConfig)
    assert cfg.chunking.target_tokens == 500  # default

"""Registry exporter - memilih exporter berdasarkan format konfigurasi."""

from __future__ import annotations

from typing import Optional

from siberrag_core.config import ExportConfig
from siberrag_core.exporters.base import BaseExporter
from siberrag_core.exporters.json_exporter import JsonExporter
from siberrag_core.exporters.jsonl_exporter import JsonlExporter
from siberrag_core.exporters.markdown_exporter import MarkdownExporter

_EXPORTERS: dict[str, type[BaseExporter]] = {
    "json": JsonExporter,
    "jsonl": JsonlExporter,
    "markdown": MarkdownExporter,
    "md": MarkdownExporter,
}


def get_exporter(config: Optional[ExportConfig] = None, *,
                 format: Optional[str] = None) -> BaseExporter:
    """Factory exporter dari format."""
    cfg = config or ExportConfig()
    fmt = (format or cfg.format).lower()
    cls = _EXPORTERS.get(fmt)
    if cls is None:
        raise ValueError(f"Format export tidak dikenal: {fmt}")
    return cls(cfg)

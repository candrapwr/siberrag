"""Exporter JSON - seluruh chunk dalam satu file JSON array."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from siberrag_core.exporters.base import BaseExporter
from siberrag_core.models.chunk import Chunk
from siberrag_core.models.validation import ChunkValidation


class JsonExporter(BaseExporter):
    extension = "json"

    def export(
        self,
        chunks: list[Chunk],
        validations: list[ChunkValidation],
        output_path: Path,
    ) -> Path:
        self.ensure_parent(output_path)
        val_by_id = {v.chunk_id: v for v in validations}
        data: list[dict[str, Any]] = []
        for chunk in chunks:
            v = val_by_id.get(chunk.id)
            data.append(self._chunk_to_dict(chunk, v))
        indent = 2 if self.config.pretty_json else None
        output_path.write_text(
            json.dumps(data, indent=indent, ensure_ascii=False),
            encoding="utf-8",
        )
        return output_path

    def _chunk_to_dict(self, chunk: Chunk, v: ChunkValidation | None) -> dict[str, Any]:
        item: dict[str, Any] = {"id": chunk.id, "text": chunk.text}
        if self.config.include_metadata:
            item["metadata"] = chunk.metadata.model_dump()
        if v is not None:
            item["validation"] = {
                "quality_score": v.quality_score,
                "warnings": [
                    {"code": f.code, "severity": f.severity, "message": f.message}
                    for f in v.warnings
                ],
                "recommendations": [
                    {"code": f.code, "message": f.message}
                    for f in v.recommendations
                ],
            }
        return item

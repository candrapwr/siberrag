"""Exporter JSONL - satu chunk per baris (ideal untuk pipeline RAG)."""

from __future__ import annotations

import json
from pathlib import Path

from siberrag_core.exporters.json_exporter import JsonExporter
from siberrag_core.models.chunk import Chunk
from siberrag_core.models.validation import ChunkValidation


class JsonlExporter(JsonExporter):
    """JSONL = satu objek JSON per baris. Warisin _chunk_to_dict dari JsonExporter."""

    extension = "jsonl"

    def export(
        self,
        chunks: list[Chunk],
        validations: list[ChunkValidation],
        output_path: Path,
    ) -> Path:
        self.ensure_parent(output_path)
        val_by_id = {v.chunk_id: v for v in validations}
        lines: list[str] = []
        for chunk in chunks:
            v = val_by_id.get(chunk.id)
            lines.append(json.dumps(self._chunk_to_dict(chunk, v), ensure_ascii=False))
        output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        return output_path

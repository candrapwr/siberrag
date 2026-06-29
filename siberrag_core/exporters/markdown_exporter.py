"""Exporter Markdown - chunk yang dapat dibaca manusia + ringkasan metadata."""

from __future__ import annotations

from pathlib import Path

from siberrag_core.exporters.base import BaseExporter
from siberrag_core.models.chunk import Chunk
from siberrag_core.models.validation import ChunkValidation


class MarkdownExporter(BaseExporter):
    extension = "md"

    def export(
        self,
        chunks: list[Chunk],
        validations: list[ChunkValidation],
        output_path: Path,
    ) -> Path:
        self.ensure_parent(output_path)
        val_by_id = {v.chunk_id: v for v in validations}
        parts: list[str] = [
            "# SiberRAG - Chunks",
            "",
            f"- Total chunks: **{len(chunks)}**",
            "",
            "---",
            "",
        ]
        for i, chunk in enumerate(chunks, start=1):
            v = val_by_id.get(chunk.id)
            parts.append(f"## Chunk {i}")
            parts.append("")
            if self.config.include_metadata:
                m = chunk.metadata
                meta_line = (
                    f"> `{m.filename}` · {m.chapter or '-'} › {m.section or '-'} · "
                    f"page {m.page_start}-{m.page_end} · "
                    f"{m.token_count} tok / {m.word_count} kata · "
                    f"lang={m.language or '-'}"
                )
                parts.append(meta_line)
                parts.append("")
            parts.append(chunk.text)
            parts.append("")
            if v is not None:
                score_tag = self._score_tag(v.quality_score)
                parts.append(f"*Quality score: {score_tag}*")
                for w in v.warnings:
                    parts.append(f"- ⚠️ **{w.code}**: {w.message}")
            parts.append("")
            parts.append("---")
            parts.append("")
        output_path.write_text("\n".join(parts), encoding="utf-8")
        return output_path

    @staticmethod
    def _score_tag(score: int) -> str:
        if score >= 90:
            return f"{score}/100 🟢"
        if score >= 70:
            return f"{score}/100 🟡"
        return f"{score}/100 🔴"

"""IndexPipeline - chunk dokumen via v1, lalu embed + store ke vector DB.

Reuse maksimal Pipeline v1 (parse → clean → chunk) untuk mendapatkan
``list[Chunk]`` dengan metadata lengkap, kemudian embed batch dan simpan
ke vector store (ChromaDB).

Dua mode input:
1. Path dokumen (file/dir) -> chunking via v1 pipeline -> embed -> store
2. Path file .jsonl (output v1 sebelumnya) -> load chunk -> embed -> store
   (berguna bila chunking sudah dilakukan & ingin re-embed dengan model lain)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from siberrag_core.config import AppConfig, load_config
from siberrag_core.embeddings.registry import get_embedder
from siberrag_core.models.chunk import Chunk, ChunkMetadata
from siberrag_core.pipeline import Pipeline, PipelineResult, ProgressReporter, NullProgress
from siberrag_core.utils.logging import logger
from siberrag_core.vectorstore.registry import get_vectorstore


@dataclass
class IndexResult:
    """Hasil indexing satu source."""

    source: str = ""
    total_chunks: int = 0
    indexed: int = 0
    skipped: int = 0
    error: Optional[str] = None
    # statistik embedding
    embedding_dim: int = 0


@dataclass
class IndexBatchResult:
    """Hasil agregat indexing."""

    results: list[IndexResult] = field(default_factory=list)

    @property
    def succeeded(self) -> list[IndexResult]:
        return [r for r in self.results if r.error is None]

    @property
    def failed(self) -> list[IndexResult]:
        return [r for r in self.results if r.error is not None]

    @property
    def total_indexed(self) -> int:
        return sum(r.indexed for r in self.results)


class IndexPipeline:
    """Orchestrator indexing: v1 chunk -> embed -> store."""

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self.config = config or load_config()
        # reuse v1 pipeline (TIDAK diubah sama sekali)
        self.chunk_pipeline = Pipeline(self.config)
        self.embedder = get_embedder(self.config)
        self.store = get_vectorstore(self.config)

    def index(
        self,
        source: Path | str,
        *,
        progress: Optional[ProgressReporter] = None,
        min_quality_score: int = 0,
    ) -> IndexBatchResult:
        """Index source (file/direktori dokumen ATAU file .jsonl).

        Args:
            source: path ke dokumen/direktori, atau file .jsonl hasil v1.
            progress: reporter progres (opsional).
            min_quality_score: lewati chunk dengan quality_score < threshold
                              (butuh validation data dari JSONL; 0 = tidak filter).
        """
        progress = progress or NullProgress()
        src = Path(source)
        batch = IndexBatchResult()

        # mode JSONL: load chunk dari file hasil v1
        if src.is_file() and src.suffix.lower() == ".jsonl":
            result = self._index_jsonl(src, progress, min_quality_score)
            batch.results.append(result)
            return batch

        # mode dokumen: chunk via v1 pipeline
        if not src.exists():
            logger.error(f"Path tidak ditemukan: {src}")
            batch.results.append(IndexResult(source=str(src), error="Path tidak ditemukan."))
            return batch

        progress.stage("Chunking documents (v1 pipeline)...")
        pipeline_result: PipelineResult = self.chunk_pipeline.run(src, progress=progress)
        if not pipeline_result.all_chunks:
            logger.warning("Tidak ada chunk dihasilkan.")
            return batch

        # kumpulkan chunk dari file yang berhasil
        for fr in pipeline_result.files:
            if fr.error is not None or not fr.chunks:
                continue
            result = self._embed_and_store(fr.chunks, str(fr.path), progress)
            batch.results.append(result)

        logger.info(f"Indexing selesai: {batch.total_indexed} chunk terindeks.")
        return batch

    def _index_jsonl(self, path: Path, progress: ProgressReporter,
                     min_quality_score: int) -> IndexResult:
        """Index dari file JSONL hasil export v1."""
        progress.stage("Loading chunks from JSONL...")
        chunks: list[Chunk] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                # filter by quality score bila diminta
                if min_quality_score > 0:
                    score = data.get("validation", {}).get("quality_score", 100)
                    if score < min_quality_score:
                        continue
                meta = ChunkMetadata(**data.get("metadata", {}))
                chunks.append(Chunk(id=data.get("id", ""), text=data.get("text", ""), metadata=meta))
        return self._embed_and_store(chunks, str(path), progress)

    def _embed_and_store(self, chunks: list[Chunk], source: str,
                         progress: ProgressReporter) -> IndexResult:
        """Embed batch chunk dan simpan ke vector store.

        Pecah jadi SUB-BATCH agar tidak exceed limit vector DB (mis. ChromaDB
        max 5461/upsert) atau limit batch embedding API. Ukuran sub-batch
        default 500 (aman di bawah limit umum).
        """
        result = IndexResult(source=source, total_chunks=len(chunks))
        if not chunks:
            return result
        # ukuran sub-batch: ambil min(embedding batch_size, 500) utk safety.
        # 500 aman di bawah limit ChromaDB (5461) & batch API umum.
        sub_batch_size = min(getattr(self.config.embedding, "batch_size", 32) or 32, 500)
        try:
            total_indexed = 0
            total = len(chunks)
            result.embedding_dim = None
            progress.stage("Embedding & storing to vector DB...")
            for start in range(0, total, sub_batch_size):
                end = min(start + sub_batch_size, total)
                batch = chunks[start:end]
                embeddings = self.embedder.embed_batch([c.text for c in batch])
                if result.embedding_dim is None:
                    result.embedding_dim = self.embedder.dimension
                indexed = self.store.upsert(batch, embeddings)
                total_indexed += indexed
                # update progress bar: done/total
                progress.update(end, total, f"Indexing chunk {end}/{total}")

            result.indexed = total_indexed
            logger.info(f"✓ {Path(source).name}: {total_indexed} chunk terindeks "
                        f"(dim={result.embedding_dim}, {total} total, "
                        f"sub-batch {sub_batch_size}).")
        except Exception as exc:
            result.error = f"{type(exc).__name__}: {exc}"
            logger.error(f"✗ Indexing gagal untuk {source}: {result.error}")
        return result

    def stats(self) -> dict:
        """Statistik vector store saat ini."""
        return {
            "collection": self.config.vector_db.collection,
            "total_chunks": self.store.count(),
            "collections": self.store.list_collections(),
            "embedding_provider": self.config.embedding.provider,
            "embedding_model": self.config.embedding.model,
        }

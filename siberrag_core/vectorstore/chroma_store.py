"""Vector store backend ChromaDB (embedded, simpan ke disk).

ChromaDB menyimpan collection persistent di ``path``. Setiap chunk disimpan
dengan id, embedding, document(text), dan metadata (untuk filtering).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from siberrag_core.config import AppConfig, VectorDBConfig
from siberrag_core.models.chunk import Chunk, ChunkMetadata
from siberrag_core.utils.logging import logger
from siberrag_core.vectorstore.base import BaseVectorStore, SearchHit, SearchResults

try:
    import chromadb  # type: ignore
    from chromadb.config import Settings  # type: ignore
    _HAS_CHROMA = True
except Exception:  # pragma: no cover - opsional
    _HAS_CHROMA = False


def is_available() -> bool:
    return _HAS_CHROMA


class ChromaVectorStore(BaseVectorStore):
    """Vector store ChromaDB."""

    name = "chroma"

    def __init__(self, config: Optional[VectorDBConfig | AppConfig] = None) -> None:
        super().__init__(config)
        if not _HAS_CHROMA:
            raise RuntimeError(
                "chromadb tidak terpasang. Install dengan: pip install -e '.[rag]'"
            )
        self._client = None
        self._collection = None

    def _get_client(self):
        if self._client is None:
            path = Path(self.config.path)
            path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"ChromaDB persistent path: {path}")
            self._client = chromadb.PersistentClient(path=str(path))
        return self._client

    def _get_collection(self):
        if self._collection is None:
            client = self._get_client()
            # distance: cosine -> chroma expects 'cosine'
            self._collection = client.get_or_create_collection(
                name=self.config.collection,
                metadata={"hnsw:space": self.config.distance},
            )
        return self._collection

    def _chunk_to_metadata(self, chunk: Chunk) -> dict[str, Any]:
        """Konversi ChunkMetadata ke dict yang Chroma-compatible (flat, primitive)."""
        m = chunk.metadata
        meta = {
            "document_id": m.document_id,
            "filename": m.filename,
            "page_start": m.page_start,
            "page_end": m.page_end,
            "chapter": m.chapter or "",
            "section": m.section or "",
            "chunk_index": m.chunk_index,
            "total_chunk": m.total_chunk,
            "token_count": m.token_count,
            "word_count": m.word_count,
            "language": m.language or "",
            "block_type": m.block_type,
        }
        return meta

    def _metadata_to_chunk(self, doc_id: str, text: str,
                           meta: dict[str, Any]) -> Chunk:
        """Rekonstruksi Chunk dari record Chroma."""
        return Chunk(
            id=doc_id,
            text=text,
            metadata=ChunkMetadata(
                id=doc_id,
                document_id=str(meta.get("document_id", "")),
                filename=str(meta.get("filename", "")),
                page_start=int(meta.get("page_start", 1)),
                page_end=int(meta.get("page_end", 1)),
                chapter=str(meta.get("chapter", "")),
                section=str(meta.get("section", "")),
                chunk_index=int(meta.get("chunk_index", 0)),
                total_chunk=int(meta.get("total_chunk", 0)),
                token_count=int(meta.get("token_count", 0)),
                word_count=int(meta.get("word_count", 0)),
                language=str(meta.get("language", "")),
                block_type=str(meta.get("block_type", "paragraph")),
            ),
        )

    def upsert(self, chunks: list[Chunk], embeddings: list[list[float]]) -> int:
        if not chunks:
            return 0
        collection = self._get_collection()
        ids = [c.id for c in chunks]
        docs = [c.text for c in chunks]
        metas = [self._chunk_to_metadata(c) for c in chunks]
        collection.upsert(ids=ids, embeddings=embeddings, documents=docs, metadatas=metas)
        logger.debug(f"ChromaDB upsert: {len(chunks)} chunk ke collection '{self.config.collection}'.")
        return len(chunks)

    def search(self, query_embedding: list[float], top_k: int = 5,
               where: Optional[dict[str, Any]] = None) -> SearchResults:
        collection = self._get_collection()
        # ChromaDB query n_results + include
        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        hits: list[SearchHit] = []
        ids_list = result.get("ids", [[]])
        docs_list = result.get("documents", [[]])
        metas_list = result.get("metadatas", [[]])
        dists_list = result.get("distances", [[]])
        if not ids_list or not ids_list[0]:
            return SearchResults()
        for i, doc_id in enumerate(ids_list[0]):
            text = docs_list[0][i] if i < len(docs_list[0]) else ""
            meta = metas_list[0][i] if i < len(metas_list[0]) else {}
            dist = dists_list[0][i] if i < len(dists_list[0]) else 1.0
            # chroma distance (cosine): 0 = identik, 2 = berlawanan
            # konversi ke similarity score (1 - distance/2) agar tinggi = relevan
            score = max(0.0, 1.0 - dist / 2.0)
            chunk = self._metadata_to_chunk(doc_id, text, meta)
            hits.append(SearchHit(chunk=chunk, score=score))
        return SearchResults(hits=hits)

    def delete(self, ids: list[str]) -> int:
        if not ids:
            return 0
        collection = self._get_collection()
        collection.delete(ids=ids)
        return len(ids)

    def count(self) -> int:
        collection = self._get_collection()
        return collection.count()

    def list_collections(self) -> list[str]:
        client = self._get_client()
        return [c.name for c in client.list_collections()]

"""Retriever - cari chunk relevan di vector store + filter skor.

Mengorkestrasi: embed query -> vector store search -> filter by score_threshold ->
return SearchResults terurut (paling relevan di atas).
"""

from __future__ import annotations

from typing import Optional

from siberrag_core.config import AppConfig, RetrievalConfig
from siberrag_core.embeddings.registry import get_embedder
from siberrag_core.utils.logging import logger
from siberrag_core.vectorstore.base import SearchResults
from siberrag_core.vectorstore.registry import get_vectorstore


class Retriever:
    """Embed query + search vector store + filter skor."""

    def __init__(self, config: Optional[AppConfig] = None,
                 embedder=None, store=None) -> None:
        self.config = config or AppConfig()
        self.embedder = embedder or get_embedder(self.config)
        self.store = store or get_vectorstore(self.config)
        self.retrieval_cfg: RetrievalConfig = self.config.retrieval

    def retrieve(
        self,
        question: str,
        *,
        top_k: Optional[int] = None,
        score_threshold: Optional[float] = None,
        document_id: Optional[str] = None,
    ) -> SearchResults:
        """Cari chunk relevan untuk ``question``.

        Args:
            question: teks pertanyaan.
            top_k: override retrieval.top_k.
            score_threshold: override retrieval.score_threshold.
            document_id: bila diisi, scope pencarian ke document_id tertentu.
        """
        k = top_k or self.retrieval_cfg.top_k
        threshold = score_threshold if score_threshold is not None else self.retrieval_cfg.score_threshold

        # 1. embed query
        q_emb = self.embedder.embed(question)
        # 2. search vector store
        where = {"document_id": document_id} if document_id else None
        results = self.store.search(q_emb, top_k=k, where=where)
        # 3. filter by score threshold
        if threshold > 0:
            before = len(results)
            results.hits = [h for h in results.hits if h.score >= threshold]
            if before != len(results.hits):
                logger.debug(f"Retrieval: filter {before - len(results.hits)} chunk "
                             f"di bawah threshold {threshold}.")
        results.query = question
        return results

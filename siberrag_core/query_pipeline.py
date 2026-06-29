"""QueryPipeline - RAG flow lengkap: retrieve -> generate.

Mengorkestrasi Retriever (embed query + search) dan LLM (generate jawaban
berdasarkan context). Mendukung:
- Query sederhana (retrieve + generate)
- Filter per document_id
- Override top_k & score_threshold
- Fallback bila tidak ada context relevan
"""

from __future__ import annotations

from typing import Optional

from siberrag_core.config import AppConfig, load_config
from siberrag_core.generation.prompts import build_rag_prompt
from siberrag_core.generation.registry import get_llm
from siberrag_core.retrieval.retriever import Retriever
from siberrag_core.generation.base import Answer
from siberrag_core.utils.logging import logger
from siberrag_core.embeddings.registry import get_embedder
from siberrag_core.vectorstore.registry import get_vectorstore


class QueryPipeline:
    """Orchestrator RAG: retrieve context + generate answer."""

    def __init__(self, config: Optional[AppConfig] = None,
                 retriever: Optional[Retriever] = None, llm=None) -> None:
        self.config = config or load_config()
        # share embedder & store antara retriever
        self.embedder = get_embedder(self.config)
        self.store = get_vectorstore(self.config)
        self.retriever = retriever or Retriever(
            self.config, embedder=self.embedder, store=self.store
        )
        # LLM lazy-init: hanya dibuat saat benar-benar generate.
        # Berguna agar mode retrieve-only tidak butuh API key OpenAI.
        self._llm = llm

    @property
    def llm(self):
        """LLM generator (lazy-loaded saat pertama diakses)."""
        if self._llm is None:
            self._llm = get_llm(self.config)
        return self._llm

    @llm.setter
    def llm(self, value):
        self._llm = value

    def query(
        self,
        question: str,
        *,
        top_k: Optional[int] = None,
        score_threshold: Optional[float] = None,
        document_id: Optional[str] = None,
    ) -> Answer:
        """Jalankan RAG flow untuk satu pertanyaan.

        Args:
            question: pertanyaan pengguna.
            top_k: override jumlah chunk yang di-retrieve.
            score_threshold: override threshold relevansi.
            document_id: scope ke dokumen tertentu (opsional).
        """
        answer = Answer(question=question, model=self.config.llm.model)

        # 1. retrieve context
        logger.debug(f"Query: {question!r} (top_k={top_k})")
        results = self.retriever.retrieve(
            question, top_k=top_k, score_threshold=score_threshold,
            document_id=document_id,
        )
        answer.sources = results
        logger.info(f"Retrieved {len(results)} chunk relevan untuk query.")

        # 2. bila tidak ada context relevan, jawab tanpa generation
        if not results.hits:
            answer.text = ("Maaf, tidak ditemukan konteks yang relevan dengan pertanyaan Anda "
                           "dalam dokumen yang telah diindeks.")
            return answer

        # 3. build RAG prompt & generate
        try:
            messages = build_rag_prompt(question, results)
            answer.text = self.llm.generate(messages)
            logger.info("LLM generation selesai.")
        except Exception as exc:
            answer.error = f"{type(exc).__name__}: {exc}"
            answer.text = f"Terjadi kesalahan saat generate jawaban: {exc}"
            logger.error(f"LLM generation gagal: {exc}")

        return answer

    def retrieve_only(
        self,
        question: str,
        *,
        top_k: Optional[int] = None,
        score_threshold: Optional[float] = None,
        document_id: Optional[str] = None,
    ):
        """Hanya retrieve context tanpa LLM generation (debug/inspection)."""
        return self.retriever.retrieve(
            question, top_k=top_k, score_threshold=score_threshold,
            document_id=document_id,
        )

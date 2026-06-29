"""FastAPI app untuk SiberRAG RAG.

Endpoints:
- GET  /api/health         -> status server
- GET  /api/stats          -> statistik vector DB
- POST /api/index          -> index dokumen/path
- POST /api/query          -> tanya jawab RAG
- GET  /                   -> Web UI (Gradio, bila terpasang)

Konfigurasi dibaca dari config/config.yaml (atau env SIBERRAG_CONFIG).
IndexPipeline & QueryPipeline di-cache (singleton) agar model embedding tidak
di-load ulang setiap request.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from siberrag_core.config import load_config

# config path bisa di-override via env (dipakai command `serve`)
_config_path = os.environ.get("SIBERRAG_CONFIG", "").strip()
CONFIG = load_config(_config_path or None)

app = FastAPI(
    title="SiberRAG API",
    description="RAG API - Document Q&A berbasis dokumen yang telah di-index.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# cache pipeline (lazy init, hindari load model di import time)
_index_pipeline = None
_query_pipeline = None


def get_index_pipeline():
    global _index_pipeline
    if _index_pipeline is None:
        from siberrag_core.index_pipeline import IndexPipeline
        _index_pipeline = IndexPipeline(CONFIG)
    return _index_pipeline


def get_query_pipeline():
    global _query_pipeline
    if _query_pipeline is None:
        from siberrag_core.query_pipeline import QueryPipeline
        _query_pipeline = QueryPipeline(CONFIG)
    return _query_pipeline


# ============================================================
# Request/Response models
# ============================================================


class IndexRequest(BaseModel):
    path: str
    collection: Optional[str] = None
    min_quality: int = 0


class IndexResponse(BaseModel):
    total_indexed: int
    sources_succeeded: int
    sources_failed: int
    errors: list[str] = []


class QueryRequest(BaseModel):
    question: str
    top_k: Optional[int] = None
    score_threshold: Optional[float] = None
    document_id: Optional[str] = None
    retrieve_only: bool = False


class SourceHit(BaseModel):
    chunk_id: str
    score: float
    text: str
    filename: str = ""
    chapter: str = ""
    section: str = ""
    page_start: int = 1


class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: list[SourceHit] = []
    model: str = ""
    error: Optional[str] = None


# ============================================================
# Endpoints
# ============================================================


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.0.0", "service": "SiberRAG"}


@app.get("/api/stats")
async def stats():
    try:
        from siberrag_core.vectorstore.registry import get_vectorstore
        store = get_vectorstore(CONFIG)
        return {
            "collection": CONFIG.vector_db.collection,
            "total_chunks": store.count(),
            "collections": store.list_collections(),
            "embedding_provider": CONFIG.embedding.provider,
            "embedding_model": CONFIG.embedding.model,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/index", response_model=IndexResponse)
async def index_endpoint(req: IndexRequest):
    try:
        pipeline = get_index_pipeline()
        if req.collection:
            CONFIG.vector_db.collection = req.collection
        result = pipeline.index(req.path, min_quality_score=req.min_quality)
        errors = [f"{r.source}: {r.error}" for r in result.failed]
        return IndexResponse(
            total_indexed=result.total_indexed,
            sources_succeeded=len(result.succeeded),
            sources_failed=len(result.failed),
            errors=errors,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/query", response_model=QueryResponse)
async def query_endpoint(req: QueryRequest):
    try:
        pipeline = get_query_pipeline()
        if req.retrieve_only:
            results = pipeline.retrieve_only(
                req.question, top_k=req.top_k,
                score_threshold=req.score_threshold, document_id=req.document_id,
            )
            return QueryResponse(
                question=req.question,
                answer="(retrieve-only mode)",
                sources=[
                    SourceHit(
                        chunk_id=h.chunk.id, score=round(h.score, 4),
                        text=h.chunk.text, filename=h.chunk.metadata.filename,
                        chapter=h.chunk.metadata.chapter, section=h.chunk.metadata.section,
                        page_start=h.chunk.metadata.page_start,
                    ) for h in results.hits
                ],
            )
        answer = pipeline.query(
            req.question, top_k=req.top_k,
            score_threshold=req.score_threshold, document_id=req.document_id,
        )
        sources = [
            SourceHit(
                chunk_id=h.chunk.id, score=round(h.score, 4),
                text=h.chunk.text[:500], filename=h.chunk.metadata.filename,
                chapter=h.chunk.metadata.chapter, section=h.chunk.metadata.section,
                page_start=h.chunk.metadata.page_start,
            ) for h in answer.sources.hits
        ]
        return QueryResponse(
            question=req.question, answer=answer.text,
            sources=sources, model=answer.model, error=answer.error,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/")
async def root():
    """Root - info + link ke docs."""
    return {
        "service": "SiberRAG API v2",
        "docs": "/docs",
        "endpoints": ["/api/health", "/api/stats", "/api/index", "/api/query"],
        "ui": "Untuk Web UI chat, jalankan: python -m siberrag_ui.app",
    }

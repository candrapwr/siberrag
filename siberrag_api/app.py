"""FastAPI app untuk SiberRAG RAG.

Endpoints:
- GET  /api/health         -> status server
- GET  /api/stats          -> statistik vector DB
- POST /api/index          -> upload & index dokumen (multipart file)
- POST /api/retrieve       -> cari chunk relevan (chunk mentah, tanpa LLM)
- POST /api/query          -> tanya jawab RAG (retrieve + LLM generation)
- GET  /                   -> info + link docs

Konfigurasi dibaca dari config/config.yaml (atau env SIBERRAG_CONFIG).
IndexPipeline & QueryPipeline di-cache (singleton) agar model embedding tidak
di-load ulang setiap request.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

# Muat .env SEBELUM config/provider diinisialisasi.
from siberrag_core.utils.env import load_env
load_env()

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from siberrag_core.config import load_config
from siberrag_core.parsers.registry import is_supported

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


class IndexResponse(BaseModel):
    total_indexed: int
    sources_succeeded: int
    sources_failed: int
    errors: list[str] = []
    filename: str = ""


class QueryRequest(BaseModel):
    question: str
    top_k: Optional[int] = None
    score_threshold: Optional[float] = None
    document_id: Optional[str] = None


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


# --- Retrieve (chunk mentah) ---

class RetrieveRequest(BaseModel):
    question: str
    top_k: Optional[int] = None
    score_threshold: Optional[float] = None
    document_id: Optional[str] = None


class ChunkMetadataOut(BaseModel):
    """Metadata chunk lengkap (sesuai ChunkMetadata v1)."""
    id: str = ""
    document_id: str = ""
    filename: str = ""
    page_start: int = 1
    page_end: int = 1
    chapter: str = ""
    section: str = ""
    chunk_index: int = 0
    total_chunk: int = 0
    token_count: int = 0
    word_count: int = 0
    language: str = ""
    block_type: str = "paragraph"


class ChunkOut(BaseModel):
    """Satu chunk mentah hasil retrieval."""
    id: str
    text: str
    score: float
    metadata: ChunkMetadataOut


class RetrieveResponse(BaseModel):
    question: str
    total: int
    chunks: list[ChunkOut] = []


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
async def index_endpoint(
    file: UploadFile = File(..., description="File dokumen yang akan di-index"),
    collection: Optional[str] = None,
    min_quality: int = 0,
):
    """Upload & index dokumen. Menerima PDF/DOCX/XLSX/HTML/MD/TXT."""
    # validasi ekstensi
    filename = file.filename or "upload.bin"
    file_path_obj = Path(filename)
    if not is_supported(file_path_obj):
        raise HTTPException(
            status_code=415,
            detail=f"Format tidak didukung: {file_path_obj.suffix}. "
                   f"Didukung: PDF, DOCX, XLSX, HTML, MD, TXT.",
        )
    try:
        pipeline = get_index_pipeline()
        if collection:
            CONFIG.vector_db.collection = collection
        # simpan file upload ke temp file, lalu index
        suffix = file_path_obj.suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix,
                                         prefix="siberrag_upload_") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        try:
            result = pipeline.index(tmp_path, min_quality_score=min_quality)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        errors = [f"{r.source}: {r.error}" for r in result.failed]
        return IndexResponse(
            total_indexed=result.total_indexed,
            sources_succeeded=len(result.succeeded),
            sources_failed=len(result.failed),
            errors=errors,
            filename=filename,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/retrieve", response_model=RetrieveResponse)
async def retrieve_endpoint(req: RetrieveRequest):
    """Cari chunk relevan. Return CHUNK MENTAH (id, text, metadata lengkap, skor)
    tanpa LLM generation. Berguna untuk integrasi sistem lain yang punya LLM sendiri."""
    try:
        pipeline = get_query_pipeline()
        results = pipeline.retrieve_only(
            req.question, top_k=req.top_k,
            score_threshold=req.score_threshold, document_id=req.document_id,
        )
        chunks = [
            ChunkOut(
                id=h.chunk.id,
                text=h.chunk.text,
                score=round(h.score, 4),
                metadata=ChunkMetadataOut(**h.chunk.metadata.model_dump()),
            )
            for h in results.hits
        ]
        return RetrieveResponse(question=req.question, total=len(chunks), chunks=chunks)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/query", response_model=QueryResponse)
async def query_endpoint(req: QueryRequest):
    """Tanya jawab RAG penuh: retrieve chunk + generate jawaban via LLM."""
    try:
        pipeline = get_query_pipeline()
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
        "endpoints": ["/api/health", "/api/stats", "/api/index", "/api/retrieve", "/api/query"],
        "ui": "Untuk Web UI chat, jalankan: python -m siberrag_ui.app",
    }

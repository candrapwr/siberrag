# SiberRAG

> **Document Preprocessing & RAG Engine** — chunking dokumen berkualitas tinggi + tanya-jawab (RAG) untuk Retrieval-Augmented Generation.

SiberRAG mengubah dokumen (PDF, DOCX, XLSX, HTML, Markdown, TXT) menjadi chunk terstruktur, lalu mengindeksnya ke vector database sehingga bisa ditanya-jawab.

- **v1 — Document Preprocessing**: chunking multi-format dengan kualitas tinggi
- **v2 — RAG Penuh**: embedding + vector DB + retrieval + LLM generation + REST API + Web UI

## ✨ Fitur

### v1: Document Preprocessing
- 🔍 **Multi-format parser**: Docling primary + fallback native otomatis (PyMuPDF, python-docx, openpyxl, BeautifulSoup4)
- 🧹 **Smart cleaning**: 7 rule hapus noise tanpa merusak struktur
- 🌳 **Hierarchy + Semantic block**: struktur tree, heading+isi tetap utuh
- ✂️ **Token-aware chunking**: target 450–550 token, overlap 80–100, tidak potong struktur
- ✅ **Validator**: quality score 0–100 + warnings
- 📤 **Export**: JSON / JSONL / Markdown

### v2: RAG
- 🧠 **Embedding hybrid**: local (BGE-m3, gratis/offline) atau OpenAI API
- 💾 **ChromaDB**: vector database embedded, simpan ke disk
- 🔎 **Retrieval**: semantic search + score filtering
- 🤖 **LLM generation**: OpenAI-compatible API (GPT-4o, Claude, LM Studio, vLLM)
- 🌐 **REST API**: FastAPI (index/query/stats endpoints)
- 💬 **Web UI**: Gradio chat interface dengan source citations

## 🚀 Quick Start

```bash
# Instalasi (editable)
pip install -e .

# v2 RAG (embedding lokal + ChromaDB + API)
pip install -e ".[rag,api]"

# (Opsional) LLM via OpenAI
pip install -e ".[rag-openai]"
# set OPENAI_API_KEY

# (Opsional) Web UI
pip install -e ".[ui]"
```

### v1: Chunking
```bash
siberrag process ./documents --format jsonl
```

### v2: Index + Query
```bash
# Index dokumen ke vector DB
siberrag index regulasi.pdf

# Tanya jawab
siberrag query "Apa kewajiban penyelenggara sistem elektronik?"

# Cek statistik
siberrag stats

# Retrieve-only (tanpa LLM, debug retrieval)
siberrag query "..." --retrieve-only --top-k 5
```

### v2: REST API + Web UI
```bash
# Jalankan REST API server
siberrag serve --port 8000
# Docs otomatis: http://127.0.0.1:8000/docs

# Web UI (Gradio)
python -m siberrag_ui.app
```

API endpoints:
```
GET  /api/health         -> status
GET  /api/stats          -> statistik vector DB
POST /api/index          -> {path} index dokumen
POST /api/query          -> {question, top_k} tanya jawab RAG
```

## ⚙️ Konfigurasi

Semua parameter diatur via `config/config.yaml` — v1 (parsing, cleaning, chunking, export) dan v2 (embedding, vector_db, llm, retrieval).

## 🏗️ Arsitektur

```
v1 (chunking, TIDAK BERUBAH):         v2 (RAG, di atas v1):
Document → Parse → Clean → Chunk  →  IndexPipeline   →  ChromaDB
                                    (embed + store)

                                   QueryPipeline    →  Retrieve → LLM → Answer
                                    (embed query)

                                   REST API + Web UI →  expose index/query
```

## 🧪 Testing

```bash
pip install -e ".[dev]"
pytest  # 57 tests passing
```

## 📦 Tech Stack

**v1**: Python 3.11+ · Typer · Pydantic · Rich · Loguru · Docling · PyMuPDF · python-docx · openpyxl · BeautifulSoup4 · tiktoken

**v2**: ChromaDB · sentence-transformers (BGE-m3) · OpenAI API · FastAPI · Uvicorn · Gradio

---

SiberRAG — dari dokumen mentah ke jawaban. Modular, configurable, privasi-first (embedding & query bisa full-offline).

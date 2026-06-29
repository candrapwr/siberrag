# SiberRAG

> **Document Preprocessing & RAG Engine** — chunking dokumen berkualitas tinggi + tanya-jawab (RAG) untuk Retrieval-Augmented Generation.

SiberRAG mengubah dokumen (PDF, DOCX, XLSX, HTML, Markdown, TXT) menjadi chunk terstruktur, lalu mengindeksnya ke vector database sehingga bisa ditanya-jawab dengan jawaban + sitasi sumber.

- **v1 — Document Preprocessing**: chunking multi-format dengan kualitas tinggi
- **v2 — RAG Penuh**: embedding + vector DB + retrieval + LLM generation + REST API + Web UI

📖 **[Panduan pemakaian lengkap → docs/USAGE.md](docs/USAGE.md)**

---

## ✨ Fitur

### v1: Document Preprocessing
- 🔍 **Multi-format parser**: Docling primary + fallback native (PyMuPDF, python-docx, openpyxl, BeautifulSoup4)
- 🧹 **Smart cleaning**: hapus noise tanpa merusak struktur (header/footer berulang, page number, OCR rusak)
- 🌳 **Hierarchy + Semantic**: struktur tree, heading/list/table tetap utuh, konten lintas-bab dipisah
- ✂️ **Token-aware chunking**: target 450–550 token, overlap 80–100, tidak potong struktur
- ✅ **Validator**: quality score 0–100 + warnings

### v2: RAG
- 🧠 **Embedding hybrid**: local (BGE-m3, gratis/offline) atau API custom (DeepInfra/OpenAI/Jina/Ollama/dll)
- 💾 **ChromaDB**: vector database embedded, simpan ke disk
- 🔎 **Retrieval**: semantic search + score filtering (memahami Bahasa Indonesia natural, bukan keyword)
- 🤖 **LLM generation**: OpenAI-compatible API (GPT-4o, Llama 3, Qwen, dll via DeepInfra/Ollama/dll)
- 🌐 **REST API**: FastAPI (index/query/stats endpoints)
- 💬 **Web UI**: Gradio chat interface dengan source citations
- 🔐 **Auto-load `.env`**: API key aman, tidak perlu export manual

---

## 🚀 Quick Start

### 1. Instalasi

```bash
git clone <repo> && cd siberrag
python -m venv .venv && source .venv/bin/activate
pip install -e ".[rag,rag-openai,api]"   # RAG + API server
```

### 2. Konfigurasi API key (untuk embedding + LLM)

Buat file `.env` di root proyek (sudah di-gitignore, aman):
```bash
cp .env.example .env
# Edit .env, isi:
# OPENAI_API_KEY=key-deepinfra-anda
```

Set provider di `config/config.yaml`:
```yaml
embedding:
  provider: "custom"
  model: "BAAI/bge-m3"
  dim: 1024
  api_base: "https://api.deepinfra.com/v1"

llm:
  provider: "openai"
  model: "meta-llama/Meta-Llama-3-8B-Instruct"
  api_base: "https://api.deepinfra.com/v1"
```

### 3. Pakai

```bash
# Index dokumen ke vector DB (sekali per dokumen)
siberrag index regulasi.pdf

# Tanya jawab
siberrag query "Apa kewajiban penyelenggara sistem elektronik?"

# Lihat sumber saja tanpa LLM (gratis, cepat)
siberrag query "..." --retrieve-only

# Jalankan REST API + Web UI
siberrag serve
```

📖 Detail lengkap: **[docs/USAGE.md](docs/USAGE.md)**

---

## ⚙️ Konfigurasi

Semua parameter diatur via `config/config.yaml` — v1 (parsing, cleaning, chunking, export) dan v2 (embedding, vector_db, llm, retrieval).

Lihat config aktif:
```bash
siberrag info
```

---

## 🏗️ Arsitektur

```
v1 (chunking, TIDAK BERUBAH):         v2 (RAG, di atas v1):
Document → Parse → Clean → Chunk  →  IndexPipeline   →  ChromaDB
                                    (embed + store)

                                   QueryPipeline    →  Retrieve → LLM → Answer
                                    (embed query)

                                   REST API + Web UI →  expose index/query
```

Engine chunking v1 **tidak diubah sama sekali** — IndexPipeline memanggilnya untuk dapat chunk, lalu embed + store.

---

## 🧪 Testing

```bash
pip install -e ".[dev]"
pytest                              # 103 tests passing
pytest tests/test_v2_pipeline.py    # test RAG end-to-end
```

---

## 📦 Tech Stack

**v1**: Python 3.11+ · Typer · Pydantic · Rich · Loguru · Docling · PyMuPDF · python-docx · openpyxl · BeautifulSoup4 · tiktoken

**v2**: ChromaDB · sentence-transformers (BGE-m3) · OpenAI SDK · FastAPI · Uvicorn · Gradio · python-dotenv

---

## 📄 Lisensi

MIT

---

SiberRAG — dari dokumen mentah ke jawaban. Modular, configurable, privasi-first (embedding & query bisa full-offline dengan model lokal).

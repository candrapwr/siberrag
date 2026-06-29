# 🇮🇩 SiberRAG

> **RAG Engine yang dirancang khusus untuk Bahasa Indonesia & dokumen regulasi.**

Kebanyakan tools RAG (LangChain, LlamaIndex, dll) dioptimalkan untuk dokumen berbahasa Inggris dengan struktur sederhana. SiberRAG lahir dari frustrasi yang sama: saat kita coba bikin chatbot untuk **UU, peraturan pemerintah, atau dokumen kebijakan Indonesia**, hasilnya berantakan — chunking memotong di tengah pasal, heading "BAB I" hilang, dan retrieval tidak mengerti bahasa campuran formal/kasual yang khas Indonesia.

SiberRAG menyelesaikan ini dari akar: **chunking yang menghormati struktur hukum Indonesia + retrieval yang memahami bahasa natural.**

---

## ❓ Kenapa SiberRAG? (Bukan LangChain/LlamaIndex biasa)

| Masalah dengan RAG generik | Solusi SiberRAG |
|---|---|
| ⚠️ Chunking memotong di tengah Pasal/BAB, konteks hukum rusak | ✅ **Heading boundary keras** — BAB/Pasal/Bagian/Lampiran selalu jadi pemisah chunk |
| ⚠️ "BAB XV" tidak terdeteksi sebagai heading (PDF pemerintah) | ✅ **Pattern detection regulasi** — deteksi heading berbasis pola teks, bukan cuma font-size |
| ⚠️ Retrieval tidak ngerti pertanyaan kasual Indonesia | ✅ **BGE-m3 multilingual** + teruji 7/7 untuk pertanyaan manusia awam (bahasa sehari-hari) |
| ⚠️ Header/footer jurnal berulang ("Volume 10 No 2") mencemari chunk | ✅ **Smart cleaning** — hapus noise tanpa rusak struktur |
| ⚠️ "fakir miskin" bercampur dengan "bendera negara" dalam 1 chunk | ✅ **Hierarki terjaga** — konten lintas-bab dipisah, tidak campur topik |
| ⚠️ Dokumen PDF pemerintah Indonesia sering encoding-nya rusak | ✅ **Parser dengan fallback** — Docling primary + native (PyMuPDF/docx), + force-split untuk teks aneh |
| ⚠️ API key bocor ke git / susah konfigurasi | ✅ **Auto-load `.env`** — API key aman, tidak perlu export manual |
| ⚠️ Terlalu kompleks, butuh banyak boilerplate | ✅ **Single command** — `siberrag index` + `siberrag query`, selesai |

### Dibuktikan dengan data

Diuji pada **UUD 1945** (18 halaman, dokumen hukum paling fundamental):

- ✅ Setiap Pasal/BAB jadi chunk terpisah (tidak campur topik)
- ✅ Retrieval akurat **7/7** untuk pertanyaan ala manusia awam tanpa keyword:
  - "gimana sih negara kita berdiri di atas apa?" → Pancasila ✅
  - "orang berkuasa paling lama berapa tahun?" → masa jabatan presiden ✅
  - "ortu nggak mampu nyekolahin anak, negara bantu nggak?" → hak pendidikan ✅
- ✅ Jawaban LLM disertai **sitasi sumber** (Pasal/halaman/skor)

---

## ✨ Fitur

### 📄 Document Preprocessing (v1)
- **Multi-format**: PDF, DOCX, XLSX, HTML, Markdown, TXT
- **Parser**: Docling (primary) + native fallback (PyMuPDF, python-docx, openpyxl, bs4)
- **Smart cleaning**: hapus noise (header/footer berulang, page number, OCR rusak) tanpa merusak struktur
- **Heading detection regulasi**: BAB/Pasal/Bagian/Lampiran (pola teks + font-size)
- **Token-aware chunking**: target 450–550 token, tidak potong struktur
- **Quality score**: validator menilai setiap chunk (0–100)

### 🧠 RAG Penuh (v2)
- **Embedding hybrid**: local BGE-m3 (gratis/offline) atau API custom (DeepInfra/OpenAI/Jina/Ollama)
- **Vector DB**: ChromaDB (embedded, simpan ke disk)
- **Retrieval semantik**: memahami Bahasa Indonesia natural, bukan keyword match
- **LLM generation**: OpenAI-compatible (GPT-4o, Llama 3, Qwen via DeepInfra/Ollama)
- **REST API**: FastAPI (index/query/stats)
- **Web UI**: Gradio chat dengan source citations
- **Auto-load `.env`**: API key aman

---

## 🚀 Quick Start

### 1. Install

```bash
git clone <repo> && cd siberrag
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[rag,rag-openai,api,ui]"
```

### 2. Set API key

```bash
cp .env.example .env
# Edit .env: OPENAI_API_KEY=key-deepinfra-anda
```

### 3. Set provider di `config/config.yaml`

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

### 4. Index & tanya jawab

```bash
# Index dokumen (sekali per dokumen)
siberrag index uu.pdf

# Tanya jawab
siberrag query "Apa kewajiban penyelenggara sistem elektronik?"
```

### 5. (Opsional) Web UI

```bash
python -m siberrag_ui.app
# Buka http://127.0.0.1:7860
```

📖 **[Panduan pemakaian lengkap → docs/USAGE.md](docs/USAGE.md)**

---

## 🏗️ Arsitektur

```
v1 (chunking):                         v2 (RAG):
Document → Parse → Clean → Chunk  →   IndexPipeline  →  ChromaDB
  ↑ pattern detection BAB/Pasal           (embed + store)
  ↑ heading boundary keras
                                        QueryPipeline →  Retrieve → LLM → Answer
                                          (embed query)

                                        REST API + Web UI
```

Engine chunking v1 **tidak diubah** — IndexPipeline memanggilnya untuk dapat chunk, lalu embed + store.

---

## 🧪 Kualitas & Testing

```bash
pip install -e ".[dev]"
pytest                              # 103 tests passing
```

Mencakup: chunking, cleaning, hierarchy, embeddings, vectorstore, retrieval, generation, pipeline end-to-end (dengan mock embedder/LLM — cepat & offline).

---

## 📦 Tech Stack

| Lapisan | Teknologi |
|---|---|
| CLI | Typer, Rich |
| Config | Pydantic, PyYAML, python-dotenv |
| Parsing | Docling, PyMuPDF, python-docx, openpyxl, BeautifulSoup4 |
| Chunking | tiktoken (token-aware) |
| Embedding | sentence-transformers (BGE-m3) / OpenAI-compatible API |
| Vector DB | ChromaDB |
| LLM | OpenAI-compatible (GPT-4o, Llama 3, Qwen, dll) |
| API | FastAPI, Uvicorn |
| UI | Gradio |
| Testing | pytest (103 tests) |

Python 3.11+

---

## 📄 Lisensi

MIT

---

**SiberRAG** — RAG yang mengerti Bahasa Indonesia & struktur dokumen regulasi. Dibangun dari pengalaman nyata, bukan teori.

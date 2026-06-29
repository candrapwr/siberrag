# SiberRAG

> **Document Preprocessing Engine** — menghasilkan semantic chunk berkualitas tinggi untuk Retrieval-Augmented Generation (RAG).

SiberRAG mengubah dokumen (PDF, DOCX, XLSX, HTML, Markdown, TXT) menjadi chunk yang terstruktur dan siap digunakan oleh sistem embedding/retrieval apa pun. Versi 1 berfokus penuh pada **preprocessing & chunking** — tidak ada embedding, vector DB, atau chatbot.

## ✨ Fitur

- 🔍 **Multi-format parser**: Docling sebagai primary + fallback native otomatis (PyMuPDF, python-docx, openpyxl, BeautifulSoup4)
- 🧹 **Smart cleaning**: hapus header/footer berulang, page number, noise OCR — tanpa merusak struktur
- 🌳 **Hierarchy builder**: struktur tree Chapter → Section → Paragraph/List/Table
- 🧩 **Semantic block**: heading+isi, list, table, caption tetap utuh
- ✂️ **Token-aware chunking**: target 450–550 token (min 250, max 700), overlap 80–100, tidak pernah memotong kalimat/heading/list/table
- 📋 **Metadata lengkap**: page range, chapter, section, token/word count, language
- ✅ **Validator**: quality score 0–100 + warning & recommendation
- 📤 **Export**: JSON / JSONL / Markdown
- 🖥️ **Single-command CLI**: `siberrag process <path>`

## 🚀 Quick Start

```bash
# Instalasi (editable)
pip install -e .

# (Opsional) parser Docling
pip install -e ".[docling]"

# Proses dokumen
siberrag process ./documents
siberrag process regulasi.pdf --output ./output --format jsonl
```

## ⚙️ Konfigurasi

Semua parameter diatur via `config/config.yaml` (chunk size, overlap, OCR, parser, export, dll).

## 🏗️ Pipeline

```
Document → Detection → Parsing → Cleaning → Hierarchy →
Semantic Block → Chunk Builder → Metadata → Validator → Export
```

## 🧪 Testing

```bash
pip install -e ".[dev]"
pytest
```

## 📦 Tech Stack

Python 3.11+ · Typer · Pydantic · Rich · Loguru · Docling · PyMuPDF · python-docx · openpyxl · BeautifulSoup4 · tiktoken · pytest

---

SiberRAG v1 — fokus pada kualitas chunk. Embedding, retrieval, dan chatbot menyusul di versi berikutnya.

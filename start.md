# SiberRAG - PRD (Version 1)

## Overview

Bangun aplikasi bernama **SiberRAG** menggunakan **Python 3+**.

SiberRAG adalah **Document Preprocessing Engine** yang berfokus menghasilkan **semantic chunk berkualitas tinggi** untuk kebutuhan Retrieval-Augmented Generation (RAG).

Versi pertama **hanya fokus sampai menghasilkan chunk**. Belum mengimplementasikan embedding, vector database, retrieval, maupun chatbot.

Arsitektur harus modular sehingga pada versi berikutnya mudah dikembangkan menjadi platform RAG yang lengkap.

---

# Tech Stack

* Python 3
* Typer (CLI)
* Pydantic
* Rich
* Loguru
* Docling (parser utama)
* PyMuPDF
* python-docx
* openpyxl
* BeautifulSoup4
* tiktoken
* pytest

---

# Goals

* Menghasilkan semantic chunk berkualitas tinggi.
* Mempertahankan struktur asli dokumen.
* Pipeline berjalan otomatis.
* Modular dan mudah dikembangkan.
* Output siap digunakan oleh model embedding apa pun.

---

# Supported Documents

* PDF
* DOCX
* XLSX
* HTML
* Markdown
* TXT

---

# Project Structure

```text
siberrag/
│
├── siberrag_core/
│   ├── parsers/
│   ├── cleaners/
│   ├── hierarchy/
│   ├── semantic/
│   ├── chunker/
│   ├── validator/
│   ├── metadata/
│   ├── exporters/
│   ├── models/
│   └── utils/
│
├── siberrag_cli/
│
├── tests/
│
├── docs/
│
├── examples/
│
├── config/
│
├── pyproject.toml
└── README.md
```

---

# Pipeline

Pipeline berjalan **sepenuhnya otomatis**.

```
Document
    │
    ▼
Document Detection
    │
    ▼
Document Parsing
    │
    ▼
Cleaning
    │
    ▼
Hierarchy Builder
    │
    ▼
Semantic Block Builder
    │
    ▼
Chunk Builder
    │
    ▼
Metadata Builder
    │
    ▼
Chunk Validator
    │
    ▼
Export
```

Tidak ada proses manual untuk setiap tahap.

---

# Parser

Parser harus mempertahankan struktur dokumen.

Minimal mengenali:

* Heading
* Paragraph
* Bullet List
* Numbered List
* Table
* Caption
* Page
* Image Caption

Parser tidak boleh mengubah dokumen menjadi satu string panjang.

Parser harus menghasilkan representasi dokumen terstruktur.

---

# Cleaning

Hilangkan noise berikut:

* Repeated header
* Repeated footer
* Page number
* Multiple whitespace
* Empty line berlebihan
* Broken OCR characters
* Invalid unicode

Jangan menghapus:

* Heading
* List
* Numbering
* Table
* Caption
* Pasal
* Ayat
* Struktur dokumen

---

# Hierarchy Builder

Bangun struktur tree.

Contoh:

```
Document
│
├── Chapter
│   ├── Section
│   │   ├── Paragraph
│   │   ├── List
│   │   └── Table
```

Seluruh elemen memiliki parent-child relationship.

---

# Semantic Block Builder

Bangun semantic block berdasarkan struktur dokumen.

Aturan:

* Heading beserta isi tetap satu block.
* Table tetap utuh.
* Bullet list tetap utuh.
* Numbered list tetap utuh.
* Caption tetap bersama objeknya.
* Jangan memotong kalimat.

Semantic block adalah dasar pembentukan chunk.

---

# Chunk Builder

Chunk dibuat dari semantic block.

Rules:

* Target 450–550 token
* Minimum 250 token
* Maximum 700 token
* Overlap 80–100 token jika chunk harus dipecah
* Jangan memotong kalimat
* Jangan memotong heading
* Jangan memotong list
* Jangan memotong table
* Split hanya pada batas paragraf bila diperlukan

Ukuran chunk bersifat dinamis.

Prioritaskan kualitas dibanding jumlah token.

---

# Metadata Builder

Setiap chunk memiliki metadata minimal:

```json
{
  "id": "",
  "document_id": "",
  "filename": "",
  "page_start": 1,
  "page_end": 1,
  "chapter": "",
  "section": "",
  "chunk_index": 1,
  "total_chunk": 1,
  "token_count": 0,
  "word_count": 0,
  "language": ""
}
```

---

# Chunk Validator

Lakukan validasi otomatis.

Pastikan:

* Tidak ada heading kosong.
* Tidak ada sentence terpotong.
* Tidak ada list terpotong.
* Tidak ada table terpotong.
* Metadata lengkap.
* Token berada dalam batas ideal.
* Tidak ada duplicate chunk.

Setiap chunk memiliki:

* Quality Score
* Warning
* Recommendation

---

# Export

Support format:

* JSON
* JSONL
* Markdown

Semua metadata ikut diekspor.

---

# CLI Design

CLI menggunakan konsep **single command pipeline**.

Pengguna hanya menjalankan:

```bash
siberrag process <path>
```

Contoh:

```bash
siberrag process ./documents
```

```bash
siberrag process regulasi.pdf
```

```bash
siberrag process ./documents --output ./output
```

```bash
siberrag process ./documents --format jsonl
```

Engine akan menjalankan seluruh pipeline secara otomatis.

---

# Console Output

```text
🚀 SiberRAG

Scanning documents...
Parsing documents...
Cleaning...
Building hierarchy...
Creating semantic blocks...
Generating chunks...
Building metadata...
Validating chunks...
Exporting...

Done!

Documents : 15
Chunks    : 842
Output    : ./output
```

Gunakan progress bar, logging yang jelas, dan ringkasan hasil di akhir proses.

---

# Configuration

Gunakan file `config.yaml`.

Semua parameter dapat diubah melalui konfigurasi, seperti:

* Chunk size
* Min token
* Max token
* Overlap
* Output format
* OCR
* Parser
* Export directory

CLI otomatis membaca konfigurasi tanpa perlu menjalankan setiap tahap secara manual.

---

# Coding Standards

* Clean Architecture
* SOLID Principle
* Modular
* Type Hint
* Unit Test
* Logging
* Configurable
* Extensible
* Dokumentasi lengkap

---

# Future Roadmap

Versi berikutnya akan menambahkan:

* Embedding Engine
* Model Manager
* HuggingFace Integration
* Ollama Integration
* OpenAI Integration
* Vector Database
* PostgreSQL + pgvector
* Qdrant
* ChromaDB
* Hybrid Search
* Reranker
* Retrieval Engine
* REST API
* Desktop GUI
* Plugin System
* Workflow Builder

Engine inti tetap digunakan oleh seluruh versi (CLI, Desktop, API) tanpa mengubah logika preprocessing.

---

# Development Principle

Fokus utama SiberRAG adalah menghasilkan **semantic chunk berkualitas tinggi** yang dapat digunakan oleh sistem RAG apa pun.

Versi pertama harus stabil, modular, mudah diuji, dan mudah dikembangkan sebelum menambahkan fitur embedding dan retrieval.

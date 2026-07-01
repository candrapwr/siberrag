# Panduan Pemakaian SiberRAG

Panduan lengkap cara memakai SiberRAG — dari instalasi, konfigurasi, indexing dokumen, sampai tanya-jawab (RAG).

---

## Daftar Isi

- [1. Instalasi](#1-instalasi)
- [2. Konfigurasi](#2-konfigurasi)
- [3. Index Dokumen](#3-index-dokumen)
- [4. Tanya Jawab (RAG)](#4-tanya-jawab-rag)
- [5. REST API](#5-rest-api)
- [6. Web UI](#6-web-ui)
- [7. Command Reference](#7-command-reference)
- [8. Troubleshooting](#8-troubleshooting)

---

## 1. Instalasi

### Prasyarat
- Python 3.11+
- pip

### Langkah instalasi

```bash
# Clone & masuk folder
git clone <repo-url> siberrag
cd siberrag

# Buat virtual environment
python3.11 -m venv .venv
source .venv/bin/activate    # Linux/macOS
# .venv\Scripts\activate     # Windows

# Install SiberRAG + fitur RAG + API
pip install -e ".[rag,rag-openai,api]"
```

### Opsi extras (pilih sesuai kebutuhan)

| Extra | Isi | Kapan dipakai |
|---|---|---|
| `rag` | ChromaDB, sentence-transformers, numpy | Selalu (fitur RAG inti) |
| `rag-openai` | openai SDK | Embedding/LLM via API |
| `api` | FastAPI, Uvicorn | REST API server |
| `ui` | Gradio | Web UI chat |
| `docling` | Docling | Parser PDF/DOCX canggih |
| `dev` | pytest, pytest-cov | Development/testing |

Install semuanya sekaligus:
```bash
pip install -e ".[rag,rag-openai,api,ui,docling,dev]"
```

### Verifikasi instalasi

```bash
siberrag info
```
Akan menampilkan format yang didukung + config aktif.

---

## 2. Konfigurasi

### 2.1 API Key (Wajib untuk mode API)

SiberRAG membaca API key dari file `.env` secara otomatis (tidak perlu `export` manual).

```bash
# Salin template
cp .env.example .env

# Edit .env, isi API key Anda
# OPENAI_API_KEY=key-anda-disini
```

> ⚠️ **Penting**: File `.env` sudah di-gitignore dan tidak akan pernah di-commit. Jangan taruh API key di `config/config.yaml`.

### 2.2 Provider Embedding & LLM

Atur di `config/config.yaml`. Ada 3 mode:

#### Mode A: Custom API (DeepInfra) — default, cepat
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

#### Mode B: Local (offline, gratis, privasi penuh)
```yaml
embedding:
  provider: "local"
  model: "BAAI/bge-m3"
  dim: 1024
  # tidak perlu api_base/api_key
```
> Catatan: mode local butuh download model (~2GB) sekali saja, lalu berjalan offline.

#### Mode C: OpenAI resmi
```yaml
embedding:
  provider: "openai"
  model: "text-embedding-3-small"
  dim: 1536

llm:
  provider: "openai"
  model: "gpt-4o-mini"
```

### Provider lain yang didukung (mode `custom`)

Cukup ganti `api_base` dan `model`:

| Provider | api_base | Contoh model |
|---|---|---|
| DeepInfra | `https://api.deepinfra.com/v1` | BAAI/bge-m3, meta-llama/Llama-3-8B |
| Jina AI | `https://api.jina.ai/v1` | jina-embeddings-v3 |
| Together AI | `https://api.together.xyz/v1` | BAAI/bge-large |
| Ollama (lokal) | `http://localhost:11434/v1` | nomic-embed-text, llama3 |
| LM Studio (lokal) | `http://localhost:1234/v1` | bge-m3 |

### 2.3 Parameter lain

Lihat & edit `config/config.yaml` untuk:
- `chunking`: ukuran chunk (target/min/max token), overlap, hard heading boundary
- `retrieval`: top_k (jumlah sumber), score_threshold
- `vector_db`: nama collection, path penyimpanan

Cek config aktif:
```bash
siberrag info
```

---

## 3. Index Dokumen

Indexing = mengubah dokumen menjadi chunk → embedding → simpan ke vector DB. **Dilakukan sekali per dokumen.**

### Index 1 file

```bash
siberrag index regulasi.pdf
```

### Index seluruh folder (otomatis scan semua format)

```bash
siberrag index ./dokumen
```

Mendukung: PDF, DOCX, XLSX/XLSM, CSV/TSV, HTML, Markdown, TXT.

Jika extra `docling` dipasang, mode parser `auto` juga bisa menangani format
Docling-only seperti PPTX dan gambar (`PNG/JPG/JPEG`). Untuk format tersebut,
pakai:
```bash
pip install -e ".[docling]"
```

### Pakai collection berbeda (pisah per topik/proyek)

```bash
siberrag index uu.pdf --collection peraturan-negara
siberrag index novel.txt --collection sastra
```

### Cek statistik vector DB

```bash
siberrag stats
```

Contoh output:
```
Vector DB stats:
  Collection : siberrag
  Total chunk: 107
  Collections: siberrag, peraturan-negara, sastra
```

### Index ulang (re-embed)

Indexing bersifat idempotent — chunk dengan ID sama akan diperbarui, tidak digandakan. Untuk re-index, jalankan ulang perintah yang sama.

> ⚠️ Jika ganti model embedding, **hapus folder `vectorstore/` dulu** karena dimensi vektor berbeda:
> ```bash
> rm -rf vectorstore
> siberrag index dokumen.pdf
> ```

---

## 4. Tanya Jawab (RAG)

### Pertanyaan biasa (full RAG + jawaban LLM)

```bash
siberrag query "Apa kewajiban penyelenggara sistem elektronik?"
```

Contoh output:
```
Jawaban:
Menurut Pasal 15, setiap penyelenggara wajib menjaga kerahasiaan data...
(Sumber: hal. 3, skor 0.84)

Sumber (5):
  1. Pasal 15 | hal.3 | skor=0.843 | regulasi.pdf
  2. Pasal 16 | hal.4 | skor=0.789 | regulasi.pdf
  ...
```

### Lihat sumber saja tanpa LLM (gratis, cepat)

```bash
siberrag query "kewajiban penyelenggara" --retrieve-only
```

Berguna untuk debugging retrieval atau bila tidak punya API key LLM.

### Batasi jumlah sumber

```bash
siberrag query "..." --top-k 3      # ambil 3 chunk paling relevan
siberrag query "..." --top-k 10     # ambil 10 chunk
```

### Pertanyaan natural diperbolehkan

SiberRAG memahami Bahasa Indonesia natural, bukan keyword. Anda bisa bertanya:
- ✅ "gimana sih sebenarnya cara bikin perusahaan itu resmi?"
- ✅ "aku dengar katanya ada aturan soal data pribadi, jelasin dong"
- ✅ "berapa lama sih orang bisa jadi presiden?"

Tidak perlu keyword formal. Sistem memahami maksudnya.

### Contoh nyata

```bash
# Setelah index UUD 1945
siberrag query "Berapa lama masa jabatan presiden dan apakah bisa dipilih kembali?"
# Jawaban: "5 tahun, dapat dipilih kembali. (Pasal 7, skor 0.84)"

siberrag query "Apa saja hak warga negara?"
# Jawaban: "Hak warga negara meliputi: mendapatkan pendidikan, pekerjaan..."
```

---

## 5. REST API

Untuk integrasi dengan aplikasi lain (web, mobile, bot, dll).

### Jalankan server

```bash
siberrag serve --port 8000
```

Dokumentasi API otomatis: http://localhost:8000/docs

> Untuk akses dari device lain di jaringan yang sama (HP/tablet), gunakan `--host 0.0.0.0`:
> ```bash
> siberrag serve --host 0.0.0.0 --port 8000
> ```
> Lalu akses via `http://<IP-komputer>:8000` dari device lain.

### Endpoints

#### Health check
```bash
curl http://localhost:8000/api/health
# {"status":"ok","version":"2.0.0"}
```

#### Statistik vector DB
```bash
curl http://localhost:8000/api/stats
```

#### Index dokumen
```bash
curl -X POST http://localhost:8000/api/index \
  -F "file=@dokumen.pdf"
```

Dengan collection berbeda:
```bash
curl -X POST "http://localhost:8000/api/index?collection=peraturan-negara" \
  -F "file=@dokumen.pdf"
```

#### Tanya jawab
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question":"apa kewajiban penyelenggara?","top_k":5}'
```

Response:
```json
{
  "question": "apa kewajiban penyelenggara?",
  "answer": "Menurut Pasal 15...",
  "sources": [
    {"chunk_id":"...","score":0.84,"text":"...","chapter":"...","section":"...","page_start":3}
  ],
  "model": "meta-llama/Meta-Llama-3-8B-Instruct"
}
```

#### Retrieve-only (tanpa LLM)
```bash
curl -X POST http://localhost:8000/api/retrieve \
  -H "Content-Type: application/json" \
  -d '{"question":"...","top_k":5}'
```

---

## 6. Web UI

Chat interface berbasis Gradio untuk tanya-jawab interaktif.

### Install & jalankan

```bash
pip install -e ".[rag,rag-openai,ui]"
# reinstall agar siberrag_ui terdeteksi (bila baru install ulang)
pip install -e . --no-deps
python -m siberrag_ui.app
```

Buka http://localhost:7860 di browser.

### Fitur Web UI
- Input pertanyaan
- Slider top-k (jumlah sumber)
- Jawaban + source citations (bab/pasal/halaman)
- History percakapan

> Pastikan dokumen sudah di-index dulu via CLI (`siberrag index`) sebelum pakai Web UI.

---

## 7. Command Reference

### Semua command CLI

| Command | Fungsi | Contoh |
|---|---|---|
| `siberrag process <path>` | Chunk dokumen saja (v1, tanpa RAG) | `siberrag process dokumen.pdf --format jsonl` |
| `siberrag index <path>` | Index ke vector DB (v2 RAG) | `siberrag index dokumen.pdf` |
| `siberrag query "<q>"` | Tanya jawab RAG penuh | `siberrag query "apa kewajiban saya?"` |
| `siberrag stats` | Statistik vector DB | `siberrag stats` |
| `siberrag serve` | Jalankan REST API server | `siberrag serve --port 8000` |
| `siberrag info` | Tampilkan config & format didukung | `siberrag info` |

### Opsi umum (berlaku semua command)

| Opsi | Fungsi |
|---|---|
| `--config <path>` / `-c` | Path file config.yaml custom |
| `--verbose` / `-v` | Logging DEBUG (untuk debugging) |

### Opsi khusus

```bash
# process
siberrag process <path> --output <dir> --format <json|jsonl|markdown>

# index
siberrag index <path> --collection <nama> --min-quality <skor>

# query
siberrag query "<q>" --top-k <n> --retrieve-only --document <doc_id>

# serve
siberrag serve --host <ip> --port <port>
```

---

## 8. Troubleshooting

### "API key tidak ditemukan"

```
EmbeddingError: API key tidak ditemukan. Set OPENAI_API_KEY atau isi config...
```

**Solusi**: Buat file `.env` di root proyek:
```bash
echo 'OPENAI_API_KEY=key-anda' > .env
```

### "Gagal memanggil endpoint embedding"

```
EmbeddingError: Gagal memanggil endpoint embedding: 401 Unauthorized
```

**Penyebab**: API key salah/expired, atau `api_base` salah.

**Solusi**:
1. Cek API key valid di dashboard provider (DeepInfra/OpenAI/dll)
2. Pastikan `api_base` di `config/config.yaml` benar
3. Untuk endpoint lokal (Ollama), pastikan server berjalan

### Embedding dimension mismatch

```
Error: collection dim 1024 tapi model 1536
```

**Penyebab**: Ganti model embedding tanpa hapus vectorstore lama.

**Solusi**:
```bash
rm -rf vectorstore
siberrag index dokumen.pdf
```

### "No module named 'siberrag_api'" saat `siberrag serve`

```
ModuleNotFoundError: No module named 'siberrag_api'
```

**Penyebab**: Package `siberrag_api`/`siberrag_ui` belum terdaftar di editable install (mis. folder dibuat setelah `pip install -e .` dijalankan, atau clone baru tanpa reinstall).

**Solusi**: Reinstall package agar discovery scan ulang:
```bash
pip install -e ".[rag,rag-openai,api]" --no-deps
# atau minimal:
pip install -e . --no-deps
```

### "No module named 'siberrag_core.vectorstore'" saat `siberrag index`

```
ModuleNotFoundError: No module named 'siberrag_core.vectorstore'
```

**Penyebab**: Editable install/venv masih mengarah ke versi lama yang belum
mendaftarkan package `siberrag_core.vectorstore`, atau package baru dibuat
setelah `pip install -e .` terakhir.

**Solusi**: Aktifkan venv yang benar lalu reinstall package:
```bash
source .venv/bin/activate
pip install -e ".[rag,rag-openai,api]" --no-deps
# bila dependency RAG belum pernah dipasang:
pip install -e ".[rag,rag-openai,api]"
```

Cek import setelah reinstall:
```bash
python -c "import siberrag_core.vectorstore; print('ok')"
```

### Model local lambat saat startup

Mode `local` (sentence-transformers) download model 2GB di first-run. Setelah itu, load model ~30 detik tiap startup.

**Solusi**: Bila lambat, pakai mode API (`custom`) yang tidak butuh download.

### Retrieval tidak menemukan jawaban

1. Pastikan dokumen sudah di-index: `siberrag stats`
2. Coba retrieve-only untuk lihat sumber: `siberrag query "..." --retrieve-only --top-k 10`
3. Turunkan `score_threshold` di config (mis. dari 0.3 ke 0.1) bila chunk relevan di-filter
4. Pertanyaan natural (panjang) biasanya lebih akurat daripada keyword pendek

### Web UI tidak bisa connect

1. Pastikan dokumen sudah di-index via CLI
2. Pastikan port tidak bentrok: `python -m siberrag_ui.app` (default 7860)
3. Cek API key di `.env` terisi

### Reset total

```bash
rm -rf vectorstore output
siberrag index dokumen.pdf
```

---

## Tips & Best Practices

1. **Index per topik**: Gunakan `--collection` untuk memisahkan dokumen per topik (mis. `peraturan`, `manual`, `faq`).

2. **Pertanyaan natural lebih baik**: Bertanyalah seperti chat, bukan keyword. Sistem memahami konteks.

3. **Retrieve-only untuk debugging**: Sebelum pakai LLM (berbayar), cek dulu retrieval relevan dengan `--retrieve-only`.

4. **Mode hybrid**: Index pakai API (cepat), tapi query bisa pakai local (gratis) — asal dimensi model sama.

5. **Re-index setelah edit config chunking**: Parameter chunking hanya berlaku saat index. Ubah config lalu re-index.

6. **Backup vectorstore**: Folder `vectorstore/` berisi semua embedding. Backup bila tidak ingin re-embed.

---

## Butuh bantuan?

- Cek config: `siberrag info`
- Debug detail: tambah `--verbose` di command
- Lihat log: pesan INFO/DEBUG di terminal

# SiberRAG - Arsitektur

## Ringkasan

SiberRAG adalah **Document Preprocessing Engine** yang menghasilkan semantic chunk
berkualitas tinggi untuk RAG. Versi 1 berfokus penuh pada preprocessing & chunking.

## Prinsip Desain

- **Clean Architecture**: core engine terpisah dari CLI; bisa dipakai programatik.
- **SOLID**: setiap modul punya satu tanggung jawab, bergantung pada abstraksi.
- **Unified IR**: semua parser menghasilkan `DocumentElement` tree yang seragam,
  sehingga tahap downstream tidak peduli format asli.
- **Configurable**: semua parameter via `config/config.yaml`.
- **Extensible**: tambah parser/cleaner/exporter cukup daftarkan di registry.

## Pipeline (9 tahap)

```
Document
    │
    ▼
1. Document Detection   (parsers/detector.py)    - scan file/direktori
    │
    ▼
2. Document Parsing     (parsers/registry.py)     - Docling primary + native fallback
    │                                                  -> DocumentElement tree
    ▼
3. Cleaning             (cleaners/cleaner.py)     - 6 rule: noise removal tanpa rusak struktur
    │
    ▼
4. Hierarchy Builder    (hierarchy/builder.py)    - flat elements -> parent-child tree
    │
    ▼
5. Semantic Block       (semantic/builder.py)     - group heading+isi, jaga list/table utuh
    │                                                  -> list[SemanticBlock]
    ▼
6. Chunk Builder        (chunker/tokenizer.py)    - token-aware chunking (tiktoken)
    │                                                  target 450-550, max 700, overlap 80-100
    ▼
7. Metadata Builder     (metadata/builder.py)     - bahasa, token/word count, page range
    │
    ▼
8. Chunk Validator      (validator/validator.py)  - quality score 0-100 + warnings
    │
    ▼
9. Export               (exporters/registry.py)   - JSON / JSONL / Markdown
```

## Intermediate Representation

### DocumentElement
Node dalam tree dokumen. Field utama:
- `type`: `ElementType` (DOCUMENT, HEADING, PARAGRAPH, BULLET_LIST, NUMBERED_LIST,
  LIST_ITEM, TABLE, TABLE_ROW, TABLE_CELL, CAPTION, PAGE_BREAK, IMAGE_CAPTION)
- `content`: teks utama
- `level`: level heading (1-6)
- `page_start`/`page_end`: rentang halaman
- `children`: turunan (untuk container)

### SemanticBlock
Unit semantik utuh (heading+isi, atau table/list/caption tersendiri).
Dasar pembentukan chunk.

### Chunk
Satu chunk + `ChunkMetadata` (id, document_id, filename, page_start/end,
chapter, section, chunk_index, total_chunk, token_count, word_count, language).

## Strategi Parser

| Mode | Perilaku |
|------|----------|
| `auto` (default) | Docling bila tersedia & mendukung; fallback native otomatis bila gagal |
| `docling` | Paksa Docling (error bila tidak terinstal) |
| `native` | Paksa parser native per-format |

Parser native: PyMuPDF (PDF), python-docx (DOCX), openpyxl (XLSX),
BeautifulSoup4 (HTML), parser builtin (MD/TXT).

## Aturan Chunking

- Target 450-550 token, minimum 250, maksimum 700.
- Overlap 80-100 token bila chunk harus dipecah.
- **Tidak pernah** memotong kalimat, heading, list, atau table.
- Heading/list/table = unit atomic (tidak dipecah walau > target).
- Paragraf dipecah di batas kalimat; fallback batas paragraf bila perlu.
- Chunk kecil bertetangga digabung bila memungkinkan.

## Quality Score

Validator menghitung skor 0-100. Penalti:
- OVERSIZED (>700 tok): -15
- UNDERSIZED (<250 tok): -8
- POSSIBLE_TRUNC_START/END: -10
- EMPTY_HEADING: -20
- INCOMPLETE_METADATA: -5
- DUPLICATE: -12

## Paket

```
siberrag_core/     # engine inti (dapat dipakai tanpa CLI)
  config.py        # AppConfig + YAML loader
  pipeline.py      # orchestrator 9 tahap
  models/          # DocumentElement, SemanticBlock, Chunk, Validation
  parsers/         # base, registry, docling + 6 native
  cleaners/        # base + 6 rule
  hierarchy/       # tree builder
  semantic/        # block builder
  chunker/         # token-aware chunker
  metadata/        # metadata enricher
  validator/       # quality scoring
  exporters/       # JSON / JSONL / Markdown
  utils/           # logging, tokens, text, ids, language
siberrag_cli/      # Typer CLI (single command pipeline)
tests/             # 50 unit + integration test
config/            # config.yaml
```

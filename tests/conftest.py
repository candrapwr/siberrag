"""Pytest fixtures & sample dokumen untuk testing."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from siberrag_core.models.elements import (
    Document,
    DocumentElement,
    ElementType,
)


# ============================================================
# v2 fixtures - mock embedder/LLM (offline, deterministik)
# ============================================================


class MockEmbedder:
    """Embedder mock deterministik: hash teks -> vektor.

    Menghasilkan vektor yang konsisten untuk teks yang sama, sehingga
    retrieval bisa diuji tanpa model/API asli. Vektor "mirip" untuk teks
    yang berbagi kata (berbasis bag-of-words sederhana).
    """

    name = "mock"
    _DIM = 64

    def __init__(self, config=None) -> None:
        self.config = config
        self._vocab: dict[str, int] = {}

    def _text_to_vec(self, text: str) -> list[float]:
        vec = [0.0] * self._DIM
        # normalisasi: lowercase + split kata
        words = [w.strip(".,;:!?\"'()[]").lower() for w in text.split()]
        for w in words:
            if not w:
                continue
            if w not in self._vocab:
                # index deterministik dari hash kata
                self._vocab[w] = int(hashlib.md5(w.encode()).hexdigest(), 16) % self._DIM
            vec[self._vocab[w]] += 1.0
        # L2 normalize
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed(self, text: str) -> list[float]:
        return self._text_to_vec(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self._text_to_vec(t) for t in texts]

    @property
    def dimension(self) -> int:
        return self._DIM


class MockLLM:
    """LLM mock: kembalikan jawaban deterministik dari pesan user."""

    name = "mock"

    def __init__(self, config=None) -> None:
        self.config = config
        self.calls: list[list[dict]] = []

    def generate(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        # ekstrak pertanyaan dari pesan user terakhir
        user_msg = ""
        for m in reversed(messages):
            if m["role"] == "user":
                user_msg = m["content"]
                break
        return f"[MOCK ANSWER] Berdasarkan konteks, jawaban untuk: {user_msg[:50]}"


@pytest.fixture
def mock_embedder() -> "MockEmbedder":
    """Embedder mock deterministik (offline)."""
    return MockEmbedder()


@pytest.fixture
def mock_llm() -> "MockLLM":
    """LLM mock deterministik (offline)."""
    return MockLLM()


@pytest.fixture
def sample_chunks() -> list:
    """Daftar chunk sample untuk testing vectorstore/retriever."""
    from siberrag_core.models.chunk import Chunk, ChunkMetadata

    return [
        Chunk(
            id="doc_c0000",
            text="Kucing adalah hewan mamalia yang suka memakan ikan dan tidur.",
            metadata=ChunkMetadata(
                id="doc_c0000", document_id="doc", filename="hewan.txt",
                page_start=1, page_end=1, chapter="Mamalia", section="Kucing",
                chunk_index=0, total_chunk=3, token_count=15, word_count=10,
                language="id", block_type="paragraph",
            ),
        ),
        Chunk(
            id="doc_c0001",
            text="Anjing adalah hewan peliharaan setia yang bisa diajak bermain.",
            metadata=ChunkMetadata(
                id="doc_c0001", document_id="doc", filename="hewan.txt",
                page_start=1, page_end=1, chapter="Mamalia", section="Anjing",
                chunk_index=1, total_chunk=3, token_count=14, word_count=9,
                language="id", block_type="paragraph",
            ),
        ),
        Chunk(
            id="tekno_c0000",
            text="Python adalah bahasa pemrograman populer untuk data science.",
            metadata=ChunkMetadata(
                id="tekno_c0000", document_id="tekno", filename="tekno.txt",
                page_start=1, page_end=1, chapter="Programming", section="Python",
                chunk_index=0, total_chunk=1, token_count=10, word_count=8,
                language="id", block_type="paragraph",
            ),
        ),
    ]


@pytest.fixture
def sample_md_text() -> str:
    """Markdown sample dengan heading, paragraf, list, dan table."""
    return """# Bab I - Pendahuluan

Ini adalah paragraf pertama yang cukup panjang untuk menjadi sebuah chunk yang
layak. Tujuannya hanya untuk memberikan konteks dan memastikan bahwa pipeline
dapat mempertahankan struktur dokumen dengan baik tanpa memotong kalimat.

## Pasal 1 - Definisi

Dalam peraturan ini, istilah-istilah berikut memiliki arti sebagai berikut:

- Siber adalah ruang komunikasi elektronik.
- Data adalah informasi yang direkam dalam format digital.
- Sistem adalah kumpulan komponen yang saling berinteraksi.

## Pasal 2 - Ruang Lingkup

Aturan ini berlaku untuk seluruh entitas yang beroperasi di sektor siber.

| No | Entitas | Kewajiban |
|----|---------|-----------|
| 1  | Penyelenggara | Menerapkan keamanan |
| 2  | Pengguna | Mematuhi aturan |

# Bab II - Ketentuan Umum

Setiap penyelenggara sistem elektronik wajib menjaga kerahasiaan data yang
dikelolanya. Pelanggaran terhadap ketentuan ini akan dikenai sanksi sesuai
peraturan yang berlaku.
"""


@pytest.fixture
def sample_md_file(tmp_path: Path, sample_md_text: str) -> Path:
    p = tmp_path / "regulasi.md"
    p.write_text(sample_md_text, encoding="utf-8")
    return p


@pytest.fixture
def sample_txt_file(tmp_path: Path) -> Path:
    p = tmp_path / "notes.txt"
    p.write_text(
        "PENDAHULUAN\n"
        "Teks ini menjelaskan dasar dari sistem yang akan dibangun. "
        "Sistem harus mampu memproses data dengan cepat dan akurat.\n\n"
        "- Item pertama\n"
        "- Item kedua\n"
        "- Item ketiga\n",
        encoding="utf-8",
    )
    return p


@pytest.fixture
def simple_document() -> Document:
    """Dokumen dengan struktur flat (sebelum HierarchyBuilder)."""
    root = DocumentElement.document(order=0)
    root.add(DocumentElement.heading("Bab I", level=1, page=1))
    root.add(DocumentElement.paragraph("Paragraf isi bab I halaman 1.", page=1))
    root.add(DocumentElement.heading("Pasal 1", level=2, page=1))
    root.add(DocumentElement.paragraph("Isi pasal 1.", page=1))
    root.add(DocumentElement.heading("Bab II", level=1, page=2))
    root.add(DocumentElement.paragraph("Paragraf isi bab II halaman 2.", page=2))
    return Document(root=root, filename="test.doc", document_id="doc_test")

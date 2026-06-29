"""Pytest fixtures & sample dokumen untuk testing."""

from __future__ import annotations

from pathlib import Path

import pytest

from siberrag_core.models.elements import (
    Document,
    DocumentElement,
    ElementType,
)


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

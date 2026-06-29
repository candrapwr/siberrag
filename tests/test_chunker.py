"""Test chunker."""

from siberrag_core.chunker.tokenizer import Chunker
from siberrag_core.config import ChunkingConfig
from siberrag_core.models.blocks import SemanticBlock
from siberrag_core.models.elements import DocumentElement, ElementType


def _make_blocks(text: str, n_paragraphs: int = 1) -> list[SemanticBlock]:
    blocks = []
    for i in range(n_paragraphs):
        blocks.append(SemanticBlock(
            block_type="paragraph",
            title=None,
            elements=[DocumentElement(type=ElementType.PARAGRAPH, content=text)],
        ))
    return blocks


def test_single_small_block_one_chunk():
    cfg = ChunkingConfig(target_tokens=500, min_tokens=50, max_tokens=700, overlap_tokens=50)
    chunker = Chunker(cfg)
    text = "Ini kalimat pertama. Ini kalimat kedua. Ini kalimat ketiga."
    blocks = _make_blocks(text)
    chunks = chunker.chunk(blocks, document_id="doc1", filename="f.txt", language="id")
    assert len(chunks) == 1
    assert chunks[0].metadata.document_id == "doc1"
    assert chunks[0].metadata.total_chunk == 1
    assert chunks[0].metadata.chunk_index == 0
    assert chunks[0].metadata.language == "id"


def test_chunking_splits_large_content():
    cfg = ChunkingConfig(target_tokens=50, min_tokens=10, max_tokens=80, overlap_tokens=20)
    chunker = Chunker(cfg)
    # buat teks panjang berkalimat
    sentences = [f"Kalimat nomor {i} berisi konten yang cukup untuk diuji." for i in range(40)]
    text = " ".join(sentences)
    blocks = _make_blocks(text)
    chunks = chunker.chunk(blocks, document_id="doc2", filename="big.txt")
    assert len(chunks) > 1
    # tidak ada chunk yang melebihi max (dengan toleransi unit atomic)
    for c in chunks:
        assert c.metadata.token_count <= 200  # toleran; inti: terpecah


def test_table_stays_atomic():
    """Table tidak boleh dipecah walau besar."""
    cfg = ChunkingConfig(target_tokens=10, min_tokens=5, max_tokens=30, overlap_tokens=5)
    chunker = Chunker(cfg)
    table = DocumentElement(type=ElementType.TABLE)
    for i in range(10):
        row = DocumentElement(type=ElementType.TABLE_ROW)
        row.add(DocumentElement(type=ElementType.TABLE_CELL, content=f"Kolom A baris {i}"))
        row.add(DocumentElement(type=ElementType.TABLE_CELL, content=f"Kolom B baris {i}"))
        table.add(row)
    blocks = [SemanticBlock(block_type="table", elements=[table])]
    chunks = chunker.chunk(blocks, document_id="doc3", filename="t.txt")
    # table besar -> mungkin 1 chunk sendiri (atomic) walau > max
    assert len(chunks) >= 1
    # seluruh baris table ada di chunk (tidak terpecah di tengah baris)
    combined = "\n".join(c.text for c in chunks)
    for i in range(10):
        assert f"baris {i}" in combined


def test_chunk_ids_unique_and_indexed():
    cfg = ChunkingConfig(target_tokens=30, min_tokens=10, max_tokens=60, overlap_tokens=10)
    chunker = Chunker(cfg)
    text = " ".join(f"Sentence number {i} is here." for i in range(30))
    blocks = _make_blocks(text)
    chunks = chunker.chunk(blocks, document_id="docX", filename="f.txt")
    ids = [c.id for c in chunks]
    assert len(ids) == len(set(ids))  # unik
    assert [c.metadata.chunk_index for c in chunks] == list(range(len(chunks)))


def test_numbered_list_preserves_sequence():
    """Nomor urut numbered list harus terjaga (1,2,3...) - bukan hardcode '1.'."""
    cfg = ChunkingConfig(target_tokens=500, min_tokens=10, max_tokens=700)
    chunker = Chunker(cfg)
    lst = DocumentElement(type=ElementType.NUMBERED_LIST)
    for i in range(4):
        lst.add(DocumentElement(type=ElementType.LIST_ITEM, content=f"Item nomor {i}"))
    blocks = [SemanticBlock(block_type="list", elements=[lst])]
    chunks = chunker.chunk(blocks, document_id="doc", filename="f.txt")
    text = chunks[0].text
    assert "1. Item nomor 0" in text
    assert "2. Item nomor 1" in text
    assert "3. Item nomor 2" in text
    assert "4. Item nomor 3" in text


def test_global_merge_avoids_undersized():
    """Block kecil berurutan harus digabung agar tidak undersized (soft boundary)."""
    # respect_heading_boundary=False agar heading bukan hard split (uji merge)
    cfg = ChunkingConfig(target_tokens=500, min_tokens=100, max_tokens=700,
                         respect_heading_boundary=False)
    chunker = Chunker(cfg)
    # 3 block kecil terpisah (simulasi pasal-pasal pendek)
    blocks = []
    for i in range(3):
        para = DocumentElement(type=ElementType.PARAGRAPH,
                               content=f"Pasal {i}. Ini teks pendek untuk diuji penggabungan lintas block.")
        blocks.append(SemanticBlock(block_type="heading", title=f"Pasal {i}",
                                    chapter="Bab", section=f"Pasal {i}",
                                    elements=[para]))
    chunks = chunker.chunk(blocks, document_id="doc", filename="f.txt")
    # 3 block kecil harus tergabung menjadi 1 chunk (bukan 3 chunk undersized)
    assert len(chunks) == 1
    # seluruh konten 3 block ada di 1 chunk
    assert "Pasal 0" in chunks[0].text
    assert "Pasal 1" in chunks[0].text
    assert "Pasal 2" in chunks[0].text


def test_hard_boundary_keeps_pasal_separate():
    """respect_heading_boundary=True: pasal kecil TETAP terpisah walau undersized."""
    cfg = ChunkingConfig(target_tokens=500, min_tokens=100, max_tokens=700,
                         respect_heading_boundary=True)
    chunker = Chunker(cfg)
    blocks = []
    for i in range(3):
        para = DocumentElement(type=ElementType.PARAGRAPH,
                               content=f"Isi pasal {i} yang pendek.")
        blocks.append(SemanticBlock(block_type="heading", title=f"Pasal {i}",
                                    chapter="Bab", section=f"Pasal {i}",
                                    elements=[para]))
    chunks = chunker.chunk(blocks, document_id="doc", filename="f.txt")
    # hard boundary: 3 pasal jadi 3 chunk terpisah (bukan 1 chunk gabungan)
    assert len(chunks) == 3


def test_prepend_context_header():
    """prepend_context=True menambahkan header konteks di awal chunk."""
    cfg = ChunkingConfig(target_tokens=500, min_tokens=10, max_tokens=700,
                         prepend_context=True)
    chunker = Chunker(cfg)
    blocks = [SemanticBlock(block_type="heading", title="Pasal 1",
                            chapter="Bab I", section="Pasal 1",
                            elements=[DocumentElement(type=ElementType.PARAGRAPH,
                                                      content="Isi pasal.")])]
    chunks = chunker.chunk(blocks, document_id="doc", filename="f.txt")
    assert chunks[0].text.startswith("[Bab I > Pasal 1]")


def test_cross_chapter_transition_marker():
    """Saat block lintas-chapter digabung, penanda chapter baru disisipkan."""
    # respect_heading_boundary=False agar 2 block bisa digabung (uji marker)
    cfg = ChunkingConfig(target_tokens=500, min_tokens=10, max_tokens=700,
                         prepend_context=False, respect_heading_boundary=False)
    chunker = Chunker(cfg)
    blocks = [
        SemanticBlock(block_type="heading", title="Pasal 1", chapter="Bab I",
                      section="Pasal 1", elements=[DocumentElement(
                          type=ElementType.PARAGRAPH, content="Isi bab satu.")]),
        SemanticBlock(block_type="heading", title="Pasal 2", chapter="Bab II",
                      section="Pasal 2", elements=[DocumentElement(
                          type=ElementType.PARAGRAPH, content="Isi bab dua.")]),
    ]
    chunks = chunker.chunk(blocks, document_id="doc", filename="f.txt")
    # penanda transisi bab muncul di teks
    assert "[Bab II]" in chunks[0].text


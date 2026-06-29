"""RAG prompt template - bangun prompt dari retrieved context + question.

Prompt dirancang untuk dokumen regulasi/hukum Indonesia: instruksi jawab
berdasarkan konteks, sebut sumber, dan akui bila tidak tahu.
"""

from __future__ import annotations

from siberrag_core.vectorstore.base import SearchResults

SYSTEM_PROMPT = """Anda adalah asisten SiberRAG, sebuah sistem tanya-jawab dokumen.
Tugas Anda menjawab pertanyaan pengguna BERDASARKAN konteks dokumen yang diberikan.

Aturan:
1. Jawab HANYA berdasarkan konteks yang diberikan. Jangan mengarang informasi.
2. Jika konteks tidak cukup untuk menjawab, katakan dengan jujur bahwa informasi tidak tersedia.
3. Sebutkan sumber referensi (bab/pasal/halaman) bila relevan.
4. Jawab dalam bahasa yang sama dengan pertanyaan (default: Bahasa Indonesia).
5. Jika pertanyaan ambigu, berikan jawaban berdasarkan interpretasi paling masuk akal dari konteks.
"""

CONTEXT_HEADER = "Berikut adalah konteks dari dokumen yang relevan dengan pertanyaan:"


def build_rag_prompt(question: str, results: SearchResults) -> list[dict[str, str]]:
    """Bangun pesan chat (system + user) untuk RAG.

    Returns:
        List pesan format OpenAI: [{"role": "system", ...}, {"role": "user", ...}]
    """
    # susun konteks dari hasil retrieval
    context_parts: list[str] = []
    for i, hit in enumerate(results.hits, start=1):
        m = hit.chunk.metadata
        source = []
        if m.chapter:
            source.append(m.chapter)
        if m.section and m.section != m.chapter:
            source.append(m.section)
        if m.page_start:
            source.append(f"hal. {m.page_start}")
        source_str = " > ".join(source) if source else m.filename
        context_parts.append(
            f"[Konteks {i}] (Sumber: {source_str}, skor: {hit.score:.2f})\n{hit.chunk.text}"
        )

    context_block = "\n\n".join(context_parts) if context_parts else "(Tidak ada konteks relevan ditemukan.)"

    user_prompt = f"""{CONTEXT_HEADER}

{context_block}

---
Pertanyaan: {question}

Jawab pertanyaan di atas berdasarkan konteks yang diberikan. Sebutkan sumber yang Anda gunakan."""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

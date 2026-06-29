"""Test generation layer (RAG prompt builder, Answer model, LLM)."""

from siberrag_core.generation.base import Answer
from siberrag_core.generation.prompts import SYSTEM_PROMPT, build_rag_prompt
from siberrag_core.models.chunk import Chunk, ChunkMetadata
from siberrag_core.models.elements import DocumentElement
from siberrag_core.vectorstore.base import SearchHit, SearchResults


def _make_results(texts: list[str], scores: list[float]) -> SearchResults:
    """Buat SearchResults mock dari list teks + skor."""
    hits = []
    for i, (text, score) in enumerate(zip(texts, scores)):
        chunk = Chunk(
            id=f"c{i}",
            text=text,
            metadata=ChunkMetadata(
                id=f"c{i}", document_id="doc", filename="f.txt",
                chapter=f"Bab {i}", section=f"Pasal {i}",
                page_start=i + 1, page_end=i + 1,
            ),
        )
        hits.append(SearchHit(chunk=chunk, score=score))
    return SearchResults(query="test", hits=hits)


def test_system_prompt_exists():
    assert "SiberRAG" in SYSTEM_PROMPT
    assert "konteks" in SYSTEM_PROMPT.lower()


def test_build_rag_prompt_returns_messages():
    results = _make_results(["Isi konteks 1"], [0.9])
    messages = build_rag_prompt("Apa jawabannya?", results)
    assert isinstance(messages, list)
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


def test_rag_prompt_includes_context():
    results = _make_results(["Pasal 1 berisi aturan penting"], [0.85])
    messages = build_rag_prompt("Apa isi Pasal 1?", results)
    user_content = messages[1]["content"]
    assert "Pasal 1 berisi aturan penting" in user_content
    assert "Apa isi Pasal 1?" in user_content


def test_rag_prompt_includes_source_citation():
    """Prompt harus sebut sumber (chapter/section/page)."""
    results = _make_results(["Kontens"], [0.7])
    messages = build_rag_prompt("q?", results)
    user_content = messages[1]["content"]
    assert "Bab 0" in user_content  # chapter
    assert "Pasal 0" in user_content  # section
    assert "hal." in user_content  # page


def test_rag_prompt_empty_context():
    """Bila tidak ada hasil retrieval, prompt tetap valid."""
    results = SearchResults(query="q", hits=[])
    messages = build_rag_prompt("pertanyaan", results)
    assert "Tidak ada konteks" in messages[1]["content"]


def test_rag_prompt_includes_score():
    """Skor relevansi harus muncul di prompt (untuk debugging)."""
    results = _make_results(["ctx"], [0.842])
    messages = build_rag_prompt("q", results)
    assert "0.84" in messages[1]["content"]


def test_answer_model_creation():
    a = Answer(question="q?", text="jawaban", model="mock-llm")
    assert a.question == "q?"
    assert a.text == "jawaban"
    assert a.model == "mock-llm"
    assert not a.is_error
    assert len(a.sources) == 0


def test_answer_error_state():
    a = Answer(question="q", error="connection failed")
    assert a.is_error
    assert a.to_dict()["error"] == "connection failed"


def test_answer_to_dict_with_sources():
    results = _make_results(["konten sumber"], [0.9])
    a = Answer(question="q", text="jawaban", sources=results, model="gpt")
    d = a.to_dict()
    assert d["question"] == "q"
    assert d["answer"] == "jawaban"
    assert len(d["sources"]) == 1
    assert d["sources"][0]["score"] == 0.9
    assert "chapter" in d["sources"][0]["metadata"]


def test_mock_llm_generate(mock_llm):
    """MockLLM harus return jawaban deterministik."""
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "Apa itu Python?"},
    ]
    out = mock_llm.generate(messages)
    assert "MOCK ANSWER" in out
    assert mock_llm.calls  # call tercatat


def test_mock_llm_records_calls(mock_llm):
    mock_llm.generate([{"role": "user", "content": "q1"}])
    mock_llm.generate([{"role": "user", "content": "q2"}])
    assert len(mock_llm.calls) == 2

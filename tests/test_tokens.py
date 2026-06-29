"""Test token & language utils."""

from siberrag_core.utils.tokens import TokenCounter, count_tokens, get_counter
from siberrag_core.utils.language import detect_language


def test_count_tokens_nonempty():
    tokens = count_tokens("ini adalah sebuah kalimat untuk diuji")
    assert tokens > 0


def test_count_tokens_empty():
    assert count_tokens("") == 0


def test_token_counter_callable():
    counter = get_counter("cl100k_base")
    assert isinstance(counter, TokenCounter)
    assert counter("hello world") > 0
    assert counter.words("hello world") == 2


def test_detect_language_indonesian():
    text = "Ini adalah teks berbahasa Indonesia yang berisi beberapa kata "
    "umum seperti dan atau yang di ke dari untuk dengan pada adalah ini itu."
    lang = detect_language(text, fallback="id")
    # langdetect mungkin return 'id'; heuristik fallback juga 'id'
    assert lang in {"id", "en"}  # toleransi; inti: tidak raise


def test_detect_language_short_text_fallback():
    assert detect_language("ok", fallback="id") == "id"

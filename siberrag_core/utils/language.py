"""Deteksi bahasa teks.

Menggunakan ``langdetect`` bila tersedia; bila tidak, fallback heuristik
berbasis frekuensi stopword Indonesia vs Inggris.
"""

from __future__ import annotations

from functools import lru_cache

try:
    from langdetect import detect as _langdetect_detect  # type: ignore
    _HAS_LANGDETECT = True
except Exception:  # pragma: no cover
    _HAS_LANGDETECT = False


_ID_STOPWORDS = {"dan", "atau", "yang", "di", "ke", "dari", "untuk", "dengan",
                 "pada", "adalah", "ini", "itu", "akan", "tidak", "dalam",
                 "atau", "juga", "oleh", "sebagai"}
_EN_STOPWORDS = {"the", "and", "or", "of", "to", "in", "for", "with", "on",
                 "is", "are", "this", "that", "a", "an", "by", "as", "not"}


@lru_cache(maxsize=1)
def _available() -> bool:
    return _HAS_LANGDETECT


def detect_language(text: str, *, fallback: str = "id") -> str:
    """Deteksi bahasa. Fallback heuristik bila ``langdetect`` tidak ada.

    Args:
        text: teks yang akan dideteksi.
        fallback: kode bahasa default bila teks terlalu pendek/ambigu.
    """
    sample = (text or "").strip()
    if len(sample.split()) < 5:
        return fallback

    if _available():
        try:
            lang = _langdetect_detect(sample)  # type: ignore[misc]
            return lang or fallback
        except Exception:
            pass

    # heuristik stopword
    tokens = {w.lower().strip(".,;:!?\"'()") for w in sample.split()}
    id_hits = len(tokens & _ID_STOPWORDS)
    en_hits = len(tokens & _EN_STOPWORDS)
    if id_hits == en_hits == 0:
        return fallback
    return "id" if id_hits >= en_hits else "en"

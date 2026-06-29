"""Token counter berbasis tiktoken dengan fallback heuristik.

tiktoken adalah dependency inti, namun bila encoding tertentu gagal
dimuat (mis. offline), kita fallback ke pendekatan kata-bobot.
"""

from __future__ import annotations

import functools
from typing import Optional

try:
    import tiktoken  # type: ignore
    _HAS_TIKTOKEN = True
except Exception:  # pragma: no cover - lingkungan tak terduga
    _HAS_TIKTOKEN = False


# rasio konversi kata -> token (perkiraan bahasa umum)
_WORD_TOKEN_RATIO = 1.33


@functools.lru_cache(maxsize=8)
def _get_encoding(name: str):
    """Ambil encoding tiktoken (di-cache)."""
    if not _HAS_TIKTOKEN:
        return None
    return tiktoken.get_encoding(name)  # type: ignore[union-attr]


def count_tokens(text: str, encoding: str = "cl100k_base") -> int:
    """Hitung jumlah token dari ``text``.

    Menggunakan tiktoken bila tersedia; bila tidak, estimasi dari jumlah kata.
    """
    if not text:
        return 0
    enc = _get_encoding(encoding)
    if enc is not None:
        try:
            return len(enc.encode(text))
        except Exception:
            pass
    # fallback heuristik
    return int(len(text.split()) * _WORD_TOKEN_RATIO)


def estimate_word_count(text: str) -> int:
    """Jumlah kata dalam ``text``."""
    if not text:
        return 0
    return len(text.split())


class TokenCounter:
    """Callable counter dengan encoding yang bisa dikonfigurasi."""

    def __init__(self, encoding: str = "cl100k_base") -> None:
        self.encoding = encoding

    def __call__(self, text: str) -> int:
        return count_tokens(text, self.encoding)

    def words(self, text: str) -> int:
        return estimate_word_count(text)


def get_counter(encoding: str = "cl100k_base") -> TokenCounter:
    """Factory TokenCounter."""
    return TokenCounter(encoding=encoding)

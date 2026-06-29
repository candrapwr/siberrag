"""Auto-loader untuk file .env.

Memuat variabel dari file .env (di root proyek) ke environment agar
OPENAI_API_KEY & var lain terbaca otomatis tanpa export manual.

Idempoten: aman dipanggil berkali-kali. Dipanggil sekali saat startup
(CLI, API server) sebelum config/provider di-inisialisasi.
"""

from __future__ import annotations

from pathlib import Path

_LOADED = False


def load_env(path: Path | str | None = None) -> bool:
    """Muat file .env ke environment. Return True bila file dimuat.

    Args:
        path: path file .env eksplisit. Bila None, cari di:
              1. direktori kerja saat ini (./.env)
              2. root proyek (parent dari siberrag_core/)
    """
    global _LOADED
    if _LOADED and path is None:
        return True  # sudah pernah dimuat (default path)

    try:
        from dotenv import load_dotenv as _load_dotenv
    except Exception:
        return False  # python-dotenv tidak ada -> skip silently

    if path is not None:
        target = Path(path)
        if target.exists():
            _load_dotenv(target, override=False)
            _LOADED = True
            return True
        return False

    # cari .env di beberapa lokasi default
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
    ]
    for cand in candidates:
        if cand.exists():
            _load_dotenv(cand, override=False)
            _LOADED = True
            return True
    _LOADED = True  # tandai sudah dicari walau tidak ada file
    return False

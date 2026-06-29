"""Orchestrator cleaning - menjalankan rule sesuai konfigurasi.

Urutan eksekusi penting:
1. normalize unicode -> perbaiki OCR -> (siapkan teks bersih)
2. page number -> repeated header/footer (perlu teks bersih agar akurat)
3. whitespace -> empty line (akhir, merapikan hasil)
"""

from __future__ import annotations

from typing import Optional

from siberrag_core.cleaners.base import CleaningRule
from siberrag_core.cleaners.rules import (
    BrokenOCRRule,
    EmptyLineRule,
    NormalizeUnicodeRule,
    PageNumberRule,
    RepeatedHeaderFooterRule,
    RepeatedHeadingRule,
    WhitespaceRule,
)
from siberrag_core.config import AppConfig, CleaningConfig
from siberrag_core.models.elements import Document
from siberrag_core.utils.logging import logger


def build_rules(cfg: CleaningConfig) -> list[CleaningRule]:
    """Bangun urutan rule aktif dari konfigurasi."""
    rules: list[CleaningRule] = []
    if cfg.fix_invalid_unicode:
        rules.append(NormalizeUnicodeRule())
    if cfg.fix_broken_ocr:
        rules.append(BrokenOCRRule())
    if cfg.remove_page_numbers:
        rules.append(PageNumberRule())
    if cfg.remove_repeated_headers:
        rules.append(RepeatedHeaderFooterRule(is_header=True))
    if cfg.remove_repeated_footers:
        rules.append(RepeatedHeaderFooterRule(is_header=False))
    # heading duplikat berulang lintas halaman (running header jurnal) - selalu
    # aktif karena heading asli harus unik per dokumen
    rules.append(RepeatedHeadingRule())
    if cfg.collapse_whitespace:
        rules.append(WhitespaceRule())
    if cfg.collapse_blank_lines:
        rules.append(EmptyLineRule())
    return rules


class Cleaner:
    """Menjalankan seluruh cleaning rule pada Document."""

    def __init__(self, config: Optional[CleaningConfig | AppConfig] = None) -> None:
        self.cfg: CleaningConfig = (
            config.cleaning if isinstance(config, AppConfig) else (config or CleaningConfig())
        )
        self.rules = build_rules(self.cfg)

    def clean(self, document: Document) -> Document:
        if not self.rules:
            return document
        logger.debug(f"Cleaning dokumen {document.filename} ({len(self.rules)} rule)...")
        for rule in self.rules:
            rule.apply(document.root)
        return document

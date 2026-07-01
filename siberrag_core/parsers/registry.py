"""Registry & dispatcher parser.

Strategi (default "auto"):
- Docling sebagai primary bila tersedia & mendukung ekstensi.
- Bila gagal/tidak tersedia, fallback ke parser native sesuai ekstensi.
- "docling": paksa pakai Docling (error bila tidak ada).
- "native": paksa pakai parser native.

Register semua parser terlepas dari ketersediaan library-nya; library yang
absen hanya akan memunculkan ParseError yang transparan saat dipakai, sehingga
registry tetap ringan & bisa diuji.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from siberrag_core.config import AppConfig, ParsingConfig
from siberrag_core.models.elements import Document
from siberrag_core.parsers.base import BaseParser, ParseError
from siberrag_core.parsers.docx_parser import DocxParser
from siberrag_core.parsers.docling_parser import DoclingParser, is_available as docling_available
from siberrag_core.parsers.html_parser import HtmlParser
from siberrag_core.parsers.markdown_parser import MarkdownParser
from siberrag_core.parsers.pdf_parser import PdfParser
from siberrag_core.parsers.txt_parser import TxtParser
from siberrag_core.parsers.csv_parser import CsvParser
from siberrag_core.parsers.xlsx_parser import XlsxParser
from siberrag_core.utils.logging import logger

#: pemetaan ekstensi -> parser native (fallback)
_NATIVE_BY_EXT: dict[str, type[BaseParser]] = {
    "pdf": PdfParser,
    "docx": DocxParser,
    "xlsx": XlsxParser,
    "xlsm": XlsxParser,
    "csv": CsvParser,
    "tsv": CsvParser,
    "html": HtmlParser,
    "htm": HtmlParser,
    "md": MarkdownParser,
    "markdown": MarkdownParser,
    "txt": TxtParser,
}

#: ekstensi yang tidak punya parser native (harus Docling)
_DOCLING_ONLY = {"pptx", "png", "jpg", "jpeg"}

#: format biner yang Docling kuasai (mode "auto" prefer Docling untuk ini).
# Catatan: PDF dipindah ke NATIVE by default karena Docling v2.x selalu load &
# menjalankan RapidOCR walau do_ocr=False, yang membuat parsing PDF sangat lambat.
# Parser native PyMuPDF lebih cepat & tidak pernah OCR. Bila butuh Docling utk
# PDF (mis. layout kompleks), set config: parsing.parser = "docling".
_DOCLING_PREFERRED = _DOCLING_ONLY

SUPPORTED_EXTENSIONS = set(_NATIVE_BY_EXT) | _DOCLING_ONLY


def supported_extensions() -> set[str]:
    return set(SUPPORTED_EXTENSIONS)


def is_supported(path: Path) -> bool:
    return path.suffix.lower().lstrip(".") in SUPPORTED_EXTENSIONS


class ParserRegistry:
    """Dispatcher parser dengan strategi auto/docling/native."""

    def __init__(self, config: Optional[ParsingConfig | AppConfig] = None) -> None:
        self._parsing_cfg: ParsingConfig = (
            config.parsing if isinstance(config, AppConfig) else
            (config or ParsingConfig())
        )
        self._docling: Optional[DoclingParser] = None
        # cache instance native
        self._native_cache: dict[type[BaseParser], BaseParser] = {}
        # progress reporter (di-set oleh pipeline, dipropagate ke parser)
        self._progress = None

    def set_progress(self, progress) -> None:
        """Set progress reporter untuk dipropagate ke parser (progress bar)."""
        self._progress = progress

    def _propagate_progress(self, parser: BaseParser) -> None:
        """Pass progress reporter ke instance parser."""
        parser._progress = self._progress

    # ----- public API -----
    def parse(self, path: Path, *, filename: Optional[str] = None) -> Document:
        ext = path.suffix.lower().lstrip(".")
        if ext not in SUPPORTED_EXTENSIONS:
            raise ParseError(f"Ekstensi tidak didukung: .{ext} ({path.name})")

        strategy = self._parsing_cfg.parser
        logger.debug(f"Parse {path.name} (ext=.{ext}, strategy={strategy})")

        if strategy == "docling":
            return self._docling_only(path, filename)

        if strategy == "native":
            return self._native_only(path, filename)

        # auto: docling dulu bila ada & mendukung, lalu fallback native.
        # PENTING: format text-native (md/html/txt) selalu pakai parser native
        # karena lebih akurat dalam mempertahankan struktur (heading/list/table)
        # dibanding Docling. Docling unggul untuk format biner (pdf/docx/pptx).
        if docling_available() and ext in _DOCLING_PREFERRED:
            try:
                doc_parser = self._get_docling()
                logger.debug(f"Menggunakan Docling untuk {path.name}")
                return doc_parser.parse(path, filename=filename)
            except ParseError as e:
                logger.warning(f"Docling gagal untuk {path.name} ({e}); fallback ke native.")

        return self._native_only(path, filename)

    # ----- internal -----
    def _native_only(self, path: Path, filename: Optional[str]) -> Document:
        ext = path.suffix.lower().lstrip(".")
        if ext in _DOCLING_ONLY:
            raise ParseError(f"Tidak ada parser native untuk .{ext}; install Docling.")
        parser_cls = _NATIVE_BY_EXT[ext]
        parser = self._native_cache.setdefault(parser_cls, parser_cls(self._parsing_cfg))
        self._propagate_progress(parser)
        return parser.parse(path, filename=filename)

    def _docling_only(self, path: Path, filename: Optional[str]) -> Document:
        return self._get_docling().parse(path, filename=filename)

    def _get_docling(self) -> DoclingParser:
        if self._docling is None:
            self._docling = DoclingParser(self._parsing_cfg)
        return self._docling


def build_registry(config: Optional[AppConfig] = None) -> ParserRegistry:
    """Factory registry dari AppConfig."""
    return ParserRegistry(config or AppConfig())

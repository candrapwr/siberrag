"""Re-export API parser."""

from siberrag_core.parsers.base import BaseParser, ParseError
from siberrag_core.parsers.detector import discover_documents, group_by_extension
from siberrag_core.parsers.registry import (
    ParserRegistry,
    build_registry,
    is_supported,
    supported_extensions,
)

__all__ = [
    "BaseParser",
    "ParseError",
    "ParserRegistry",
    "build_registry",
    "is_supported",
    "supported_extensions",
    "discover_documents",
    "group_by_extension",
]

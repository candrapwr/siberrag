"""Base class untuk cleaning rule.

Setiap rule adalah objek callable yang menerima DocumentElement tree dan
mengembalikan tree yang sudah dibersihkan. Rule wajib **mempertahankan struktur**
(heading/list/table/caption/pasal/ayat) dan hanya menghapus noise teks.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from siberrag_core.models.elements import DocumentElement


class CleaningRule(ABC):
    """Kontrak cleaning rule: ``clean(element) -> DocumentElement`` (in-place OK)."""

    name: str = "rule"

    @abstractmethod
    def apply(self, element: DocumentElement) -> DocumentElement:
        """Terapkan rule pada elemen (boleh mutasi)."""
        raise NotImplementedError

    def __call__(self, element: DocumentElement) -> DocumentElement:
        return self.apply(element)

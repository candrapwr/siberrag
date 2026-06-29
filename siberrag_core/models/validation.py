"""Model hasil validasi chunk."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Tingkat keparahan temuan validasi."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ValidationFinding(BaseModel):
    """Satu temuan (warning/recommendation/error) pada sebuah chunk."""

    code: str
    severity: Severity = Severity.WARNING
    message: str

    model_config = {"use_enum_values": True}


class ChunkValidation(BaseModel):
    """Hasil validasi untuk satu chunk."""

    chunk_id: str
    quality_score: int = 100  # 0-100, 100 = sempurna
    findings: list[ValidationFinding] = Field(default_factory=list)

    @property
    def warnings(self) -> list[ValidationFinding]:
        return [f for f in self.findings if f.severity in ("warning", "error")]

    @property
    def recommendations(self) -> list[ValidationFinding]:
        return [f for f in self.findings if f.severity == "info"]

    def add(self, code: str, message: str, severity: Severity = Severity.WARNING) -> None:
        self.findings.append(
            ValidationFinding(code=code, message=message, severity=severity)
        )

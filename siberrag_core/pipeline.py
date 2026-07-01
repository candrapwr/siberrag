"""Pipeline orchestrator - menjalankan seluruh 9 tahap otomatis.

Mengorkestrasi: Detection → Parsing → Cleaning → Hierarchy → Semantic →
Chunker → Metadata → Validator → Export.

Mendesain agar bisa dipanggil programatik MAUPUN dari CLI dengan progres.
``process_file`` menangani satu dokumen; ``process_documents`` menangani
banyak dokumen dan menggabungkan hasilnya.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Protocol

from siberrag_core.cleaners.cleaner import Cleaner
from siberrag_core.config import AppConfig, load_config
from siberrag_core.exporters.registry import get_exporter
from siberrag_core.hierarchy.builder import HierarchyBuilder
from siberrag_core.metadata.builder import MetadataBuilder
from siberrag_core.models.chunk import Chunk
from siberrag_core.models.validation import ChunkValidation
from siberrag_core.parsers.detector import discover_documents
from siberrag_core.parsers.registry import ParserRegistry
from siberrag_core.semantic.builder import SemanticBuilder
from siberrag_core.chunker.tokenizer import Chunker
from siberrag_core.utils.logging import logger
from siberrag_core.validator.validator import ChunkValidator


class ProgressReporter(Protocol):
    """Protokol callback progres (dipanggil pipeline setiap tahap/dokumen).

    Method:
    - stage(name): tandai awal tahap baru (mis. "Embedding...")
    - advance(n):  tandai n item selesai diproses
    - update(done, total, desc): update progres detail (done/total) untuk progress bar
    """

    def stage(self, name: str) -> None: ...

    def advance(self, n: int = 1) -> None: ...

    def update(self, done: int, total: int, desc: str = "") -> None: ...


class NullProgress:
    """No-op progress reporter."""

    def stage(self, name: str) -> None:
        pass

    def advance(self, n: int = 1) -> None:
        pass

    def update(self, done: int, total: int, desc: str = "") -> None:
        pass


@dataclass
class FileResult:
    """Hasil pemrosesan satu file."""

    path: Path
    chunks: list[Chunk] = field(default_factory=list)
    validations: list[ChunkValidation] = field(default_factory=list)
    error: Optional[str] = None
    output_path: Optional[Path] = None


@dataclass
class PipelineResult:
    """Hasil agregat seluruh pipeline."""

    files: list[FileResult] = field(default_factory=list)
    total_chunks: int = 0
    output_dir: Optional[Path] = None

    @property
    def succeeded(self) -> list[FileResult]:
        return [f for f in self.files if f.error is None]

    @property
    def failed(self) -> list[FileResult]:
        return [f for f in self.files if f.error is not None]

    @property
    def all_chunks(self) -> list[Chunk]:
        out: list[Chunk] = []
        for f in self.files:
            out.extend(f.chunks)
        return out


class Pipeline:
    """Orchestrator pipeline SiberRAG."""

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self.config: AppConfig = config or load_config()
        # bangun komponen sekali, reuse lintas dokumen
        self.registry = ParserRegistry(self.config)
        self.cleaner = Cleaner(self.config)
        self.hierarchy = HierarchyBuilder()
        self.semantic = SemanticBuilder()
        self.chunker = Chunker(self.config)
        self.metadata_builder = MetadataBuilder(
            self.config, encoding=self.config.chunking.encoding
        )
        self.validator = ChunkValidator(self.config)

    # ----- entry point utama -----
    def run(
        self,
        source: Path | str,
        *,
        output_dir: Optional[Path | str] = None,
        format: Optional[str] = None,
        progress: Optional[ProgressReporter] = None,
    ) -> PipelineResult:
        """Jalankan pipeline penuh untuk ``source`` (file atau direktori)."""
        progress = progress or NullProgress()

        # 1. Detection
        progress.stage("Scanning documents...")
        files = discover_documents(Path(source))
        if not files:
            logger.warning(f"Tidak ada dokumen yang didukung ditemukan di: {source}")
            return PipelineResult()

        result = PipelineResult()
        out_dir = Path(output_dir or self.config.export.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        result.output_dir = out_dir

        for path in files:
            fr = self.process_file(path, output_dir=out_dir, format=format,
                                   progress=progress)
            result.files.append(fr)
            result.total_chunks += len(fr.chunks)

        return result

    # ----- per file -----
    def process_file(
        self,
        path: Path,
        *,
        output_dir: Path,
        format: Optional[str] = None,
        progress: Optional[ProgressReporter] = None,
    ) -> FileResult:
        """Proses satu file melalui seluruh tahap pipeline."""
        progress = progress or NullProgress()
        fr = FileResult(path=path)

        try:
            # 2. Parsing
            progress.stage("Parsing documents...")
            # pass progress ke parser agar bisa menampilkan progress bar per halaman
            self.registry.set_progress(progress)
            document = self.registry.parse(path)
            self.registry.set_progress(None)

            # 3. Cleaning
            progress.stage("Cleaning...")
            document = self.cleaner.clean(document)
            progress.stage(f"Cleaning... ({len(document.elements())} elemen dibersihkan)")

            # 4. Hierarchy
            progress.stage("Building hierarchy...")
            document = self.hierarchy.build(document)

            # 5. Semantic blocks
            progress.stage("Creating semantic blocks...")
            blocks = self.semantic.build(document)
            progress.stage(f"Creating semantic blocks... ({len(blocks)} block)")

            # 6. Chunking
            progress.stage("Generating chunks...")
            chunks = self.chunker.chunk(
                blocks,
                document_id=document.document_id,
                filename=document.filename,
            )
            progress.stage(f"Generating chunks... ({len(chunks)} chunk)")

            # 7. Metadata
            progress.stage("Building metadata...")
            sample = " ".join(document.root.walk()[0].text()[:500] for _ in [0]) \
                if document.root.children else ""
            chunks = self.metadata_builder.enrich(chunks, sample_text=sample)

            # 8. Validation (dengan progress bar per chunk)
            progress.stage("Validating chunks...")
            validations = self.validator.validate_all(chunks, progress=progress)

            # 9. Export
            progress.stage(f"Exporting... ({len(chunks)} chunk)")
            out_path = self._export(chunks, validations, output_dir,
                                    stem=path.stem, format=format)

            fr.chunks = chunks
            fr.validations = validations
            fr.output_path = out_path
            logger.info(f"✓ {path.name}: {len(chunks)} chunk -> {out_path.name}")
        except Exception as exc:
            fr.error = f"{type(exc).__name__}: {exc}"
            logger.error(f"✗ {path.name}: {fr.error}")

        progress.advance(1)
        return fr

    # ----- export -----
    def _export(
        self,
        chunks: list[Chunk],
        validations: list[ChunkValidation],
        output_dir: Path,
        *,
        stem: str,
        format: Optional[str] = None,
    ) -> Path:
        fmt = (format or self.config.export.format).lower()
        # override config sementara untuk format custom
        export_cfg = self.config.export.model_copy(update={"format": fmt})
        exporter = get_exporter(export_cfg, format=fmt)
        ext = fmt if fmt != "markdown" else "md"
        out_path = output_dir / f"{stem}.{ext}"
        return exporter.export(chunks, validations, out_path)

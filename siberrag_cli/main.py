"""Entry point CLI SiberRAG - single command pipeline.

Penggunaan:
    siberrag process <path>
    siberrag process ./documents --output ./output --format jsonl
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

# Muat .env SEBELUM config/provider diinisialisasi.
from siberrag_core.utils.env import load_env
load_env()

import typer
from rich.console import Console

from siberrag_cli.display import (  # type: ignore[attr-defined]
    STAGES,
    banner,
    console,
    make_progress,
    print_summary,
)
from siberrag_core.config import load_config
from siberrag_core.pipeline import Pipeline, ProgressReporter

app = typer.Typer(
    name="siberrag",
    help="SiberRAG - Document Preprocessing Engine untuk RAG.",
    no_args_is_help=True,
    add_completion=False,
)


class RichProgressReporter(ProgressReporter):
    """Adapter ProgressReporter -> Rich progress bar (mode simple per-stage)."""

    def __init__(self) -> None:
        self._stage_index = 0

    def stage(self, name: str) -> None:
        console.print(f"[cyan]▶[/cyan] {name}")

    def advance(self, n: int = 1) -> None:
        pass  # per-file advance tidak ditampilkan detail (lihat loop di command)


@app.command()
def process(
    path: Path = typer.Argument(..., help="File atau direktori dokumen."),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Direktori output (override config)."
    ),
    format: Optional[str] = typer.Option(
        None, "--format", "-f",
        help="Format export: json | jsonl | markdown (override config).",
    ),
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path file config.yaml (default: config/config.yaml)."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Logging DEBUG."),
) -> None:
    """Proses dokumen menjadi chunk berkualitas tinggi."""
    from siberrag_core.utils.logging import setup_logging
    setup_logging(level="DEBUG" if verbose else "INFO", force=True)

    banner()

    cfg = load_config(config)
    pipeline = Pipeline(cfg)
    reporter = RichProgressReporter()

    console.print(f"[dim]Input :[/dim] {path}")
    if output:
        console.print(f"[dim]Output:[/dim] {output}")
    if format:
        console.print(f"[dim]Format:[/dim] {format}")
    console.print()

    result = pipeline.run(
        path,
        output_dir=output,
        format=format,
        progress=reporter,
    )

    print_summary(result)

    if result.failed:
        raise typer.Exit(code=1)


@app.command()
def info(
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path file config.yaml."
    ),
) -> None:
    """Tampilkan konfigurasi aktif & format yang didukung."""
    from siberrag_core.parsers.registry import supported_extensions
    cfg = load_config(config)
    banner()
    console.print("[bold]Supported formats:[/bold] "
                  + ", ".join(sorted(supported_extensions())))
    console.print()
    console.print("[bold]Active config:[/bold]")
    console.print_json(data=cfg.to_dict(), default=str)


# ============================================================
# v2 - RAG commands: index, query, serve
# ============================================================


@app.command()
def index(
    path: Path = typer.Argument(..., help="Dokumen/direktori atau file .jsonl untuk di-index."),
    collection: Optional[str] = typer.Option(None, "--collection", help="Override collection."),
    min_quality: int = typer.Option(0, "--min-quality", help="Lewati chunk di bawah quality score."),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path config.yaml."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Logging DEBUG."),
) -> None:
    """Index dokumen ke vector database (embed + store)."""
    from siberrag_core.utils.logging import setup_logging
    setup_logging(level="DEBUG" if verbose else "INFO", force=True)

    from siberrag_core.index_pipeline import IndexPipeline

    banner()
    cfg = load_config(config)
    if collection:
        cfg.vector_db.collection = collection
    console.print(f"[dim]Index source:[/dim] {path}")
    console.print(f"[dim]Collection  :[/dim] {cfg.vector_db.collection}")
    console.print(f"[dim]Embedding  :[/dim] {cfg.embedding.provider} ({cfg.embedding.model})")
    console.print()

    pipeline = IndexPipeline(cfg)
    result = pipeline.index(path, min_quality_score=min_quality)

    # ringkasan
    succeeded = result.succeeded
    failed = result.failed
    console.print()
    console.print(f"[green]✓ Indexed:[/green] {result.total_indexed} chunk "
                  f"dari {len(succeeded)} source.")
    if failed:
        console.print(f"[red]✗ Failed:[/red] {len(failed)} source:")
        for r in failed:
            console.print(f"  • {r.source}: {r.error}")
        raise typer.Exit(code=1)


@app.command()
def query(
    question: str = typer.Argument(..., help="Pertanyaan."),
    top_k: Optional[int] = typer.Option(None, "--top-k", help="Jumlah chunk di-retrieve."),
    document: Optional[str] = typer.Option(None, "--document", help="Filter document_id."),
    retrieve_only: bool = typer.Option(False, "--retrieve-only", help="Tanpa LLM, hanya retrieve."),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path config.yaml."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Logging DEBUG."),
) -> None:
    """Tanya jawab dokumen yang sudah di-index (RAG)."""
    from siberrag_core.utils.logging import setup_logging
    setup_logging(level="DEBUG" if verbose else "INFO", force=True)

    from siberrag_core.query_pipeline import QueryPipeline

    banner()
    cfg = load_config(config)
    console.print(f"[dim]Question :[/dim] {question}")
    console.print()

    pipeline = QueryPipeline(cfg)

    if retrieve_only:
        results = pipeline.retrieve_only(question, top_k=top_k, document_id=document)
        console.print(f"[bold]Retrieved {len(results)} chunk:[/bold]\n")
        for i, hit in enumerate(results.hits, 1):
            m = hit.chunk.metadata
            console.print(f"[cyan]{i}.[/cyan] score={hit.score:.3f} | "
                          f"{m.chapter} > {m.section} | hal.{m.page_start}")
            console.print(f"   [dim]{hit.chunk.text[:150]}...[/dim]\n")
        return

    answer = pipeline.query(question, top_k=top_k, document_id=document)
    console.print(f"[bold green]Jawaban:[/bold green]\n")
    console.print(answer.text)
    console.print()
    if answer.sources.hits:
        console.print(f"[bold]Sumber ({len(answer.sources.hits)}):[/bold]")
        for i, hit in enumerate(answer.sources.hits, 1):
            m = hit.chunk.metadata
            console.print(f"  [cyan]{i}.[/cyan] {m.chapter} > {m.section} | "
                          f"hal.{m.page_start} | skor={hit.score:.3f} | {m.filename}")
    if answer.is_error:
        raise typer.Exit(code=1)


@app.command()
def stats(
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path config.yaml."),
) -> None:
    """Tampilkan statistik vector database."""
    banner()
    cfg = load_config(config)
    from siberrag_core.vectorstore.registry import get_vectorstore
    store = get_vectorstore(cfg)
    console.print(f"[bold]Vector DB stats:[/bold]")
    console.print(f"  Collection : {cfg.vector_db.collection}")
    console.print(f"  Total chunk: {store.count()}")
    console.print(f"  Collections: {', '.join(store.list_collections())}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Host bind."),
    port: int = typer.Option(8000, "--port", help="Port."),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path config.yaml."),
) -> None:
    """Jalankan REST API + Web UI server."""
    banner()
    console.print(f"[bold]Starting SiberRAG server...[/bold]")
    console.print(f"[dim]Host:[/dim] {host}:{port}")
    cfg = load_config(config)

    import os
    os.environ["SIBERRAG_CONFIG"] = str(config) if config else ""
    # delegate ke siberrag_api
    import uvicorn
    uvicorn.run("siberrag_api.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":  # pragma: no cover
    app()

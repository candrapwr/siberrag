"""Entry point CLI SiberRAG - single command pipeline.

Penggunaan:
    siberrag process <path>
    siberrag process ./documents --output ./output --format jsonl
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

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


if __name__ == "__main__":  # pragma: no cover
    app()

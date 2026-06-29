"""Display helper - output Rich (progress bar, ringkasan, banner)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from siberrag_core.pipeline import FileResult, PipelineResult

console = Console()

STAGES = [
    "Scanning documents...",
    "Parsing documents...",
    "Cleaning...",
    "Building hierarchy...",
    "Creating semantic blocks...",
    "Generating chunks...",
    "Building metadata...",
    "Validating chunks...",
    "Exporting...",
]


def banner() -> None:
    console.print(Panel.fit("[bold cyan]🚀 SiberRAG[/bold cyan] "
                            "[dim]Document Preprocessing Engine[/dim]",
                            border_style="cyan"))


def print_summary(result: PipelineResult) -> None:
    """Cetak ringkasan akhir proses."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("Documents", str(len(result.files)))
    table.add_row("  ✓ succeeded", str(len(result.succeeded)))
    if result.failed:
        table.add_row("  ✗ failed", str(len(result.failed)))
    table.add_row("Chunks", str(result.total_chunks))
    table.add_row("Output", str(result.output_dir or "-"))
    console.print()
    console.print(table)

    # detail kegagalan
    if result.failed:
        console.print("\n[red]Failed documents:[/red]")
        for fr in result.failed:
            console.print(f"  • {fr.path.name}: {fr.error}")


def make_progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    )

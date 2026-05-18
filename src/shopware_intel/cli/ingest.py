from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from shopware_intel.config import get_settings
from shopware_intel.ingest.clone import ensure_mirror, list_tags
from shopware_intel.ingest.orchestrator import run_glob, run_one
from shopware_intel.state import StateStore

app = typer.Typer(help="Ingest Shopware tags into the Qdrant index.")
console = Console()


@app.command()
def run(
    tag: str | None = typer.Option(None, help="Single tag, e.g. v6.7.0.0"),
    tag_glob: str = typer.Option("v6.7.*", help="Tag glob, e.g. 'v6.7.*'"),
    skip_prerelease: bool = typer.Option(True),
) -> None:
    settings = get_settings()
    if tag:
        count = run_one(tag, settings)
        console.print(f"[green]Ingested {tag}: {count} chunks")
        return
    results = run_glob(tag_glob, settings, skip_prerelease=skip_prerelease)
    total = sum(results.values())
    console.print(f"[bold green]Done.[/] {len(results)} tags, {total} chunks total.")


@app.command()
def status() -> None:
    settings = get_settings()
    state = StateStore(settings.state_db)
    rows = state.tag_summary()
    if not rows:
        console.print("[yellow]No tags ingested yet.[/]")
        return
    t = Table(title="Ingested tags")
    t.add_column("Tag")
    t.add_column("Chunks", justify="right")
    t.add_column("Finished at")
    for tag, n, when in rows:
        t.add_row(tag, str(n), when)
    console.print(t)


@app.command("list-tags")
def list_available_tags(glob: str = "v6.[4567].*", skip_prerelease: bool = True) -> None:
    settings = get_settings()
    ensure_mirror(settings.mirror_path)
    tags = list_tags(settings.mirror_path, glob=glob, skip_prerelease=skip_prerelease)
    console.print(f"[bold]{len(tags)} tags match '{glob}':")
    for t in tags:
        console.print(f"  {t}")


@app.command()
def finalize() -> None:
    console.print("[yellow]finalize: not yet implemented (Phase 5)[/]")


if __name__ == "__main__":
    app()

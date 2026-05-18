from __future__ import annotations

import asyncio
import json

import typer
from rich.console import Console

from shopware_intel.config import Settings, get_settings
from shopware_intel.retrieval.search import Searcher

console = Console()


def main(
    query: str = typer.Argument(..., help="Query text"),
    area: str = typer.Option("core", help="core|storefront|administration|checkout|flow"),
    version: str | None = typer.Option(None, help="e.g. '6.7.0.0'"),
    limit: int = typer.Option(8),
) -> None:
    settings = get_settings()
    asyncio.run(_run(settings, query, area, version, limit))


async def _run(settings: Settings, query: str, area: str, version: str | None, limit: int) -> None:
    searcher = Searcher(settings)
    try:
        hits = await searcher.search_collection(area, query, version=version, limit=limit)
    finally:
        await searcher.close()
    if not hits:
        console.print(f"[yellow]No matches for {query!r}[/]")
        return
    console.print(
        json.dumps(
            {"query": query, "area": area, "version": version, "hits": [h.to_dict() for h in hits]},
            indent=2,
            ensure_ascii=False,
        )
    )


def app() -> None:
    typer.run(main)


if __name__ == "__main__":
    app()

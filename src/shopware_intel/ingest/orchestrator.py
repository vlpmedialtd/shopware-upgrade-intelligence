from __future__ import annotations

import asyncio
import logging
import tempfile
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from shopware_intel.areas import Area
from shopware_intel.config import Settings
from shopware_intel.ingest.chunk.base import Chunk
from shopware_intel.ingest.chunk.changelog import chunk_changelog
from shopware_intel.ingest.chunk.markdown import chunk_upgrade_md
from shopware_intel.ingest.chunk.php import chunk_php
from shopware_intel.ingest.chunk.scss import chunk_scss
from shopware_intel.ingest.chunk.ts_js import chunk_ts_js
from shopware_intel.ingest.chunk.twig import chunk_twig
from shopware_intel.ingest.chunk.vue import chunk_vue
from shopware_intel.ingest.chunk.xml import chunk_xml
from shopware_intel.ingest.clone import (
    ensure_mirror,
    export_tag,
    list_tags,
    supplement_export_ignored,
    tag_sha,
)
from shopware_intel.ingest.embed import OllamaEmbedder
from shopware_intel.ingest.extract import SourceFile, walk_tag
from shopware_intel.ingest.load import (
    CODE_COLLECTIONS,
    ensure_collections,
    open_client,
    upsert_chunks,
)
from shopware_intel.state import StateStore

log = logging.getLogger(__name__)
console = Console()


def chunk_file(sf: SourceFile) -> list[Chunk]:
    try:
        content = sf.abs_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    area = sf.area.value
    path = sf.rel_path
    if sf.language == "php":
        return chunk_php(content, file_path=path, area=area)
    if sf.language == "twig":
        return chunk_twig(content, file_path=path, area=area)
    if sf.language == "scss" or sf.language == "css":
        return chunk_scss(content, file_path=path, area=area)
    if sf.language == "vue":
        return chunk_vue(content, file_path=path, area=area)
    if sf.language in ("ts", "js"):
        return chunk_ts_js(content, file_path=path, area=area, language=sf.language)
    if sf.language == "xml":
        return chunk_xml(content, file_path=path, area=area)
    if sf.language == "markdown":
        if path.startswith("changelog/"):
            return chunk_changelog(content, file_path=path, area=area)
        if path.startswith("UPGRADE-"):
            return chunk_upgrade_md(content, file_path=path, area=area)
    return []


async def _process_tag(tag: str, settings: Settings, state: StateStore) -> int:
    if state.is_done(tag):
        console.print(f"[dim]skip[/] {tag}")
        return 0

    sha = tag_sha(settings.mirror_path, tag)
    with tempfile.TemporaryDirectory(prefix=f"sw-intel-{tag}-") as tmp:
        tmp_path = Path(tmp)
        console.print(f"[cyan]extract[/] {tag} → {tmp_path}")
        export_tag(settings.mirror_path, tag, tmp_path)
        supplement_count = supplement_export_ignored(settings.mirror_path, tag, tmp_path)
        console.print(f"  [dim]supplemented {supplement_count} export-ignored files[/]")

        files = [sf for sf in walk_tag(tmp_path) if sf.area is not Area.OTHER]
        console.print(f"  [dim]{len(files)} files after filter[/]")

        by_area: dict[str, list[Chunk]] = defaultdict(list)
        for sf in files:
            for chunk in chunk_file(sf):
                by_area[chunk.area].append(chunk)

        total_chunks = sum(len(v) for v in by_area.values())
        console.print(f"  [dim]{total_chunks} chunks across {len(by_area)} areas[/]")

        if total_chunks == 0:
            state.mark_done(tag, sha, 0)
            return 0

        embedder = OllamaEmbedder(
            settings.ollama_host,
            settings.embed_model,
            settings.embed_dim,
            settings.embed_batch_size,
        )
        client = open_client(settings.qdrant_path)
        ensure_collections(client, settings.embed_dim)
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("{task.description}"),
                BarColumn(),
                TextColumn("{task.completed}/{task.total}"),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                for area_name, chunks in by_area.items():
                    collection = "changes" if area_name == Area.CHANGES.value else area_name
                    if collection not in CODE_COLLECTIONS and collection != "changes":
                        continue
                    task_id = progress.add_task(f"embed[{collection}]", total=len(chunks))
                    texts = [c.content for c in chunks]
                    vectors = await embedder.embed(texts, kind="document")
                    progress.update(task_id, advance=len(chunks))
                    point_ids = upsert_chunks(client, collection, tag, chunks, vectors)
                    for pid, chunk in zip(point_ids, chunks, strict=True):
                        state.record_point(pid, tag, chunk.file_path, chunk.content_sha)
            client.close()
        finally:
            await embedder.close()

    state.mark_done(tag, sha, total_chunks)
    console.print(f"[green]done[/] {tag} ({total_chunks} chunks)")
    return total_chunks


async def run_tags(settings: Settings, tags: Iterable[str]) -> dict[str, int]:
    state = StateStore(settings.state_db)
    counts: dict[str, int] = {}
    for tag in tags:
        counts[tag] = await _process_tag(tag, settings, state)
    return counts


def run_one(tag: str, settings: Settings) -> int:
    state = StateStore(settings.state_db)
    ensure_mirror(settings.mirror_path)
    return asyncio.run(_process_tag(tag, settings, state))


def run_glob(glob: str, settings: Settings, skip_prerelease: bool = True) -> dict[str, int]:
    ensure_mirror(settings.mirror_path)
    tags = list_tags(settings.mirror_path, glob=glob, skip_prerelease=skip_prerelease)
    return asyncio.run(run_tags(settings, tags))

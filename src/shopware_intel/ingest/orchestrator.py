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
from shopware_intel.ingest.chunk.base import Chunk, embedding_text
from shopware_intel.ingest.chunk.changelog import chunk_changelog
from shopware_intel.ingest.chunk.markdown import chunk_upgrade_md
from shopware_intel.ingest.chunk.php_ts import chunk_php_ts as chunk_php
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
        client = open_client(settings.qdrant_path, url=settings.qdrant_url)
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

                    # Cross-tag content dedup: lookup existing vectors by content_sha.
                    # Most files barely change across patch releases, so this typically
                    # saves 70-85% of embed work on a multi-tag ingest run.
                    shas = [c.content_sha for c in chunks]
                    cached = state.get_cached_vectors(shas)
                    to_embed_idx = [i for i, c in enumerate(chunks) if c.content_sha not in cached]
                    progress.update(
                        progress.add_task(
                            f"cache-hit[{collection}]",
                            total=len(chunks),
                            completed=len(chunks) - len(to_embed_idx),
                        )
                    )

                    if to_embed_idx:
                        task_id = progress.add_task(f"embed[{collection}]", total=len(to_embed_idx))
                        texts = [embedding_text(chunks[i]) for i in to_embed_idx]
                        new_vectors = await embedder.embed(texts, kind="document")
                        progress.update(task_id, advance=len(to_embed_idx))
                        # Persist for future tags
                        state.cache_vectors(
                            [
                                (chunks[i].content_sha, list(v))
                                for i, v in zip(to_embed_idx, new_vectors, strict=True)
                            ]
                        )
                        for i, v in zip(to_embed_idx, new_vectors, strict=True):
                            cached[chunks[i].content_sha] = list(v)

                    vectors = [cached[c.content_sha] for c in chunks]
                    point_ids = upsert_chunks(client, collection, tag, chunks, vectors)
                    state.record_points(
                        [
                            (pid, tag, c.file_path, c.content_sha)
                            for pid, c in zip(point_ids, chunks, strict=True)
                        ]
                    )
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

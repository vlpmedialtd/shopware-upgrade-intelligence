"""Parallel multi-tag ingest.

Spawns N independent sw-intel-ingest worker subprocesses, each handling one tag
end-to-end (archive -> chunk -> embed -> upsert -> mark done). Each worker has its
own mirror tmpdir + own Ollama HTTP client + own Qdrant connection; coordination
is only through state.sqlite (already-done tags are skipped) and shared Ollama
daemon (with OLLAMA_NUM_PARALLEL >= N for concurrent embed requests).

The simpler alternative — a single Python process with multiprocessing.Pool —
would require pickling chunk batches across worker boundaries, which is wasteful
for a CPU- and I/O-bound workload that already has per-tag isolation.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import time
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table

from shopware_intel.config import get_settings
from shopware_intel.ingest.clone import ensure_mirror, list_tags
from shopware_intel.state import StateStore

console = Console()


def main(
    tag_glob: str = typer.Option("v6.[4567].*", help="Tag glob; default = all stable 6.4-6.7"),
    workers: int = typer.Option(4, "--workers", "-w", min=1, max=10),
    skip_prerelease: bool = typer.Option(True),
    dry_run: bool = typer.Option(False, help="List the tag plan without running"),
) -> None:
    settings = get_settings()
    ensure_mirror(settings.mirror_path)
    all_tags = list_tags(settings.mirror_path, glob=tag_glob, skip_prerelease=skip_prerelease)
    state = StateStore(settings.state_db)
    done = {t for t, _, _ in state.tag_summary()}
    pending = [t for t in all_tags if t not in done]

    console.print(
        f"[bold]{len(all_tags)}[/] tags match {tag_glob!r}; "
        f"[green]{len(done)}[/] already ingested, [yellow]{len(pending)}[/] pending."
    )

    if dry_run or not pending:
        return

    if workers > 4 and "OLLAMA_NUM_PARALLEL" not in os.environ:
        console.print(
            f"[yellow]Hint: set OLLAMA_NUM_PARALLEL={workers} on the Ollama server "
            "to actually parallelize embed requests."
        )

    started_at = time.time()
    cmd_template = [
        sys.executable,
        "-m",
        "shopware_intel.cli.ingest",
        "run",
        "--tag",
        "{tag}",
    ]
    running: dict[str, subprocess.Popen[bytes]] = {}
    queue = list(pending)
    results: list[tuple[str, int, float]] = []

    def _spawn(tag: str) -> None:
        cmd = [c.format(tag=tag) for c in cmd_template]
        log_dir = settings.state_db.parent / "ingest-logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log = log_dir / f"{tag}.log"
        f = log.open("wb")
        proc = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT)
        running[tag] = proc
        console.print(f"[cyan]START[/] {tag} (pid {proc.pid}, log {log})")

    while queue or running:
        while queue and len(running) < workers:
            _spawn(queue.pop(0))

        for tag in list(running):
            rc = running[tag].poll()
            if rc is None:
                continue
            elapsed = time.time() - started_at
            results.append((tag, rc, elapsed))
            status = "[green]OK[/]" if rc == 0 else f"[red]EXIT {rc}[/]"
            console.print(
                f"  {status} {tag}  ({elapsed / 60:.1f} min wall since start; "
                f"{len(results)}/{len(pending)} done; {len(queue)} queued)"
            )
            del running[tag]

        if running:
            time.sleep(2)

    table = Table(title="Parallel ingest summary")
    table.add_column("Tag")
    table.add_column("Status")
    for tag, rc, _ in results:
        table.add_row(tag, "OK" if rc == 0 else f"EXIT {rc}")
    console.print(table)

    finished_at = datetime.now().isoformat()
    total_minutes = (time.time() - started_at) / 60
    console.print(
        f"[bold green]Done.[/] {len(results)} tags in {total_minutes:.1f} min "
        f"({total_minutes / max(1, len(results)):.1f} min/tag on average). Finished {finished_at}."
    )


def app() -> None:
    typer.run(main)


if __name__ == "__main__":
    app()


# Hint for shell quoting when calling under nohup / launchd
_EXAMPLE = (
    f"OLLAMA_NUM_PARALLEL=4 nohup uv run sw-intel-parallel-ingest "
    f"--workers 4 --tag-glob {shlex.quote('v6.[4567].*')} > parallel.log 2>&1 &"
)

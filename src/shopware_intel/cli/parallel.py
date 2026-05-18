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
from pathlib import Path

import httpx
import typer
from rich.console import Console
from rich.table import Table

from shopware_intel.config import get_settings
from shopware_intel.ingest.clone import ensure_mirror, list_tags
from shopware_intel.ingest.load import ensure_collections, open_client
from shopware_intel.state import StateStore

console = Console()


def _start_ollama_instances(n: int, base_port: int = 11434) -> list[subprocess.Popen[bytes]]:
    """Start N independent ollama serve instances on consecutive ports.

    Ollama serializes embed requests through its single loaded model regardless of
    OLLAMA_NUM_PARALLEL: that flag controls the request queue, not parallel forward
    passes. Real N-fold throughput requires N independent instances, each holding
    its own copy of the model (1.1 GB nomic-embed-text x N).
    """
    procs: list[subprocess.Popen[bytes]] = []
    for i in range(n):
        port = base_port + i
        if _ollama_ready(f"http://localhost:{port}"):
            console.print(f"[dim]ollama:{port} already up[/]")
            continue
        env = {
            **os.environ,
            "OLLAMA_HOST": f"127.0.0.1:{port}",
            "OLLAMA_MODELS": str(Path.home() / ".ollama" / "models"),
            "OLLAMA_KEEP_ALIVE": "24h",
            "OLLAMA_FLASH_ATTENTION": "1",
        }
        log_path = Path("/tmp") / f"ollama-{port}.log"
        proc = subprocess.Popen(
            ["ollama", "serve"],
            env=env,
            stdout=log_path.open("wb"),
            stderr=subprocess.STDOUT,
        )
        procs.append(proc)
        console.print(f"[cyan]ollama:{port} starting (pid {proc.pid}, log {log_path})[/]")
    # Wait for all to be reachable
    for i in range(n):
        port = base_port + i
        deadline = time.time() + 30
        while time.time() < deadline:
            if _ollama_ready(f"http://localhost:{port}"):
                console.print(f"[green]ollama:{port} up[/]")
                break
            time.sleep(1)
        else:
            console.print(f"[red]ollama:{port} did not come up in 30s[/]")
    return procs


def _ollama_ready(host: str) -> bool:
    try:
        return httpx.get(f"{host}/api/tags", timeout=2.0).status_code == 200
    except Exception:
        return False


def main(
    tag_glob: str = typer.Option("v6.[4567].*", help="Tag glob; default = all stable 6.4-6.7"),
    workers: int = typer.Option(4, "--workers", "-w", min=1, max=10),
    skip_prerelease: bool = typer.Option(True),
    dry_run: bool = typer.Option(False, help="List the tag plan without running"),
    multi_ollama: bool = typer.Option(
        True,
        "--multi-ollama/--single-ollama",
        help=(
            "Start one ollama serve instance per worker on consecutive ports "
            "(default). Real N-fold embed throughput; costs ~1.1 GB RAM per extra "
            "instance. --single-ollama queues all workers through localhost:11434."
        ),
    ),
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

    # Pre-create Qdrant collections once so the workers don't race on creation.
    qdrant = open_client(settings.qdrant_path, url=settings.qdrant_url)
    ensure_collections(qdrant, settings.embed_dim)
    qdrant.close()
    console.print("[dim]qdrant collections ready[/]")

    if multi_ollama and workers > 1:
        _start_ollama_instances(workers)

    started_at = time.time()
    running: dict[str, subprocess.Popen[bytes]] = {}
    queue = list(pending)
    results: list[tuple[str, int, float]] = []

    def _spawn(tag: str, worker_index: int) -> None:
        cmd = [
            sys.executable,
            "-m",
            "shopware_intel.cli.ingest",
            "run",
            "--tag",
            tag,
        ]
        log_dir = settings.state_db.parent / "ingest-logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log = log_dir / f"{tag}.log"
        env = {**os.environ}
        if multi_ollama:
            env["SW_INTEL_OLLAMA_HOST"] = f"http://localhost:{11434 + worker_index}"
        f = log.open("wb")
        proc = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, env=env)
        running[tag] = proc
        host_label = env.get("SW_INTEL_OLLAMA_HOST", settings.ollama_host)
        console.print(f"[cyan]START[/] {tag} (pid {proc.pid}, ollama {host_label}, log {log})")

    # worker_index → tag mapping so each slot consistently hits the same ollama port
    slots: dict[int, str | None] = {i: None for i in range(workers)}

    def _free_slot() -> int | None:
        for i, t in slots.items():
            if t is None:
                return i
        return None

    while queue or running:
        while queue and (idx := _free_slot()) is not None:
            tag = queue.pop(0)
            slots[idx] = tag
            _spawn(tag, idx)

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
            for i, t in slots.items():
                if t == tag:
                    slots[i] = None
                    break

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

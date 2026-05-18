from __future__ import annotations

import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from shopware_intel.config import get_settings
from shopware_intel.ingest.embed import ping_sync

app = typer.Typer(help="Health-check the local stack.")
console = Console()


@app.callback(invoke_without_command=True)
def main() -> None:
    s = get_settings()
    t = Table(title="shopware-intel doctor")
    t.add_column("Check")
    t.add_column("Status")
    t.add_column("Detail")

    ok = True

    git = shutil.which("git")
    t.add_row("git", "OK" if git else "MISSING", git or "")
    ok &= bool(git)

    mirror_ok = (s.mirror_path / "HEAD").exists()
    t.add_row(
        "git mirror",
        "OK" if mirror_ok else "MISSING",
        str(s.mirror_path) + (" (run `just mirror`)" if not mirror_ok else ""),
    )
    ok &= mirror_ok

    ollama_ok = ping_sync(s.ollama_host)
    t.add_row(
        "ollama",
        "OK" if ollama_ok else "DOWN",
        s.ollama_host if ollama_ok else f"{s.ollama_host} (run `brew services start ollama`)",
    )
    ok &= ollama_ok

    qdrant_writable = _writable(s.qdrant_path)
    t.add_row("qdrant path", "OK" if qdrant_writable else "FAIL", str(s.qdrant_path))
    ok &= qdrant_writable

    state_writable = _writable(s.state_db.parent)
    t.add_row("state.db dir", "OK" if state_writable else "FAIL", str(s.state_db.parent))
    ok &= state_writable

    disk_free_gb = _disk_free_gb(s.qdrant_path)
    enough = disk_free_gb >= 30
    t.add_row("disk free", "OK" if enough else "WARN", f"{disk_free_gb:.1f} GB (need ≥30 GB)")

    console.print(t)
    raise SystemExit(0 if ok else 1)


def _writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".sw-intel-probe"
        probe.write_text("ok")
        probe.unlink()
        return True
    except Exception:
        return False


def _disk_free_gb(path: Path) -> float:
    while not path.exists():
        path = path.parent
    usage = shutil.disk_usage(path)
    return usage.free / (1024**3)


if __name__ == "__main__":
    app()

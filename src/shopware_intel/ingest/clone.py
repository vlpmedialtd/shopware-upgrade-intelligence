from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

SHOPWARE_REPO = "https://github.com/shopware/shopware.git"

STABLE_TAG_RE = re.compile(r"^v6\.[4567]\.\d+\.\d+$")


def ensure_mirror(mirror_path: Path, repo_url: str = SHOPWARE_REPO) -> None:
    if mirror_path.exists():
        subprocess.run(
            ["git", "remote", "update"],
            cwd=mirror_path,
            check=True,
            capture_output=True,
        )
        return
    mirror_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--mirror", repo_url, str(mirror_path)],
        check=True,
    )


def list_tags(
    mirror_path: Path, glob: str = "v6.[4567].*", skip_prerelease: bool = True
) -> list[str]:
    out = subprocess.run(
        ["git", "tag", "-l", glob],
        cwd=mirror_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    tags = [t.strip() for t in out.splitlines() if t.strip()]
    if skip_prerelease:
        tags = [t for t in tags if STABLE_TAG_RE.match(t)]
    return sorted(tags, key=_tag_sort_key)


def _tag_sort_key(tag: str) -> tuple[int, ...]:
    m = re.match(r"^v(\d+)\.(\d+)\.(\d+)\.(\d+)$", tag)
    if not m:
        return (0, 0, 0, 0)
    return tuple(int(x) for x in m.groups())


def tag_sha(mirror_path: Path, tag: str) -> str:
    out = subprocess.run(
        ["git", "rev-parse", tag],
        cwd=mirror_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return out.strip()


def export_tag(mirror_path: Path, tag: str, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    archive = subprocess.Popen(
        ["git", "archive", "--format=tar", tag],
        cwd=mirror_path,
        stdout=subprocess.PIPE,
    )
    try:
        subprocess.run(
            ["tar", "-x", "-C", str(dest)],
            stdin=archive.stdout,
            check=True,
        )
    finally:
        if archive.stdout is not None:
            archive.stdout.close()
        archive.wait()
    if archive.returncode != 0:
        raise RuntimeError(f"git archive failed for {tag}: exit {archive.returncode}")


def show_file(mirror_path: Path, tag: str, path: str) -> bytes | None:
    proc = subprocess.run(
        ["git", "show", f"{tag}:{path}"],
        cwd=mirror_path,
        capture_output=True,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def list_tree_files(mirror_path: Path, tag: str, *, prefix: str = "") -> list[str]:
    """List all files in a tag's tree (ignores .gitattributes export-ignore)."""
    cmd = ["git", "ls-tree", "-r", "--name-only", tag]
    if prefix:
        cmd.append(prefix)
    out = subprocess.run(cmd, cwd=mirror_path, check=True, capture_output=True, text=True).stdout
    return [line.strip() for line in out.splitlines() if line.strip()]


def supplement_export_ignored(mirror_path: Path, tag: str, dest: Path) -> int:
    """Materialize changelog/ and UPGRADE-*.md files that git archive strips.

    Shopware's .gitattributes marks `/changelog` and `/*.md` as export-ignore, so
    `git archive` omits them. We fetch them via `git show` since they are the primary
    source of structured upgrade information.
    """
    count = 0
    for path in list_tree_files(mirror_path, tag, prefix="changelog/"):
        data = show_file(mirror_path, tag, path)
        if data is None:
            continue
        target = dest / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        count += 1
    for path in list_tree_files(mirror_path, tag):
        if not path.startswith("UPGRADE-") or not path.endswith(".md"):
            continue
        data = show_file(mirror_path, tag, path)
        if data is None:
            continue
        (dest / path).write_bytes(data)
        count += 1
    return count

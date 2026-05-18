from __future__ import annotations

import re

import yaml

from shopware_intel.ingest.chunk.base import Chunk

FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
RELEASE_DIR_RE = re.compile(r"changelog/release-(\d+)-(\d+)-(\d+)-(\d+)/")
SECTION_HEADER_RE = re.compile(r"^# ([A-Za-z][\w\s-]*)$", re.MULTILINE)

MAX_BODY = 2000


def chunk_changelog(content: str, *, file_path: str, area: str) -> list[Chunk]:
    target_version = _target_version_from_path(file_path)
    front, body = _split_front_matter(content)
    title = front.get("title", "")
    issue = front.get("issue")
    author = front.get("author")
    flag = front.get("flag")

    if not body.strip():
        return []

    sections = _split_sections(body)
    if not sections:
        sections = [("general", body)]

    chunks: list[Chunk] = []
    for section_name, section_body in sections:
        if not section_body.strip():
            continue
        full_text = f"{title}\n\n{section_body}".strip()
        chunks.append(
            Chunk(
                file_path=file_path,
                language="markdown",
                area=area,
                content=full_text[:MAX_BODY],
                start_line=1,
                end_line=1 + full_text.count("\n"),
                symbol_kind="changelog_entry",
                symbol_name=title or file_path.rsplit("/", 1)[-1],
                extra={
                    "target_version": target_version,
                    "section": section_name.lower(),
                    "issue": issue,
                    "author": author,
                    "flag": flag,
                },
            )
        )
    return chunks


def _target_version_from_path(file_path: str) -> str | None:
    m = RELEASE_DIR_RE.search(file_path)
    if not m:
        return None
    return ".".join(m.groups())


def _split_front_matter(content: str) -> tuple[dict[str, str], str]:
    m = FRONT_MATTER_RE.match(content)
    if not m:
        return {}, content
    try:
        front = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        front = {}
    if not isinstance(front, dict):
        front = {}
    return {str(k): v for k, v in front.items()}, content[m.end() :]


def _split_sections(body: str) -> list[tuple[str, str]]:
    matches = list(SECTION_HEADER_RE.finditer(body))
    if not matches:
        return []
    bounds = [m.start() for m in matches] + [len(body)]
    result: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        name = m.group(1).strip()
        section = body[bounds[i] : bounds[i + 1]]
        result.append((name, section.strip()))
    return result

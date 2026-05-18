from __future__ import annotations

import re

from shopware_intel.ingest.chunk.base import Chunk

UPGRADE_HEADER_RE = re.compile(r"^# (\d+\.\d+\.\d+\.\d+)\s*$", re.MULTILINE)
SUB_HEADER_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)

MAX_BODY = 2000


def chunk_upgrade_md(content: str, *, file_path: str, area: str) -> list[Chunk]:
    """Split UPGRADE-6.X.md into per-version, per-section chunks."""
    version_matches = list(UPGRADE_HEADER_RE.finditer(content))
    if not version_matches:
        return [
            Chunk(
                file_path=file_path,
                language="markdown",
                area=area,
                content=content[:MAX_BODY],
                start_line=1,
                end_line=content.count("\n") + 1,
                symbol_kind="upgrade_note",
                symbol_name=file_path.rsplit("/", 1)[-1],
            )
        ]

    bounds = [m.start() for m in version_matches] + [len(content)]
    chunks: list[Chunk] = []
    for i, m in enumerate(version_matches):
        version = m.group(1)
        section = content[m.start() : bounds[i + 1]]
        sub_matches = list(SUB_HEADER_RE.finditer(section))
        if not sub_matches:
            chunks.append(
                _md_chunk(file_path, area, section, version, "general", m.start(), content)
            )
            continue
        sub_bounds = [sm.start() for sm in sub_matches] + [len(section)]
        intro = section[: sub_matches[0].start()].strip()
        if intro:
            chunks.append(_md_chunk(file_path, area, intro, version, "intro", m.start(), content))
        for j, sm in enumerate(sub_matches):
            title = sm.group(1).strip()
            sub_body = section[sm.start() : sub_bounds[j + 1]]
            chunks.append(
                _md_chunk(
                    file_path, area, sub_body, version, title, m.start() + sm.start(), content
                )
            )
    return chunks


def _md_chunk(
    file_path: str,
    area: str,
    body: str,
    version: str,
    title: str,
    offset: int,
    full_text: str,
) -> Chunk:
    return Chunk(
        file_path=file_path,
        language="markdown",
        area=area,
        content=body[:MAX_BODY],
        start_line=full_text.count("\n", 0, offset) + 1,
        end_line=full_text.count("\n", 0, offset + len(body)) + 1,
        symbol_kind="upgrade_note",
        symbol_name=f"{version} — {title}",
        extra={"target_version": version, "title": title},
    )

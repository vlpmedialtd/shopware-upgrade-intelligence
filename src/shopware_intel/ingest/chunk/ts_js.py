from __future__ import annotations

import re

from shopware_intel.ingest.chunk.base import Chunk

EXPORT_DECL_RE = re.compile(
    r"^(?:export\s+(?:default\s+)?)?(?:abstract\s+)?(class|interface|function|const|enum|type)\s+([A-Za-z_$][A-Za-z0-9_$]*)",
    re.MULTILINE,
)

MAX_BODY = 2000


def chunk_ts_js(content: str, *, file_path: str, area: str, language: str) -> list[Chunk]:
    matches = list(EXPORT_DECL_RE.finditer(content))
    if not matches:
        return [
            Chunk(
                file_path=file_path,
                language=language,
                area=area,
                content=content[:MAX_BODY],
                start_line=1,
                end_line=content.count("\n") + 1,
                symbol_kind="file",
                symbol_name=file_path.rsplit("/", 1)[-1],
            )
        ]
    boundaries = [m.start() for m in matches] + [len(content)]
    chunks: list[Chunk] = []
    for i, m in enumerate(matches):
        kind = m.group(1)
        name = m.group(2)
        body = content[m.start() : boundaries[i + 1]]
        if len(body) > MAX_BODY:
            body = body[:MAX_BODY]
        chunks.append(
            Chunk(
                file_path=file_path,
                language=language,
                area=area,
                content=body,
                start_line=_line_of(content, m.start()),
                end_line=_line_of(content, boundaries[i + 1] - 1),
                symbol_kind=f"ts_{kind}",
                symbol_name=name,
            )
        )
    return chunks


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, max(0, offset)) + 1

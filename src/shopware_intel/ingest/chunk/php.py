from __future__ import annotations

import re

from shopware_intel.ingest.chunk.base import Chunk

NAMESPACE_RE = re.compile(r"^namespace\s+([A-Za-z0-9_\\]+)\s*;", re.MULTILINE)
TYPE_DECL_RE = re.compile(
    r"^((?:/\*\*[\s\S]*?\*/\s*\n)?(?:#\[[\s\S]*?\]\s*\n)*(?:final\s+|abstract\s+|readonly\s+)?(class|interface|trait|enum)\s+([A-Za-z_][A-Za-z0-9_]*))",
    re.MULTILINE,
)
DEPRECATED_TAG_RE = re.compile(r"@deprecated\s+tag:(v6\.\d+\.\d+(?:\.\d+)?)")


def chunk_php(content: str, *, file_path: str, area: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    ns_match = NAMESPACE_RE.search(content)
    namespace = ns_match.group(1) if ns_match else ""

    type_matches = list(TYPE_DECL_RE.finditer(content))
    if not type_matches:
        return [
            Chunk(
                file_path=file_path,
                language="php",
                area=area,
                content=content[:3500],
                start_line=1,
                end_line=_count_lines(content[:3500]),
                symbol_kind="file",
                symbol_name=file_path.rsplit("/", 1)[-1],
            )
        ]

    boundaries = [m.start() for m in type_matches] + [len(content)]
    for i, m in enumerate(type_matches):
        kind = m.group(2)
        name = m.group(3)
        body_start = m.start()
        body_end = boundaries[i + 1]
        body = content[body_start:body_end].strip()
        if len(body) > 3500:
            body = body[:3500]
        fqn = f"{namespace}\\{name}" if namespace else name
        deprecated_in = _find_deprecated(content[: m.end()])
        chunks.append(
            Chunk(
                file_path=file_path,
                language="php",
                area=area,
                content=body,
                start_line=_line_of_offset(content, body_start),
                end_line=_line_of_offset(content, body_end - 1),
                symbol_kind=kind,
                symbol_name=name,
                symbol_fqn=fqn,
                deprecated_in=deprecated_in,
            )
        )
    return chunks


def _find_deprecated(prefix: str) -> str | None:
    last = None
    for m in DEPRECATED_TAG_RE.finditer(prefix):
        last = m.group(1)
    return last


def _line_of_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, max(0, offset)) + 1


def _count_lines(text: str) -> int:
    return text.count("\n") + 1

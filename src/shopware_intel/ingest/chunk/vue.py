from __future__ import annotations

import re

from shopware_intel.ingest.chunk.base import Chunk

SECTION_RE = re.compile(
    r"<(template|script|style)(\s+[^>]*)?>([\s\S]*?)</\1>",
    re.MULTILINE,
)
COMPONENT_NAME_RE = re.compile(
    r"""(?:Component\.register|Component\.extend)\s*\(\s*['"]([^'"]+)['"]"""
)
SHOPWARE_OVERRIDE_RE = re.compile(r"""Component\.override\s*\(\s*['"]([^'"]+)['"]""")

MAX_BODY = 2000


def chunk_vue(content: str, *, file_path: str, area: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    file_name = file_path.rsplit("/", 1)[-1]

    component_name = None
    m = COMPONENT_NAME_RE.search(content) or SHOPWARE_OVERRIDE_RE.search(content)
    if m:
        component_name = m.group(1)

    sections = list(SECTION_RE.finditer(content))
    if not sections:
        chunks.append(
            Chunk(
                file_path=file_path,
                language="vue",
                area=area,
                content=content[:MAX_BODY],
                start_line=1,
                end_line=content.count("\n") + 1,
                symbol_kind="vue_component",
                symbol_name=component_name or file_name,
            )
        )
        return chunks

    for s in sections:
        section_kind = s.group(1)
        body = s.group(3)
        body_text = body if len(body) <= MAX_BODY else body[:MAX_BODY]
        chunks.append(
            Chunk(
                file_path=file_path,
                language="vue",
                area=area,
                content=body_text,
                start_line=_line_of(content, s.start()),
                end_line=_line_of(content, s.end()),
                symbol_kind=f"vue_{section_kind}",
                symbol_name=component_name or file_name,
            )
        )
    return chunks


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, max(0, offset)) + 1

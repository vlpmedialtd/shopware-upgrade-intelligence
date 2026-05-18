from __future__ import annotations

import re

from shopware_intel.ingest.chunk.base import Chunk

BLOCK_OPEN_RE = re.compile(r"{%\s*block\s+([A-Za-z0-9_]+)\s*%}")
BLOCK_CLOSE_RE = re.compile(r"{%\s*endblock\s*(?:[A-Za-z0-9_]+\s*)?%}")
DEPRECATED_COMMENT_RE = re.compile(
    r"{#\s*@deprecated\s+tag:(v6\.\d+\.\d+(?:\.\d+)?)[^#]*#}", re.IGNORECASE
)
EXTENDS_RE = re.compile(
    r"""{%\s*sw_extends\s+['"]([^'"]+)['"]\s*%}|{%\s*extends\s+['"]([^'"]+)['"]\s*%}"""
)

MAX_BODY = 2000


def chunk_twig(content: str, *, file_path: str, area: str) -> list[Chunk]:
    file_dep = _first_deprecation(content)
    extends = _extends_target(content)

    blocks = _extract_blocks(content)
    chunks: list[Chunk] = []

    header_lines = content.split("\n", 30)[:30]
    header = "\n".join(header_lines)[:1500]
    chunks.append(
        Chunk(
            file_path=file_path,
            language="twig",
            area=area,
            content=header,
            start_line=1,
            end_line=min(30, content.count("\n") + 1),
            symbol_kind="file",
            symbol_name=file_path.rsplit("/", 1)[-1],
            deprecated_in=file_dep,
            extra={"extends": extends} if extends else {},
        )
    )

    for block_name, body, start_offset, end_offset in blocks:
        body_text = body if len(body) <= MAX_BODY else body[:MAX_BODY]
        chunks.append(
            Chunk(
                file_path=file_path,
                language="twig",
                area=area,
                content=body_text,
                start_line=_line_of(content, start_offset),
                end_line=_line_of(content, end_offset),
                symbol_kind="twig_block",
                symbol_name=block_name,
                deprecated_in=_first_deprecation(body) or file_dep,
            )
        )
    return chunks


def _extract_blocks(content: str) -> list[tuple[str, str, int, int]]:
    opens = [(m.group(1), m.start(), m.end()) for m in BLOCK_OPEN_RE.finditer(content)]
    closes = [(m.start(), m.end()) for m in BLOCK_CLOSE_RE.finditer(content)]
    if not opens or not closes:
        return []

    result: list[tuple[str, str, int, int]] = []
    stack: list[tuple[str, int, int]] = []
    close_idx = 0
    for name, o_start, o_end in opens:
        while close_idx < len(closes) and closes[close_idx][0] < o_start:
            close_idx += 1
        stack.append((name, o_start, o_end))

    cursor = 0
    for name, o_start, o_end in opens:
        match_close = None
        for c_start, c_end in closes:
            if c_start > o_end and c_start >= cursor:
                match_close = (c_start, c_end)
                break
        if not match_close:
            continue
        body = content[o_start : match_close[1]]
        result.append((name, body, o_start, match_close[1]))
        cursor = match_close[1]
    return result


def _first_deprecation(text: str) -> str | None:
    m = DEPRECATED_COMMENT_RE.search(text)
    return m.group(1) if m else None


def _extends_target(content: str) -> str | None:
    m = EXTENDS_RE.search(content)
    if not m:
        return None
    return m.group(1) or m.group(2)


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, max(0, offset)) + 1

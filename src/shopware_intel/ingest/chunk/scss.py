from __future__ import annotations

import re

from shopware_intel.ingest.chunk.base import Chunk

CLASS_RE = re.compile(r"\.([A-Za-z_][A-Za-z0-9_-]*)\s*[,{:]")
RULE_OPEN_RE = re.compile(r"^([^{}]+)\{", re.MULTILINE)

MAX_BODY = 2000


def chunk_scss(content: str, *, file_path: str, area: str) -> list[Chunk]:
    if not content.strip():
        return []
    classes = sorted(set(CLASS_RE.findall(content)))
    file_chunk = Chunk(
        file_path=file_path,
        language="scss",
        area=area,
        content=content[:MAX_BODY],
        start_line=1,
        end_line=content.count("\n") + 1,
        symbol_kind="file",
        symbol_name=file_path.rsplit("/", 1)[-1],
        extra={"css_classes": classes[:200]},
    )
    return [file_chunk]


def extract_classes(content: str) -> list[str]:
    return sorted(set(CLASS_RE.findall(content)))

from __future__ import annotations

from shopware_intel.ingest.chunk.base import Chunk

MAX_BODY = 2000


def chunk_xml(content: str, *, file_path: str, area: str) -> list[Chunk]:
    if not content.strip():
        return []
    return [
        Chunk(
            file_path=file_path,
            language="xml",
            area=area,
            content=content[:MAX_BODY],
            start_line=1,
            end_line=content.count("\n") + 1,
            symbol_kind="file",
            symbol_name=file_path.rsplit("/", 1)[-1],
        )
    ]

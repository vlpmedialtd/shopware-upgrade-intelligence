from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Chunk:
    file_path: str
    language: str
    area: str
    content: str
    start_line: int
    end_line: int
    symbol_kind: str = "file"
    symbol_name: str = ""
    symbol_fqn: str = ""
    deprecated_in: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def content_sha(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8", errors="replace")).hexdigest()


def point_id_for(tag: str, file_path: str, index: int, content_sha: str) -> str:
    h = hashlib.blake2s(
        f"{tag}|{file_path}|{index}|{content_sha}".encode(),
        digest_size=16,
    )
    raw = h.hexdigest()
    return f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"

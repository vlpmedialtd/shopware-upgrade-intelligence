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


def embedding_text(chunk: Chunk) -> str:
    """Build the text that actually goes to the embedder.

    Prepends the canonical English identifier when one exists (PHP class/method
    FQN, Twig block name). Avoids file_path as a default prefix: paths like
    `Migration/Fixtures/mails/de-html.html.twig` hijack German-language queries by
    matching locale codes (`de-`) rather than meaning. Falls back to the file path
    only when no symbol identifier is available (e.g. xml/scss/vue file chunks).
    Markdown content is already self-descriptive.
    """
    if chunk.language == "markdown":
        return chunk.content
    identifier = chunk.symbol_fqn or chunk.symbol_name
    if not identifier:
        return chunk.file_path + "\n" + chunk.content
    if identifier in chunk.content[:200]:
        return chunk.content
    return identifier + "\n" + chunk.content


def point_id_for(tag: str, file_path: str, index: int, content_sha: str) -> str:
    h = hashlib.blake2s(
        f"{tag}|{file_path}|{index}|{content_sha}".encode(),
        digest_size=16,
    )
    raw = h.hexdigest()
    return f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"

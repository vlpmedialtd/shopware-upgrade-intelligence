from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from shopware_intel.areas import Area, classify, is_ingest_candidate, language_of


@dataclass(frozen=True)
class SourceFile:
    rel_path: str
    abs_path: Path
    area: Area
    language: str


def walk_tag(root: Path) -> Iterator[SourceFile]:
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if not is_ingest_candidate(rel):
            continue
        lang = language_of(rel)
        if lang is None:
            continue
        yield SourceFile(rel_path=rel, abs_path=p, area=classify(rel), language=lang)

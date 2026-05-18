from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient

from shopware_intel.ingest.chunk.scss import extract_classes
from shopware_intel.ingest.chunk.twig import BLOCK_OPEN_RE
from shopware_intel.ingest.clone import show_file

PHP_METHOD_RE = re.compile(
    r"^(?:\s*)(?:public|protected|private)?\s*(?:static\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)",
    re.MULTILINE,
)
PHP_DEPRECATED_RE = re.compile(r"@deprecated\s+tag:(v6\.\d+\.\d+(?:\.\d+)?)")


@dataclass
class SymbolDiff:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, list[str]]:
        return {"added": self.added, "removed": self.removed, "changed": self.changed}


@dataclass
class WhyChangedReport:
    file_path: str
    from_version: str
    to_version: str
    file_exists_from: bool
    file_exists_to: bool
    language: str
    structural_diff: dict[str, list[str]]
    new_deprecations: list[str]
    related_changelog_entries: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "file_exists_from": self.file_exists_from,
            "file_exists_to": self.file_exists_to,
            "language": self.language,
            "structural_diff": self.structural_diff,
            "new_deprecations": self.new_deprecations,
            "related_changelog_entries": self.related_changelog_entries,
        }


def _language_of(path: str) -> str:
    if path.endswith(".php"):
        return "php"
    if path.endswith((".twig", ".html.twig")):
        return "twig"
    if path.endswith(".scss") or path.endswith(".css"):
        return "scss"
    if path.endswith(".vue"):
        return "vue"
    if path.endswith((".ts", ".js")):
        return "ts"
    if path.endswith(".xml"):
        return "xml"
    return "text"


def _twig_blocks(content: str) -> set[str]:
    return {m.group(1) for m in BLOCK_OPEN_RE.finditer(content)}


def _scss_classes(content: str) -> set[str]:
    return set(extract_classes(content))


def _php_methods(content: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in PHP_METHOD_RE.finditer(content):
        name = m.group(1)
        params = re.sub(r"\s+", " ", m.group(2)).strip()
        out[name] = params
    return out


def _php_classes(content: str) -> set[str]:
    return {
        m.group(2)
        for m in re.finditer(
            r"^(?:final\s+|abstract\s+)?(class|interface|trait|enum)\s+([A-Za-z_][A-Za-z0-9_]*)",
            content,
            re.MULTILINE,
        )
    }


def _structural_diff(language: str, from_content: str, to_content: str) -> SymbolDiff:
    diff = SymbolDiff()
    if language == "twig":
        a, b = _twig_blocks(from_content), _twig_blocks(to_content)
        diff.added = sorted(b - a)
        diff.removed = sorted(a - b)
    elif language == "scss":
        a, b = _scss_classes(from_content), _scss_classes(to_content)
        diff.added = sorted(b - a)
        diff.removed = sorted(a - b)
    elif language == "php":
        a_methods, b_methods = _php_methods(from_content), _php_methods(to_content)
        diff.added = sorted(set(b_methods) - set(a_methods))
        diff.removed = sorted(set(a_methods) - set(b_methods))
        diff.changed = sorted(
            n for n in (set(a_methods) & set(b_methods)) if a_methods[n] != b_methods[n]
        )
        a_classes, b_classes = _php_classes(from_content), _php_classes(to_content)
        diff.added += sorted(b_classes - a_classes)
        diff.removed += sorted(a_classes - b_classes)
    elif language == "vue":
        a_classes, b_classes = _scss_classes(from_content), _scss_classes(to_content)
        diff.added = sorted(b_classes - a_classes)
        diff.removed = sorted(a_classes - b_classes)
    return diff


def _new_deprecations(from_content: str, to_content: str) -> list[str]:
    a = {m.group(0) for m in PHP_DEPRECATED_RE.finditer(from_content)}
    b = {m.group(0) for m in PHP_DEPRECATED_RE.finditer(to_content)}
    return sorted(b - a)


def _related_changelog(
    client: QdrantClient,
    file_path: str,
    from_version: str,
    to_version: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    base_name = file_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    needles = {file_path, base_name}

    hits: list[dict[str, Any]] = []
    offset: Any = None
    while True:
        points, offset = client.scroll(
            collection_name="changes",
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for p in points:
            payload = p.payload or {}
            version = payload.get("version", "")
            if not (from_version < version <= to_version):
                continue
            content = payload.get("content", "")
            if not any(n in content for n in needles):
                continue
            hits.append(
                {
                    "version": version,
                    "title": payload.get("symbol_name", ""),
                    "section": (payload.get("section") or "").lower()
                    or payload.get("symbol_kind", ""),
                    "issue": payload.get("issue"),
                    "snippet": content[:400] + ("…" if len(content) > 400 else ""),
                }
            )
            if len(hits) >= limit:
                break
        if offset is None or len(hits) >= limit:
            break
    return hits


def why_changed(
    mirror_path: Path,
    client: QdrantClient,
    file_path: str,
    from_version: str,
    to_version: str,
) -> WhyChangedReport:
    from_tag = f"v{from_version}"
    to_tag = f"v{to_version}"
    from_raw = show_file(mirror_path, from_tag, file_path)
    to_raw = show_file(mirror_path, to_tag, file_path)
    from_content = from_raw.decode("utf-8", errors="replace") if from_raw else ""
    to_content = to_raw.decode("utf-8", errors="replace") if to_raw else ""
    language = _language_of(file_path)
    diff = _structural_diff(language, from_content, to_content)
    new_dep = _new_deprecations(from_content, to_content)
    related = _related_changelog(client, file_path, from_version, to_version)
    return WhyChangedReport(
        file_path=file_path,
        from_version=from_version,
        to_version=to_version,
        file_exists_from=from_raw is not None,
        file_exists_to=to_raw is not None,
        language=language,
        structural_diff=diff.to_dict(),
        new_deprecations=new_dep,
        related_changelog_entries=related,
    )

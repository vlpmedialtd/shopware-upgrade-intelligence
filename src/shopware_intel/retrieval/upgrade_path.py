from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from qdrant_client import QdrantClient

SECTION_ORDER = (
    "upgrade information",
    "next major version changes",
    "core",
    "api",
    "administration",
    "storefront",
    "general",
    "intro",
)


@dataclass
class UpgradeEntry:
    target_version: str
    section: str
    title: str
    issue: str | None
    changelog_path: str
    kind: str
    snippet: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_version": self.target_version,
            "section": self.section,
            "title": self.title,
            "issue": self.issue,
            "changelog_path": self.changelog_path,
            "kind": self.kind,
            "snippet": self.snippet,
        }


def _version_tuple(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(p) for p in v.split("."))
    except (ValueError, AttributeError):
        return ()


def _section_key(name: str) -> int:
    try:
        return SECTION_ORDER.index(name)
    except ValueError:
        return len(SECTION_ORDER)


def upgrade_path(
    client: QdrantClient,
    from_version: str,
    to_version: str,
    areas: list[str] | None = None,
    limit_per_section: int = 50,
) -> dict[str, Any]:
    """Synthesize the upgrade story from from_version (exclusive) to to_version (inclusive).

    Pulls from the `changes` collection, filters by `target_version` (the version
    documented inside the changelog file, not the ingest tag), groups by section,
    deduplicates by issue id where present.
    """
    from_t = _version_tuple(from_version)
    to_t = _version_tuple(to_version)
    if not from_t or not to_t or from_t >= to_t:
        return {
            "from_version": from_version,
            "to_version": to_version,
            "error": "invalid version range",
            "sections": {},
        }

    requested_areas = {a.lower() for a in areas} if areas else None
    by_section: dict[str, list[UpgradeEntry]] = defaultdict(list)
    seen_issues: set[str] = set()
    seen_files: set[str] = set()

    offset: Any = None
    while True:
        points, offset = client.scroll(
            collection_name="changes",
            limit=512,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for p in points:
            payload = p.payload or {}
            target = payload.get("target_version", "")
            t_tuple = _version_tuple(target)
            if not t_tuple or not (from_t < t_tuple <= to_t):
                continue
            section = (payload.get("section") or "").lower() or "general"
            if requested_areas and section not in requested_areas:
                continue
            issue = payload.get("issue")
            if issue and issue in seen_issues:
                continue
            cl_file = payload.get("file_path", "")
            section_key = f"{cl_file}::{section}"
            if section_key in seen_files:
                continue
            seen_files.add(section_key)
            if issue:
                seen_issues.add(issue)
            content = payload.get("content", "")
            entry = UpgradeEntry(
                target_version=target,
                section=section,
                title=payload.get("symbol_name", "") or "(untitled)",
                issue=issue,
                changelog_path=cl_file,
                kind=payload.get("symbol_kind", ""),
                snippet=content[:500] + ("…" if len(content) > 500 else ""),
            )
            by_section[section].append(entry)
        if offset is None:
            break

    sections_sorted = {
        section: sorted(entries, key=lambda e: (_version_tuple(e.target_version), e.title))[
            :limit_per_section
        ]
        for section, entries in sorted(by_section.items(), key=lambda kv: _section_key(kv[0]))
    }

    total = sum(len(v) for v in sections_sorted.values())
    return {
        "from_version": from_version,
        "to_version": to_version,
        "areas_filter": sorted(requested_areas) if requested_areas else None,
        "total_entries": total,
        "sections": {k: [e.to_dict() for e in v] for k, v in sections_sorted.items()},
    }

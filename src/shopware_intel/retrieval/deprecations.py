from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from shopware_intel.ingest.load import CODE_COLLECTIONS


@dataclass
class DeprecationRecord:
    symbol_fqn: str
    symbol_name: str
    symbol_kind: str
    deprecated_in: str
    file_path: str
    area: str
    language: str
    first_version_seen: str
    last_version_seen: str
    snippet: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol_fqn": self.symbol_fqn,
            "symbol_name": self.symbol_name,
            "symbol_kind": self.symbol_kind,
            "deprecated_in": self.deprecated_in,
            "file_path": self.file_path,
            "area": self.area,
            "language": self.language,
            "first_version_seen": self.first_version_seen,
            "last_version_seen": self.last_version_seen,
            "snippet": self.snippet,
        }


def _has_deprecation_filter(pattern: str | None) -> qm.Filter:
    must: list[Any] = [
        qm.IsNullCondition(is_null=qm.PayloadField(key="deprecated_in")),
    ]
    return qm.Filter(must_not=must)


def find_deprecations(
    client: QdrantClient, pattern: str | None = None, area: str | None = None, limit: int = 100
) -> list[DeprecationRecord]:
    collections = [area] if area in CODE_COLLECTIONS else list(CODE_COLLECTIONS)

    aggregated: dict[str, DeprecationRecord] = {}
    for col in collections:
        offset: Any = None
        seen = 0
        while True:
            points, offset = client.scroll(
                collection_name=col,
                scroll_filter=_has_deprecation_filter(pattern),
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for p in points:
                payload = p.payload or {}
                fqn = payload.get("symbol_fqn") or payload.get("symbol_name", "")
                if not fqn:
                    continue
                if pattern and pattern.lower() not in fqn.lower():
                    name = payload.get("symbol_name", "")
                    if pattern.lower() not in name.lower():
                        continue
                version = payload.get("version", "")
                existing = aggregated.get(fqn)
                if existing is None:
                    snippet = payload.get("content", "")[:300]
                    aggregated[fqn] = DeprecationRecord(
                        symbol_fqn=fqn,
                        symbol_name=payload.get("symbol_name", ""),
                        symbol_kind=payload.get("symbol_kind", ""),
                        deprecated_in=payload.get("deprecated_in", ""),
                        file_path=payload.get("file_path", ""),
                        area=payload.get("area", ""),
                        language=payload.get("language", ""),
                        first_version_seen=version,
                        last_version_seen=version,
                        snippet=snippet,
                    )
                else:
                    if version and version < existing.first_version_seen:
                        existing.first_version_seen = version
                    if version and version > existing.last_version_seen:
                        existing.last_version_seen = version
                seen += 1
                if len(aggregated) >= limit and pattern is None:
                    break
            if offset is None or (len(aggregated) >= limit and pattern is None):
                break
        if len(aggregated) >= limit and pattern is None:
            break

    return sorted(
        aggregated.values(),
        key=lambda r: (r.deprecated_in, r.symbol_fqn),
    )[:limit]

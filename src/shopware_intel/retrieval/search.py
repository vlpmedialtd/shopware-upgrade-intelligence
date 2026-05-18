from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from shopware_intel.config import Settings
from shopware_intel.ingest.embed import OllamaEmbedder


@dataclass
class Hit:
    score: float
    version: str
    area: str
    file_path: str
    language: str
    symbol_kind: str
    symbol_name: str
    symbol_fqn: str
    deprecated_in: str | None
    start_line: int
    end_line: int
    snippet: str

    @classmethod
    def from_point(cls, point: Any) -> Hit:
        p = point.payload or {}
        content = p.get("content", "")
        snippet = content if len(content) <= 600 else content[:600] + "…"
        return cls(
            score=float(point.score or 0.0),
            version=p.get("version", ""),
            area=p.get("area", ""),
            file_path=p.get("file_path", ""),
            language=p.get("language", ""),
            symbol_kind=p.get("symbol_kind", ""),
            symbol_name=p.get("symbol_name", ""),
            symbol_fqn=p.get("symbol_fqn", ""),
            deprecated_in=p.get("deprecated_in"),
            start_line=int(p.get("start_line", 0)),
            end_line=int(p.get("end_line", 0)),
            snippet=snippet,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 4),
            "version": self.version,
            "area": self.area,
            "file_path": self.file_path,
            "language": self.language,
            "symbol_kind": self.symbol_kind,
            "symbol_name": self.symbol_name,
            "symbol_fqn": self.symbol_fqn,
            "deprecated_in": self.deprecated_in,
            "lines": f"{self.start_line}-{self.end_line}",
            "snippet": self.snippet,
        }


def build_filter(
    *,
    version: str | None = None,
    language: str | None = None,
    file_path: str | None = None,
) -> qm.Filter | None:
    must: list[Any] = []
    if version:
        must.append(qm.FieldCondition(key="version", match=qm.MatchValue(value=version)))
    if language:
        must.append(qm.FieldCondition(key="language", match=qm.MatchValue(value=language)))
    if file_path:
        must.append(qm.FieldCondition(key="file_path", match=qm.MatchValue(value=file_path)))
    return qm.Filter(must=must) if must else None


class Searcher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = QdrantClient(path=str(settings.qdrant_path))
        self.embedder = OllamaEmbedder(
            settings.ollama_host, settings.embed_model, settings.embed_dim
        )

    async def close(self) -> None:
        await self.embedder.close()
        self.client.close()

    async def search_collection(
        self,
        collection: str,
        query: str,
        *,
        version: str | None = None,
        language: str | None = None,
        file_path: str | None = None,
        limit: int = 10,
    ) -> list[Hit]:
        vec = await self.embedder.embed_one(query, kind="query")
        qfilter = build_filter(version=version, language=language, file_path=file_path)
        oversample = limit * 4 if collection == "changes" else limit
        response = self.client.query_points(
            collection_name=collection,
            query=vec,
            query_filter=qfilter,
            limit=oversample,
            with_payload=True,
        )
        hits = [Hit.from_point(p) for p in response.points]
        if collection == "changes":
            hits = _dedup_changelog_hits(hits)
        return hits[:limit]


def _dedup_changelog_hits(hits: list[Hit]) -> list[Hit]:
    """A logical changelog entry (e.g. release-6-5-2-0/foo.md) is re-indexed once per
    ingest tag because Shopware ships its full historical `changelog/` tree in every
    release. Different sections of the same entry are kept distinct (their content
    differs); duplicate ingestions of the same section collapse to the highest-scoring
    hit, which arrives first since `query_points` is score-ordered."""
    seen: set[tuple[str, str, str, str]] = set()
    out: list[Hit] = []
    for h in hits:
        basename = h.file_path.rsplit("/", 1)[-1]
        release_marker = ""
        if "release-" in h.file_path:
            release_marker = h.file_path.split("release-", 1)[1].split("/", 1)[0]
        section_signature = (h.snippet or "")[:120]
        key = (release_marker or h.file_path, h.symbol_name, basename, section_signature)
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
    return out

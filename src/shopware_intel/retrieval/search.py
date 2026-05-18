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
        response = self.client.query_points(
            collection_name=collection,
            query=vec,
            query_filter=qfilter,
            limit=limit,
            with_payload=True,
        )
        return [Hit.from_point(p) for p in response.points]

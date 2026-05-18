from __future__ import annotations

import contextlib
from collections.abc import Sequence
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from shopware_intel.areas import Area
from shopware_intel.ingest.chunk.base import Chunk, point_id_for

CODE_COLLECTIONS = tuple(
    a.value for a in (Area.CORE, Area.STOREFRONT, Area.ADMINISTRATION, Area.CHECKOUT, Area.FLOW)
)
META_COLLECTIONS = ("changes",)
SYMBOL_COLLECTION = "symbols"


def open_client(qdrant_path: Path, url: str | None = None) -> QdrantClient:
    if url:
        return QdrantClient(url=url, prefer_grpc=False, timeout=60)
    qdrant_path.mkdir(parents=True, exist_ok=True)
    return QdrantClient(path=str(qdrant_path))


def ensure_collections(client: QdrantClient, dim: int) -> None:
    existing = {c.name for c in client.get_collections().collections}
    for name in (*CODE_COLLECTIONS, *META_COLLECTIONS):
        if name not in existing:
            client.create_collection(
                collection_name=name,
                vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
            )
            _create_payload_indexes(client, name)
    if SYMBOL_COLLECTION not in existing:
        client.create_collection(
            collection_name=SYMBOL_COLLECTION,
            vectors_config=qm.VectorParams(size=4, distance=qm.Distance.COSINE),
        )
        _create_symbol_indexes(client)


def _create_payload_indexes(client: QdrantClient, name: str) -> None:
    for field, schema in (
        ("version", qm.PayloadSchemaType.KEYWORD),
        ("area", qm.PayloadSchemaType.KEYWORD),
        ("language", qm.PayloadSchemaType.KEYWORD),
        ("symbol_kind", qm.PayloadSchemaType.KEYWORD),
        ("symbol_fqn", qm.PayloadSchemaType.KEYWORD),
        ("deprecated_in", qm.PayloadSchemaType.KEYWORD),
        ("file_path", qm.PayloadSchemaType.KEYWORD),
    ):
        with contextlib.suppress(Exception):
            client.create_payload_index(collection_name=name, field_name=field, field_schema=schema)


def _create_symbol_indexes(client: QdrantClient) -> None:
    for field, schema in (
        ("version", qm.PayloadSchemaType.KEYWORD),
        ("fqn", qm.PayloadSchemaType.KEYWORD),
        ("kind", qm.PayloadSchemaType.KEYWORD),
        ("file_path", qm.PayloadSchemaType.KEYWORD),
    ):
        with contextlib.suppress(Exception):
            client.create_payload_index(
                collection_name=SYMBOL_COLLECTION, field_name=field, field_schema=schema
            )


def upsert_chunks(
    client: QdrantClient,
    collection: str,
    tag: str,
    chunks: Sequence[Chunk],
    vectors: Sequence[Sequence[float]],
) -> list[str]:
    if not chunks:
        return []
    version = tag.lstrip("v")
    version_tuple = [int(x) for x in version.split(".")]
    points: list[qm.PointStruct] = []
    point_ids: list[str] = []
    for idx, (chunk, vec) in enumerate(zip(chunks, vectors, strict=True)):
        pid = point_id_for(tag, chunk.file_path, idx, chunk.content_sha)
        point_ids.append(pid)
        payload = {
            "version": version,
            "version_tuple": version_tuple,
            "area": chunk.area,
            "file_path": chunk.file_path,
            "language": chunk.language,
            "symbol_kind": chunk.symbol_kind,
            "symbol_name": chunk.symbol_name,
            "symbol_fqn": chunk.symbol_fqn,
            "deprecated_in": chunk.deprecated_in,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "content": chunk.content,
        }
        payload.update(chunk.extra)
        points.append(qm.PointStruct(id=pid, vector=list(vec), payload=payload))

    # Qdrant's default HTTP body limit is 32 MB; chunked upsert keeps each payload
    # well under that for the 2 KB-payload chunks we produce.
    BATCH = 512
    for i in range(0, len(points), BATCH):
        client.upsert(collection_name=collection, points=points[i : i + BATCH])
    return point_ids

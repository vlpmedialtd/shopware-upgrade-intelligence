from __future__ import annotations

import asyncio
from collections.abc import Sequence

import httpx


class OllamaEmbedder:
    def __init__(self, host: str, model: str, dim: int, batch_size: int = 64) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.dim = dim
        self.batch_size = batch_size
        self._client = httpx.AsyncClient(timeout=120.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def embed(self, texts: Sequence[str], *, kind: str = "document") -> list[list[float]]:
        if not texts:
            return []
        prefix = "search_query: " if kind == "query" else "search_document: "
        prepared = [prefix + t for t in texts]
        results: list[list[float]] = []
        for i in range(0, len(prepared), self.batch_size):
            batch = prepared[i : i + self.batch_size]
            resp = await self._client.post(
                f"{self.host}/api/embed",
                json={
                    "model": self.model,
                    "input": batch,
                    "truncate": True,
                    "options": {"num_ctx": 8192},
                },
            )
            if resp.status_code != 200:
                body = resp.text[:500]
                lengths = sorted({len(t) for t in batch}, reverse=True)[:5]
                raise RuntimeError(
                    f"ollama embed {resp.status_code} (batch={len(batch)}, longest_chars={lengths}): {body}"
                )
            data = resp.json()
            embeddings = data.get("embeddings")
            if not embeddings or len(embeddings) != len(batch):
                raise RuntimeError(
                    f"ollama returned {len(embeddings) if embeddings else 0} embeddings for batch of {len(batch)}; body: {resp.text[:300]}"
                )
            results.extend(embeddings)
        return results

    async def embed_one(self, text: str, *, kind: str = "query") -> list[float]:
        out = await self.embed([text], kind=kind)
        return out[0]


async def ping(host: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{host.rstrip('/')}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


def ping_sync(host: str) -> bool:
    return asyncio.run(ping(host))

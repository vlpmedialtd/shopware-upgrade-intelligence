from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

CSS_AREAS = ("storefront", "administration", "checkout", "flow")


@dataclass
class CssClassHit:
    class_name: str
    file_path: str
    version: str
    area: str
    language: str
    snippet: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "class_name": self.class_name,
            "file_path": self.file_path,
            "version": self.version,
            "area": self.area,
            "language": self.language,
            "snippet": self.snippet,
        }


def find_css_class(
    client: QdrantClient,
    class_name: str,
    version: str | None = None,
    limit: int = 30,
) -> dict[str, list[CssClassHit]]:
    """Locate where a CSS class is defined (SCSS) and used (Twig).

    Implementation note: payload-indexed `array_contains` is not available in
    embedded Qdrant, so we scroll the SCSS / Twig population and filter in Python.
    Cheap enough at current scale; if we ever go past 10M points this should move
    to a dedicated symbols collection.
    """
    needle = class_name.lstrip(".")

    must: list[Any] = []
    if version:
        must.append(qm.FieldCondition(key="version", match=qm.MatchValue(value=version)))

    definitions: list[CssClassHit] = []
    usages: list[CssClassHit] = []

    for col in CSS_AREAS:
        offset: Any = None
        while True:
            points, offset = client.scroll(
                collection_name=col,
                scroll_filter=qm.Filter(must=must) if must else None,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for p in points:
                payload = p.payload or {}
                lang = payload.get("language", "")
                content = payload.get("content", "")
                if lang == "scss":
                    classes = payload.get("css_classes") or []
                    if needle in classes:
                        definitions.append(_hit(needle, payload))
                elif lang == "twig":
                    if needle in content:
                        usages.append(_hit(needle, payload))
                if len(definitions) + len(usages) >= limit * 2:
                    break
            if offset is None or len(definitions) + len(usages) >= limit * 2:
                break

    return {
        "definitions": definitions[:limit],
        "usages": usages[:limit],
    }


def _hit(class_name: str, payload: dict[str, Any]) -> CssClassHit:
    content = payload.get("content", "")
    snippet = content if len(content) <= 400 else content[:400] + "…"
    return CssClassHit(
        class_name=class_name,
        file_path=payload.get("file_path", ""),
        version=payload.get("version", ""),
        area=payload.get("area", ""),
        language=payload.get("language", ""),
        snippet=snippet,
    )

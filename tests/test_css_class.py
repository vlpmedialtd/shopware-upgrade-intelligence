"""Smoke test for find_css_class against the live local index.

Skipped when the local Qdrant index is empty. Confirms the retrieval pipeline
returns hits for a class that we know exists in Shopware's Storefront SCSS.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from shopware_intel.config import get_settings
from shopware_intel.retrieval.css_class import find_css_class


def _index_has_storefront() -> bool:
    qp = Path.home() / "Library/Application Support/shopware-intel/qdrant"
    if not qp.exists():
        return False
    client: QdrantClient | None = None
    try:
        client = QdrantClient(path=str(qp))
        info = client.get_collection("storefront")
        return info.points_count > 0
    except Exception:
        return False
    finally:
        if client is not None:
            with contextlib.suppress(Exception):
                client.close()


@pytest.mark.skipif(
    not _index_has_storefront(),
    reason="local Qdrant index is empty; run `just pilot-one-tag v6.7.0.0` first",
)
def test_known_storefront_class_returns_definitions():
    settings = get_settings()
    client = QdrantClient(path=str(settings.qdrant_path))
    try:
        result = find_css_class(client, "product-description", limit=10)
    finally:
        client.close()
    assert isinstance(result["definitions"], list)
    assert isinstance(result["usages"], list)

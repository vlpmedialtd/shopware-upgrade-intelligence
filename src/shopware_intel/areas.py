from __future__ import annotations

from enum import StrEnum
from pathlib import PurePosixPath


class Area(StrEnum):
    CORE = "core"
    STOREFRONT = "storefront"
    ADMINISTRATION = "administration"
    CHECKOUT = "checkout"
    FLOW = "flow"
    CHANGES = "changes"
    OTHER = "other"


def classify(path: str) -> Area:
    p = path.lstrip("./")
    norm = PurePosixPath(p).as_posix()

    if norm.startswith("changelog/") or norm.startswith("UPGRADE-"):
        return Area.CHANGES
    if (
        "src/Core/Content/Flow/" in norm
        or "src/Administration/Resources/app/administration/src/module/sw-flow" in norm
    ):
        return Area.FLOW
    if (
        "src/Core/Checkout/" in norm
        or "Storefront/Resources/views/storefront/page/checkout" in norm
        or "Storefront/Resources/views/storefront/component/checkout" in norm
    ):
        return Area.CHECKOUT
    if "src/Administration/" in norm:
        return Area.ADMINISTRATION
    if "src/Storefront/" in norm:
        return Area.STOREFRONT
    if "src/Core/" in norm:
        return Area.CORE
    return Area.OTHER


CODE_LANGUAGES = {
    ".php": "php",
    ".twig": "twig",
    ".vue": "vue",
    ".ts": "ts",
    ".js": "js",
    ".scss": "scss",
    ".css": "css",
    ".xml": "xml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
}


def language_of(path: str) -> str | None:
    p = PurePosixPath(path)
    return CODE_LANGUAGES.get(p.suffix.lower())


EXCLUDE_SEGMENTS = frozenset({"tests", "Test", "vendor", "node_modules"})
EXCLUDE_SUBSTRINGS = (
    "/Resources/public/",
    "/Resources/dist/",
    ".spec.",
    ".test.",
    "Migration_",
)


def is_ingest_candidate(path: str) -> bool:
    if language_of(path) is None:
        return False
    norm = path.replace("\\", "/")
    if any(seg in EXCLUDE_SEGMENTS for seg in norm.split("/")):
        return False
    return not any(pat in norm for pat in EXCLUDE_SUBSTRINGS)

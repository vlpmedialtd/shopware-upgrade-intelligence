# mypy: disable-error-code="untyped-decorator,no-untyped-call"
from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from shopware_intel.config import get_settings
from shopware_intel.retrieval.css_class import find_css_class
from shopware_intel.retrieval.deprecations import find_deprecations
from shopware_intel.retrieval.search import Searcher
from shopware_intel.retrieval.upgrade_path import upgrade_path
from shopware_intel.retrieval.why_changed import why_changed

log = logging.getLogger(__name__)


def _search_tool(name: str, area_label: str, examples: str) -> Tool:
    return Tool(
        name=name,
        description=(
            f"Semantic search across the Shopware {area_label} code (indexed across all known "
            f"Shopware 6 versions). Use this for questions like: {examples}\n\n"
            "TIP: Shopware's source uses English identifiers (PHP class names, event names, "
            "service IDs, Twig block names). German prose queries match weakly — if your query "
            "is 'wie greife ich auf das Kategorielisting zu', also try the English/code form "
            "'ProductListingCriteriaEvent', 'product-listing.criteria', or the file path "
            "'src/Storefront/Resources/views/storefront/component/listing/'. The retrieval "
            "model is local nomic-embed-text and does not bridge German prose → English code "
            "well; one extra call with the technical term usually fixes a poor first result."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural-language question or code phrase.",
                },
                "version": {
                    "type": "string",
                    "description": "Optional Shopware version (e.g. '6.7.0.0').",
                },
                "language": {
                    "type": "string",
                    "description": "Optional language filter: php | twig | vue | ts | js | scss | xml | markdown.",
                },
                "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50},
            },
            "required": ["query"],
        },
    )


_TOOL_DEFINITIONS: list[Tool] = [
    _search_tool(
        "search_core",
        "Core (Framework, DataAbstractionLayer, System, Content)",
        "'how does EntityRepository work in 6.7?', 'how do I write a custom entity loader?'",
    ),
    _search_tool(
        "search_storefront",
        "Storefront (Twig templates, SCSS, Storefront-JS, Storefront-PHP)",
        "'wie greife ich im Frontend auf das Kategorielisting zu?', 'wo wird der Produkt-Card-Block definiert?'",
    ),
    _search_tool(
        "search_administration",
        "Administration (Vue SFCs, TS/JS, Admin-Twig)",
        "'wie überschreibe ich das Produkt-Detail-Modul im Admin?'",
    ),
    _search_tool(
        "search_checkout",
        "Checkout (cross-cut Storefront + Core checkout)",
        "'wo wird die Versandkostenberechnung im Checkout aufgerufen?'",
    ),
    _search_tool(
        "search_flow_builder",
        "Flow Builder (triggers, actions, admin-modules)",
        "'welche Trigger gibt es für Bestellzustands-Änderungen?'",
    ),
    Tool(
        name="search_changes",
        description=(
            "Search the indexed Shopware changelog YAML entries and UPGRADE-6.X.md notes. "
            "Use for 'was kam neu in 6.7?', 'changelog entries about flow builder triggers', "
            "'breaking changes to ArrayEntity', etc."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "version": {"type": "string", "description": "Filter to a specific version."},
                "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="find_deprecations",
        description=(
            "List Shopware symbols marked @deprecated, optionally filtered by name/pattern and "
            "area. Each result includes the version the deprecation was first observed in plus "
            "the targeted removal version (e.g. tag:v6.8.0). Use for: 'when was KernelListener "
            "deprecated?', 'which API classes are scheduled for removal in 6.8?'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Optional substring (case-insensitive) to match against symbol_fqn or symbol_name.",
                },
                "area": {
                    "type": "string",
                    "description": "Optional area: core | storefront | administration | checkout | flow.",
                },
                "limit": {"type": "integer", "default": 50, "minimum": 1, "maximum": 200},
            },
        },
    ),
    Tool(
        name="find_css_class",
        description=(
            "Find where a Storefront CSS class is defined (in SCSS) and used (in Twig templates). "
            "Pass the class name without the leading dot. Use for: 'welche CSS-Klasse stylt die "
            "Produktbeschreibung?', 'wo wird product-card verwendet?'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "class_name": {
                    "type": "string",
                    "description": "CSS class name without leading dot.",
                },
                "version": {"type": "string", "description": "Optional version filter."},
                "limit": {"type": "integer", "default": 30, "minimum": 1, "maximum": 200},
            },
            "required": ["class_name"],
        },
    ),
    Tool(
        name="upgrade_path",
        description=(
            "Synthesize the upgrade story from one Shopware version to another. Aggregates "
            "changelog entries and UPGRADE-6.X.md sections whose target_version falls into "
            "the (from, to] range, groups by section (Core / API / Storefront / Administration / "
            "etc.), and deduplicates by NEXT-* issue id. Use for: 'was muss ich vor dem Update "
            "von 6.4.20.2 auf 6.7.0.0 anpassen?', 'was kam neu zwischen 6.6 und 6.7 im API?'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "from_version": {
                    "type": "string",
                    "description": "Lower bound (exclusive), e.g. '6.4.20.2'.",
                },
                "to_version": {
                    "type": "string",
                    "description": "Upper bound (inclusive), e.g. '6.7.0.0'.",
                },
                "areas": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional section filter; subset of [core, api, administration, storefront, upgrade information, next major version changes].",
                },
                "limit_per_section": {
                    "type": "integer",
                    "default": 50,
                    "minimum": 1,
                    "maximum": 200,
                },
            },
            "required": ["from_version", "to_version"],
        },
    ),
    Tool(
        name="why_changed",
        description=(
            "Structural diff of a single Shopware file across two versions, plus linked changelog "
            "entries that mention the file. Detects Twig block additions/removals, SCSS class "
            "changes, PHP method-signature changes, and new @deprecated markers. Use for: 'warum "
            "sieht meine Storefront nach dem Update anders aus?', 'was hat sich an "
            "src/Storefront/.../product-detail/index.html.twig zwischen 6.5 und 6.6 geändert?'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Repo-relative path, e.g. src/Storefront/Resources/views/storefront/page/product-detail/index.html.twig",
                },
                "from_version": {"type": "string", "description": "e.g. '6.5.0.0'"},
                "to_version": {"type": "string", "description": "e.g. '6.6.0.0'"},
            },
            "required": ["file_path", "from_version", "to_version"],
        },
    ),
]


_SEARCH_AREA_BY_TOOL = {
    "search_core": "core",
    "search_storefront": "storefront",
    "search_administration": "administration",
    "search_checkout": "checkout",
    "search_flow_builder": "flow",
    "search_changes": "changes",
}


def _build_server() -> Server:
    app: Server = Server("shopware-upgrade-intelligence")
    settings = get_settings()
    searcher = Searcher(settings)

    @app.list_tools()
    async def list_tools() -> list[Tool]:
        return _TOOL_DEFINITIONS

    @app.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        if name in _SEARCH_AREA_BY_TOOL:
            return await _search(_SEARCH_AREA_BY_TOOL[name], arguments, searcher)
        if name == "find_deprecations":
            return _deprecations(arguments, searcher)
        if name == "find_css_class":
            return _css_class(arguments, searcher)
        if name == "why_changed":
            return _why_changed(arguments, searcher, settings)
        if name == "upgrade_path":
            return _upgrade_path(arguments, searcher)
        raise ValueError(f"Unknown tool: {name}")

    return app


async def _search(
    collection: str, arguments: dict[str, Any], searcher: Searcher
) -> list[TextContent]:
    query = arguments["query"]
    version = arguments.get("version")
    language = arguments.get("language")
    limit = int(arguments.get("limit", 10))
    hits = await searcher.search_collection(
        collection, query, version=version, language=language, limit=limit
    )
    if not hits:
        return [TextContent(type="text", text=f"No matches for: {query!r}")]
    payload = {
        "query": query,
        "version_filter": version,
        "language_filter": language,
        "collection": collection,
        "hits": [h.to_dict() for h in hits],
    }
    return [TextContent(type="text", text=json.dumps(payload, indent=2, ensure_ascii=False))]


def _deprecations(arguments: dict[str, Any], searcher: Searcher) -> list[TextContent]:
    pattern = arguments.get("pattern")
    area = arguments.get("area")
    limit = int(arguments.get("limit", 50))
    records = find_deprecations(searcher.client, pattern=pattern, area=area, limit=limit)
    payload = {
        "pattern": pattern,
        "area": area,
        "count": len(records),
        "deprecations": [r.to_dict() for r in records],
    }
    return [TextContent(type="text", text=json.dumps(payload, indent=2, ensure_ascii=False))]


def _css_class(arguments: dict[str, Any], searcher: Searcher) -> list[TextContent]:
    class_name = arguments["class_name"]
    version = arguments.get("version")
    limit = int(arguments.get("limit", 30))
    result = find_css_class(searcher.client, class_name, version=version, limit=limit)
    payload = {
        "class_name": class_name.lstrip("."),
        "version_filter": version,
        "definitions": [h.to_dict() for h in result["definitions"]],
        "usages": [h.to_dict() for h in result["usages"]],
    }
    return [TextContent(type="text", text=json.dumps(payload, indent=2, ensure_ascii=False))]


def _why_changed(arguments: dict[str, Any], searcher: Searcher, settings: Any) -> list[TextContent]:
    report = why_changed(
        settings.mirror_path,
        searcher.client,
        arguments["file_path"],
        arguments["from_version"],
        arguments["to_version"],
    )
    return [
        TextContent(type="text", text=json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    ]


def _upgrade_path(arguments: dict[str, Any], searcher: Searcher) -> list[TextContent]:
    result = upgrade_path(
        searcher.client,
        arguments["from_version"],
        arguments["to_version"],
        areas=arguments.get("areas"),
        limit_per_section=int(arguments.get("limit_per_section", 50)),
    )
    return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]


async def _serve() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )
    app = _build_server()
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


def main() -> None:
    asyncio.run(_serve())


if __name__ == "__main__":
    main()

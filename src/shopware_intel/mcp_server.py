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
from shopware_intel.retrieval.search import Searcher

log = logging.getLogger(__name__)


def _search_tool(name: str, area: str, area_label: str, examples: str) -> Tool:
    return Tool(
        name=name,
        description=(
            f"Semantic search across the Shopware {area_label} code (indexed across all known "
            f"Shopware 6 versions). Use this for questions like: {examples}"
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
                    "description": "Optional Shopware version (e.g. '6.7.0.0'). If omitted, searches across all indexed versions.",
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
        "core",
        "Core (Framework, DataAbstractionLayer, System, Content, Checkout-core)",
        "'how does EntityRepository work in 6.7?', 'where is the cart calculator?', 'how do I write a custom entity loader?'",
    ),
    _search_tool(
        "search_storefront",
        "storefront",
        "Storefront (Twig templates, SCSS, Storefront-JS, Storefront-PHP)",
        "'wie greife ich im Frontend auf das Kategorielisting zu?', 'welche CSS-Klasse stylt die Produktbeschreibung?', 'wo wird der Produkt-Card-Block definiert?'",
    ),
    _search_tool(
        "search_administration",
        "administration",
        "Administration (Vue SFCs, TS/JS, Admin-Twig)",
        "'wie überschreibe ich das Produkt-Detail-Modul im Admin?', 'wo wird sw-product-list initialisiert?'",
    ),
    _search_tool(
        "search_checkout",
        "checkout",
        "Checkout (cross-cut Storefront + Core checkout)",
        "'wo wird die Versandkostenberechnung im Checkout aufgerufen?', 'welche Validierungen laufen im OffcanvasCart?'",
    ),
    _search_tool(
        "search_flow_builder",
        "flow",
        "Flow Builder (triggers, actions, admin-modules)",
        "'welche Trigger gibt es für Bestellzustands-Änderungen?', 'wie definiere ich eine Custom-Flow-Aktion?'",
    ),
    Tool(
        name="search_changes",
        description=(
            "Search the indexed Shopware changelog and UPGRADE notes. Use this when you need to know "
            "what was added/changed/deprecated in a specific patch — e.g. 'was kam neu in 6.7?', "
            "'changelog entries about flow builder triggers in 6.6.*'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "version": {
                    "type": "string",
                    "description": "Filter to a specific version (e.g. '6.7.0.0').",
                },
                "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50},
            },
            "required": ["query"],
        },
    ),
]


_AREA_BY_TOOL = {
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
        collection = _AREA_BY_TOOL.get(name)
        if collection is None:
            raise ValueError(f"Unknown tool: {name}")
        return await _search(collection, arguments, searcher)

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

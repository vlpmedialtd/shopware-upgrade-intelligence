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


_TOOL_DEFINITIONS: list[Tool] = [
    Tool(
        name="search_core",
        description=(
            "Search the Shopware Core PHP code (Framework, DataAbstractionLayer, System, Content, "
            "Checkout-core etc.). Use this for plugin-development questions: 'how does EntityRepository "
            "work in 6.7', 'where is the cart calculator defined', 'how do I write a custom entity loader'."
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
                "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50},
            },
            "required": ["query"],
        },
    ),
]


def _build_server() -> Server:
    app: Server = Server("shopware-upgrade-intelligence")
    settings = get_settings()
    searcher = Searcher(settings)

    @app.list_tools()
    async def list_tools() -> list[Tool]:
        return _TOOL_DEFINITIONS

    @app.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        if name == "search_core":
            return await _search_area("core", arguments, searcher)
        raise ValueError(f"Unknown tool: {name}")

    return app


async def _search_area(
    area: str, arguments: dict[str, Any], searcher: Searcher
) -> list[TextContent]:
    query = arguments["query"]
    version = arguments.get("version")
    limit = int(arguments.get("limit", 10))
    hits = await searcher.search_collection(area, query, version=version, limit=limit)
    if not hits:
        return [TextContent(type="text", text=f"No matches for: {query!r}")]
    payload = {
        "query": query,
        "version_filter": version,
        "area": area,
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

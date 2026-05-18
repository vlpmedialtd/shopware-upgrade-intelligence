# Area routing

`src/shopware_intel/areas.py::classify(path)` is the single source of truth for which
Qdrant collection a given file lands in. Routing is intentionally short-circuit: the
first matching rule wins.

| Order | Rule | Area | Why this order |
|---|---|---|---|
| 1 | `changelog/` or `UPGRADE-` prefix | `changes` | Upgrade metadata is queryable independently |
| 2 | `src/Core/Content/Flow/` or admin `module/sw-flow/` | `flow` | Cross-cut: must beat both core and admin |
| 3 | `src/Core/Checkout/` or storefront `checkout` views | `checkout` | Cross-cut: must beat both core and storefront |
| 4 | `src/Administration/` | `administration` | After flow check |
| 5 | `src/Storefront/` | `storefront` | After checkout check |
| 6 | `src/Core/` | `core` | Fallback for core files |
| _ | anything else | `other` | Skipped at ingest time |

## File-level filter

`is_ingest_candidate(path)` runs after classification and rejects:

- files in path segments `tests`, `Test`, `vendor`, `node_modules`
- paths containing `/Resources/public/`, `/Resources/dist/`
- files matching `*.spec.*`, `*.test.*`, `Migration_*`
- file extensions not in the supported language set (`.php`, `.twig`, `.vue`, `.ts`,
  `.js`, `.scss`, `.css`, `.xml`, `.yaml/.yml`, `.md`)

## Adding a new area

1. Add an `Area` enum value in `areas.py`.
2. Add the routing rule in `classify()` in the correct precedence position.
3. Add the collection name to `CODE_COLLECTIONS` in `ingest/load.py` (or as a special
   case if it's not vector-based).
4. Add a new MCP tool in `mcp_server.py` and route it via `_AREA_BY_TOOL`.
5. Add test coverage in `tests/test_areas.py`.

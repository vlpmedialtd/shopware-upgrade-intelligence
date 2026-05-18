# Shopware Upgrade Intelligence

> Ask Claude Code anything about any Shopware 6 version — locally, with structured breaking-change intel.

A local-first **RAG-MCP server** that indexes every stable Shopware 6 release tag from 6.4 onwards
and exposes it to [Claude Code](https://claude.com/claude-code) via the Model Context Protocol.
Built to answer the questions that the official `UPGRADE-6.X.md` files leave you guessing at:

- *"Welche CSS-Klasse stylt die Produktbeschreibung in 6.7?"*
- *"Warum sieht meine Storefront nach dem Update auf 6.6 anders aus?"*
- *"Welche Symfony-Services wurden zwischen 6.5 und 6.6 umbenannt?"*
- *"Was muss ich vor dem Update von 6.4.20 auf 6.7.0 anpassen?"*

Everything runs locally on Apple Silicon — no API keys, no cloud, no sending source code anywhere.

## Stack

- **Embeddings:** [Ollama](https://ollama.com) + `nomic-embed-text` (768-dim, ~270 MB)
- **Vector store:** [Qdrant](https://qdrant.tech) in embedded mode (no Docker)
- **MCP:** Python SDK over stdio, registered with Claude Code
- **Language:** Python 3.11, managed via [`uv`](https://docs.astral.sh/uv/) + [`just`](https://github.com/casey/just)
- **Sources:** all stable tags matching `v6.[4567].*.*` from
  [`shopware/shopware`](https://github.com/shopware/shopware) (~163 tags)

## Quickstart

```bash
git clone https://github.com/<you>/shopware-upgrade-intelligence
cd shopware-upgrade-intelligence
just bootstrap                       # installs python@3.11, ollama, uv, just, pulls the model
just pilot-one-tag v6.7.0.0          # ~3–5 min, indexes a single tag
just doctor                          # verifies the stack
```

Register the MCP server with Claude Code:

```bash
claude mcp add shopware-intel \
  -- uv run --project "$PWD" sw-intel-mcp
```

Then ask Claude Code:

> *"Use shopware-intel: how does EntityRepository work in 6.7?"*

## Roadmap

This repo follows an 8-phase plan; see [`docs/`](docs/) for details.

- **Phase 1** — Walking skeleton: single tag, PHP-only, single `search_core` tool ← **you are here**
- **Phase 2** — Multi-area chunking (Twig, SCSS, Vue/TS, XML, Changelog YAML)
- **Phase 3** — Multi-tag pilot (`just pilot` indexes all 6.7.x patches in <20 min)
- **Phase 4** — Symbol index + structural diff between versions
- **Phase 5** — Killer tools: `why_changed`, `find_deprecations`, `find_css_class`
- **Phase 6** — `upgrade_path` synthesis from changelog YAML front-matter
- **Phase 7** — Full ingestion (~163 tags, ~4 h on M-series)
- **Phase 8** — Public launch

## Tools the MCP server will expose (planned)

| Tool | Use it for |
|---|---|
| `search_storefront` | Twig templates, SCSS, Storefront-JS, Storefront-PHP |
| `search_administration` | Vue SFCs, TS/JS, Admin Twig |
| `search_core` | PHP Core APIs for plugin development |
| `search_checkout` | Cross-cut Storefront + Core checkout |
| `search_flow_builder` | Flow Builder triggers and actions |
| `find_css_class` | Where a CSS class is defined, used, what it styles |
| `diff_versions` | Structured diff: added/removed/renamed/deprecated |
| `find_deprecations` | When marked, when removed |
| `why_changed` | Per-file structural diff + linked changelog entries |
| `upgrade_path` | Synthesized upgrade guide from `changelog/release-*/` |

## License

MIT — see [LICENSE](LICENSE).

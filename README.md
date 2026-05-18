# Shopware Upgrade Intelligence

> Ask Claude Code anything about any Shopware 6 version — locally, with structured breaking-change intel.

A local-first **RAG-MCP server** that indexes every stable Shopware 6 release tag from
6.4 onwards and exposes it to [Claude Code](https://claude.com/claude-code) via the
Model Context Protocol. Built to answer the questions that the official `UPGRADE-6.X.md`
files leave you guessing at:

- *"Welche CSS-Klasse stylt die Produktbeschreibung in 6.7?"*
- *"Warum sieht meine Storefront nach dem Update auf 6.6 anders aus?"*
- *"Welche Symfony-Services wurden zwischen 6.5 und 6.6 umbenannt?"*
- *"Was muss ich vor dem Update von 6.4.20 auf 6.7.0 anpassen?"*

Everything runs locally on Apple Silicon — no API keys, no cloud, no sending source
code anywhere.

## Stack

- **Embeddings:** [Ollama](https://ollama.com) + `nomic-embed-text` (768-dim, ~270 MB)
- **Vector store:** [Qdrant](https://qdrant.tech) in embedded mode (no Docker)
- **MCP:** Python SDK over stdio, registered with Claude Code
- **Language:** Python 3.11, managed via [`uv`](https://docs.astral.sh/uv/) +
  [`just`](https://github.com/casey/just)
- **Sources:** all stable tags matching `v6.[4567].*.*` from
  [`shopware/shopware`](https://github.com/shopware/shopware) (~163 tags)

## Quickstart

```bash
git clone https://github.com/vlpmedialtd/shopware-upgrade-intelligence
cd shopware-upgrade-intelligence
just bootstrap                       # installs python@3.11, ollama, uv, just, pulls the model
just pilot-one-tag v6.7.0.0          # ~10 min, indexes a single tag (all 6 collections)
just doctor                          # verifies the stack
```

Register the MCP server with Claude Code:

```bash
claude mcp add shopware-intel -- uv run --project "$PWD" sw-intel-mcp
```

Then ask Claude Code:

> *"Use shopware-intel: how does EntityRepository work in 6.7?"*

## What's indexed per tag

Six Qdrant collections, populated from each Shopware tag in one ingestion pass:

| Collection | Source | Chunker | Purpose |
|---|---|---|---|
| `core` | `src/Core/**/*.{php,xml,yaml}` | PHP class/interface/trait/enum + XML file-level | Framework, DAL, System, Content |
| `storefront` | `src/Storefront/**/*.{php,twig,scss,js}` | PHP + Twig blocks + SCSS class extraction | Templates, theme CSS, JS plugins |
| `administration` | `src/Administration/**/*.{vue,ts,js,twig}` | Vue SFC sections + TS/JS exports + Twig | Admin Vue components, JS plugin API |
| `checkout` | cross-cut Storefront/Checkout + Core/Checkout | language-appropriate | Cart, order, payment flow |
| `flow` | `src/Core/Content/Flow/` + admin `sw-flow` module | language-appropriate | Flow Builder triggers, actions |
| `changes` | `changelog/release-*/*.md` + `UPGRADE-6.X.md` | YAML front-matter + section split | Structured breaking-change data |

Shopware ships `.gitattributes` with `/changelog export-ignore` and `/*.md export-ignore`
— `git archive` strips exactly the upgrade metadata we need. The ingester compensates
by supplementing those files via `git show <tag>:<path>` after the archive is extracted.

## MCP tools

| Tool | What it answers |
|---|---|
| `search_core` | Plugin-dev questions: *how does EntityRepository work?*, *where's the cart calculator?* |
| `search_storefront` | Frontend: *welche CSS-Klasse stylt die Produktbeschreibung?*, *wie greife ich auf das Kategorielisting zu?* |
| `search_administration` | Admin Vue/TS: *wie überschreibe ich das Produkt-Detail-Modul?* |
| `search_checkout` | Cross-cut: *wo wird die Versandkostenberechnung aufgerufen?* |
| `search_flow_builder` | *welche Trigger gibt es für Bestellzustands-Änderungen?* |
| `search_changes` | *was kam neu in 6.7?*, *breaking changes to ArrayEntity* |
| `find_deprecations` | Lists `@deprecated` symbols + their target removal version |
| `find_css_class` | Where a CSS class is defined (SCSS) and used (Twig templates) |
| `why_changed` | Per-file structural diff across versions + linked changelog entries |
| `upgrade_path` | Synthesized upgrade story from version A to version B, grouped by section |

## Roadmap

| Phase | Status |
|---|---|
| 1 — Walking skeleton | ✅ |
| 2 — Multi-area chunkers (PHP, Twig, SCSS, Vue, TS/JS, XML, Markdown, Changelog YAML) | ✅ |
| 3 — Multi-tag orchestrator + state checkpointing | ✅ |
| 4 — Symbol index + `diff_versions` (set-diff of class/method names across tags) | planned |
| 5 — Killer tools (`find_deprecations`, `find_css_class`, `why_changed`) | ✅ |
| 6 — `upgrade_path` synthesis | ✅ |
| 7 — Full ingestion across all ~163 stable 6.4–6.7 tags | runtime-only |
| 8 — Public launch on GitHub | ✅ |

## Why this exists

Shopware upgrades are notoriously painful. Between minor versions, Symfony services get
renamed, Twig blocks get deprecated, CSS classes change, admin JS APIs break. The
official `UPGRADE-6.X.md` files are prose; they're not searchable across versions, can't
answer "where did this CSS class go" or "is this method still safe to use in 6.7", and
contain no structured machine-readable diff. This project turns those files plus the
full source tree into something Claude Code can reason about — locally, repeatably,
under your control.

## License

MIT — see [LICENSE](LICENSE).

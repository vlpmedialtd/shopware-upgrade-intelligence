# Benchmarks

Measured on an Apple Silicon Mac (M-series), local Ollama, embedded Qdrant.

## Phase 1 (PHP-only, walking skeleton)

| Tag | Files (filtered) | Chunks | Wall time |
|---|---|---|---|
| `v6.7.0.0` | 9 496 | 5 277 | ~3 min |

Embedding throughput: ~30 chunks/sec at batch size 64.

## Phase 2 (all chunkers: PHP, Twig, SCSS, Vue, TS/JS, XML, Markdown, Changelog)

| Tag | Files (filtered) | Chunks | Wall time |
|---|---|---|---|
| `v6.7.0.0` | 14 873 | 27 393 | ~11 min |

Of those, 5 378 files were `export-ignored` by Shopware's `.gitattributes` and recovered
via the `git show` supplement (the entire changelog/ tree plus top-level `*.md`).

Collections after Phase 2 (single tag `v6.7.0.0`):

| Collection | Points | Notes |
|---|---:|---|
| `core` | 4 428 | PHP class-level chunks from `src/Core/` |
| `storefront` | 3 083 | PHP + Twig blocks + SCSS class lists |
| `administration` | 11 453 | Vue SFC sections + TS/JS exports + Twig |
| `checkout` | 1 062 | Cross-cut Storefront/Checkout + Core/Checkout |
| `flow` | 479 | Flow Builder triggers/actions |
| `changes` | 6 888 | Changelog YAML-entries + UPGRADE-*.md sections |
| `symbols` | 0 | Populated in Phase 4 |

Embedding throughput: ~85 chunks/sec at batch=64 against local Ollama (M-series).

Query latency: cosine search on the largest collection (`administration`, 11 453 points)
returns in <100 ms p50 including the embed call for the query.

## Phase 3 (Pilot — all 6.7.x patches)

TBD.

## Phase 7 (Full 6.4 → 6.7)

TBD.

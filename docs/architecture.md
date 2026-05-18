# Architecture

```
   ┌────────────────────────────────────────────────────────────┐
   │  git mirror (shopware/shopware --mirror, bare, ~600 MB)    │
   └──────────────────────────┬─────────────────────────────────┘
                              │
                  git archive <tag>  +  git show <tag>:changelog/…
                  (latter compensates for `export-ignore` in
                  Shopware's .gitattributes that strips changelog/)
                              ▼
                  tmp/ sw-intel-<tag>/
                              │
                              ▼
             ┌──────────────────────────────────┐
             │ Area router (areas.py::classify) │
             │ core / storefront / admin /      │
             │ checkout / flow / changes        │
             └──────┬───────────────────────────┘
                    │
       ┌────────────┼────────────────┬────────────────┐
       ▼            ▼                ▼                ▼
   chunk/php   chunk/twig       chunk/vue         chunk/changelog
   chunk/xml   chunk/scss       chunk/ts_js       chunk/markdown
       │            │                │                │
       └────────────┴───────┬────────┴────────────────┘
                            ▼
              Ollama embed (batch=64, async, hard-cap 7000 chars)
                            ▼
         ┌─────────────────────────────────────────┐
         │ Qdrant embedded — 7 collections         │
         │  core | storefront | administration |   │
         │  checkout | flow | changes | symbols    │
         └────────────────────┬────────────────────┘
                              ▼
              MCP Server (stdio) — search_core, search_storefront,
              search_administration, search_checkout,
              search_flow_builder, search_changes
                              ▼
                        Claude Code
```

## Design notes

- **One tag at a time.** A full Shopware tag is ~600 MB on disk; processing one at a
  time keeps the transient disk footprint low. Idempotency comes from blake2s-derived
  point IDs hashed over (tag + file + chunk-index + content).
- **`git archive` plus `git show` supplement.** Shopware's `.gitattributes` declares
  `/changelog` and `/*.md` as `export-ignore`, so a raw `git archive` strips the most
  structured upgrade data. `supplement_export_ignored()` fetches those files via
  `git show <tag>:<path>` and materializes them next to the archive output before
  walking the tree.
- **Chunkers are deliberately regex-based.** A tree-sitter pipeline was considered but
  carries a stability risk on Shopware-specific Twig (`sw_extends`) and Vue SFCs.
  Regex chunkers are fast, dependency-light, and good enough for retrieval; a future
  upgrade can layer tree-sitter on top for symbol extraction.
- **Token budget.** `nomic-embed-text` has a hard 2048-token limit. Chunks are capped
  at 2000 chars (~800 tokens worst case for code) and the embedder defensively
  truncates anything above 7000 chars before sending.

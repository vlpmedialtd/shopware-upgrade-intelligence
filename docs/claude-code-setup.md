# Registering the MCP server with Claude Code

## Recommended: project-local registration

From inside the repo:

```bash
claude mcp add shopware-intel -- uv run --project "$PWD" sw-intel-mcp
```

This adds a `mcpServers.shopware-intel` entry to your Claude Code config and points it
at the project's local `uv` environment. The server is invoked over stdio.

## Manual: edit `~/.claude.json`

If you prefer to wire it up by hand, add to your `~/.claude.json`:

```json
{
  "mcpServers": {
    "shopware-intel": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/Users/<you>/path/to/shopware-upgrade-intelligence",
        "sw-intel-mcp"
      ],
      "env": {
        "SW_INTEL_QDRANT_PATH": "/Users/<you>/Library/Application Support/shopware-intel/qdrant"
      }
    }
  }
}
```

Restart Claude Code afterwards.

## Verifying

Inside a Claude Code session:

```
/mcp shopware-intel
```

Should list the available tools (`search_core`, `search_storefront`, …). Then ask:

> *Use shopware-intel: which Symfony services were renamed in 6.6?*

If the server can't reach Qdrant or Ollama, errors are streamed to stderr — run
`just doctor` to diagnose.

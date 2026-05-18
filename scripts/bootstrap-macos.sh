#!/usr/bin/env bash
set -euo pipefail

echo "==> Homebrew (idempotent) …"
if ! command -v brew >/dev/null 2>&1; then
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
if [ -x /opt/homebrew/bin/brew ]; then eval "$(/opt/homebrew/bin/brew shellenv)"; fi

echo "==> Pakete: python@3.11 ollama uv just …"
brew install python@3.11 ollama uv just

echo "==> Ollama service & Embedding-Modell …"
brew services start ollama || true
sleep 2
ollama pull nomic-embed-text

echo "==> uv sync …"
cd "$(dirname "$0")/.."
uv sync --all-extras

echo "==> Mirror (idempotent) …"
mkdir -p mirrors
if [ ! -d mirrors/platform.git ]; then
  git clone --mirror https://github.com/shopware/shopware.git mirrors/platform.git
else
  (cd mirrors/platform.git && git remote update)
fi

echo "==> Health-Check …"
uv run sw-intel-doctor

echo ""
echo "Fertig. Nächste Schritte:"
echo "  just pilot-one-tag v6.7.0.0   # ~3-5 min, indexiert einen Tag"
echo "  just mcp                       # MCP-Server starten (stdio)"
echo "  just pilot                     # alle 6.7.x Patches (~20 min)"

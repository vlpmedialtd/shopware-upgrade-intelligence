set shell := ["bash", "-cu"]

default:
    @just --list

bootstrap:
    bash scripts/bootstrap-macos.sh

mirror:
    mkdir -p mirrors
    test -d mirrors/platform.git || git clone --mirror https://github.com/shopware/shopware.git mirrors/platform.git
    cd mirrors/platform.git && git remote update

doctor:
    uv run sw-intel-doctor

pilot-one-tag tag="v6.7.0.0":
    uv run sw-intel-ingest run --tag {{tag}}

pilot:
    uv run sw-intel-ingest run --tag-glob 'v6.7.*' --skip-prerelease

ingest-all:
    uv run sw-intel-ingest run --tag-glob 'v6.[4567].*' --skip-prerelease

# Parallel multi-tag ingest. Use OLLAMA_NUM_PARALLEL=N matching --workers.
ingest-parallel workers="4" tag_glob="v6.[4567].*":
    OLLAMA_NUM_PARALLEL={{workers}} uv run sw-intel-parallel-ingest --workers {{workers}} --tag-glob '{{tag_glob}}'

finalize:
    uv run sw-intel-ingest finalize

mcp:
    uv run sw-intel-mcp

query Q:
    uv run sw-intel-query "{{Q}}"

lint:
    uv run ruff check src tests
    uv run ruff format --check src tests

format:
    uv run ruff format src tests

type:
    uv run mypy src

test:
    uv run pytest -q

check: lint type test

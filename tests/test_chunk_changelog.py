from shopware_intel.ingest.chunk.changelog import chunk_changelog

SAMPLE = """---
title: Make user activity tab overarching
issue: NEXT-24983
author: Sebastian Seggewiss
---
# Administration
* Added `sw-inactivity-login` component
* Changed `Module.register` signature to include feature flag

# Core
* Added new config option `shopware.activity.timeout`

# API
* Added new endpoint `/api/_action/activity`
"""


def test_target_version_from_path():
    chunks = chunk_changelog(
        SAMPLE,
        file_path="changelog/release-6-7-2-0/2024-01-01-foo.md",
        area="changes",
    )
    for c in chunks:
        assert c.extra.get("target_version") == "6.7.2.0"


def test_sections_split():
    chunks = chunk_changelog(
        SAMPLE,
        file_path="changelog/release-6-7-2-0/2024-01-01-foo.md",
        area="changes",
    )
    sections = {c.extra.get("section") for c in chunks}
    assert sections == {"administration", "core", "api"}


def test_front_matter_fields_propagated():
    chunks = chunk_changelog(
        SAMPLE,
        file_path="changelog/release-6-7-2-0/2024-01-01-foo.md",
        area="changes",
    )
    for c in chunks:
        assert c.extra.get("issue") == "NEXT-24983"
        assert c.extra.get("author") == "Sebastian Seggewiss"
        assert c.symbol_name == "Make user activity tab overarching"


def test_no_front_matter_still_chunks():
    bare = "# Core\n* Just a body without front matter."
    chunks = chunk_changelog(bare, file_path="changelog/release-6-7-2-0/file.md", area="changes")
    assert chunks
    assert any(c.extra.get("section") == "core" for c in chunks)

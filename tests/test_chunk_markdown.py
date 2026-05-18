from shopware_intel.ingest.chunk.markdown import chunk_upgrade_md

SAMPLE = """# 6.7.2.0

Intro paragraph.

## Removed deprecated services
The service `shopware.foo` was removed. Use `shopware.bar` instead.

## Twig template changes
Block `product_description_outer` renamed to `product_card_description`.

# 6.7.1.0

## Other change
Lorem ipsum.
"""


def test_per_version_sections():
    chunks = chunk_upgrade_md(SAMPLE, file_path="UPGRADE-6.7.md", area="changes")
    versions = {c.extra["target_version"] for c in chunks if "target_version" in c.extra}
    assert versions == {"6.7.2.0", "6.7.1.0"}


def test_subsections_become_chunks():
    chunks = chunk_upgrade_md(SAMPLE, file_path="UPGRADE-6.7.md", area="changes")
    titles = {c.extra["title"] for c in chunks if "title" in c.extra}
    assert "Removed deprecated services" in titles
    assert "Twig template changes" in titles
    assert "Other change" in titles

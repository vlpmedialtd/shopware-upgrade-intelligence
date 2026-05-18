from shopware_intel.retrieval.search import Hit, _dedup_changelog_hits


def _hit(score: float, path: str, name: str, snippet: str) -> Hit:
    return Hit(
        score=score,
        version="6.7.0.0",
        area="changes",
        file_path=path,
        language="markdown",
        symbol_kind="changelog_entry",
        symbol_name=name,
        symbol_fqn="",
        deprecated_in=None,
        start_line=1,
        end_line=10,
        snippet=snippet,
    )


def test_same_entry_indexed_from_two_ingest_tags_collapses():
    hits = [
        _hit(
            0.71,
            "changelog/release-6-5-2-0/foo.md",
            "Update lazy",
            "Update lazy\n\n# Core\n* changed Foo",
        ),
        _hit(
            0.70,
            "changelog/release-6-5-2-0/foo.md",
            "Update lazy",
            "Update lazy\n\n# Core\n* changed Foo",
        ),
    ]
    out = _dedup_changelog_hits(hits)
    assert len(out) == 1
    assert out[0].score == 0.71


def test_different_sections_of_same_entry_are_kept():
    hits = [
        _hit(
            0.71,
            "changelog/release-6-5-2-0/foo.md",
            "Update lazy",
            "Update lazy\n\n# Core\n* core change",
        ),
        _hit(
            0.70,
            "changelog/release-6-5-2-0/foo.md",
            "Update lazy",
            "Update lazy\n\n# Administration\n* admin change",
        ),
    ]
    out = _dedup_changelog_hits(hits)
    assert len(out) == 2


def test_different_entries_in_same_release_are_kept():
    hits = [
        _hit(
            0.71, "changelog/release-6-5-2-0/foo.md", "Update lazy", "Update lazy\n# Core\nchange A"
        ),
        _hit(
            0.70, "changelog/release-6-5-2-0/bar.md", "Other entry", "Other entry\n# Core\nchange B"
        ),
    ]
    out = _dedup_changelog_hits(hits)
    assert len(out) == 2


def test_upgrade_md_entries_unaffected():
    hits = [
        _hit(0.71, "UPGRADE-6.4.md", "6.4.0.0 — Breaking changes", "snippet A"),
        _hit(0.70, "UPGRADE-6.5.md", "6.5.1.0 — ArrayEntity::getVars", "snippet B"),
    ]
    out = _dedup_changelog_hits(hits)
    assert len(out) == 2

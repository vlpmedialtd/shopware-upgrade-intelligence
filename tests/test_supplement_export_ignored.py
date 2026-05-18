"""Regression test for the export-ignore supplement.

Shopware's .gitattributes marks `/changelog` and `/*.md` as `export-ignore`,
so `git archive` strips them. supplement_export_ignored() re-materializes
them via `git show`. This test confirms a known-existing file is restored.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from shopware_intel.config import get_settings
from shopware_intel.ingest.clone import export_tag, supplement_export_ignored

PILOT_TAG = "v6.7.0.0"


@pytest.mark.skipif(
    not (Path(__file__).parent.parent / "mirrors/platform.git" / "HEAD").exists(),
    reason="git mirror not initialized; run `just mirror` first",
)
def test_supplement_restores_upgrade_md():
    settings = get_settings()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        export_tag(settings.mirror_path, PILOT_TAG, tmp_path)
        assert not (tmp_path / "UPGRADE-6.7.md").exists(), \
            "archive should have stripped UPGRADE-6.7.md"
        count = supplement_export_ignored(settings.mirror_path, PILOT_TAG, tmp_path)
        assert count > 0
        assert (tmp_path / "UPGRADE-6.7.md").exists()
        assert (tmp_path / "changelog").exists()
        assert (tmp_path / "changelog").is_dir()

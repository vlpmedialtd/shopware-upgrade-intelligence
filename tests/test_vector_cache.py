import tempfile
from pathlib import Path

from shopware_intel.state import StateStore


def test_cache_roundtrip_preserves_float32_precision():
    with tempfile.TemporaryDirectory() as tmp:
        s = StateStore(Path(tmp) / "state.db")
        v = [0.123456, -0.789, 0.0, 1.5, -2.25]
        s.cache_vectors([("sha1", v)])
        got = s.get_cached_vectors(["sha1"])["sha1"]
        # float32 round-trip — accept ~1e-6 epsilon
        for a, b in zip(v, got, strict=True):
            assert abs(a - b) < 1e-5


def test_cache_miss_returns_no_entry():
    with tempfile.TemporaryDirectory() as tmp:
        s = StateStore(Path(tmp) / "state.db")
        got = s.get_cached_vectors(["nope", "alsonope"])
        assert got == {}


def test_cache_batch_lookup():
    with tempfile.TemporaryDirectory() as tmp:
        s = StateStore(Path(tmp) / "state.db")
        s.cache_vectors([(f"sha{i}", [float(i)] * 4) for i in range(10)])
        got = s.get_cached_vectors([f"sha{i}" for i in range(5)] + ["missing"])
        assert len(got) == 5
        assert "missing" not in got
        assert got["sha0"][0] == 0.0
        assert got["sha4"][0] == 4.0


def test_cache_insert_or_ignore_is_safe():
    """Two writers caching the same sha shouldn't fail; first write wins."""
    with tempfile.TemporaryDirectory() as tmp:
        s = StateStore(Path(tmp) / "state.db")
        s.cache_vectors([("sha", [1.0, 2.0])])
        s.cache_vectors([("sha", [9.0, 9.0])])  # ignored
        assert s.get_cached_vectors(["sha"])["sha"][0] == 1.0


def test_cache_stats():
    with tempfile.TemporaryDirectory() as tmp:
        s = StateStore(Path(tmp) / "state.db")
        s.cache_vectors([("a", [0.0] * 768), ("b", [0.0] * 768)])
        count, total = s.vector_cache_stats()
        assert count == 2
        # 768 float32 = 3072 bytes per vector
        assert total == 2 * 768 * 4

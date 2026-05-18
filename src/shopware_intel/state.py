from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS tag_status (
    tag TEXT PRIMARY KEY,
    sha TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    chunk_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS chunk_index (
    point_id TEXT PRIMARY KEY,
    tag TEXT NOT NULL,
    file_path TEXT NOT NULL,
    content_sha TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunk_tag ON chunk_index(tag);
"""


class StateStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def is_done(self, tag: str) -> bool:
        with self._conn() as c:
            row = c.execute("SELECT 1 FROM tag_status WHERE tag = ?", (tag,)).fetchone()
            return row is not None

    def mark_done(self, tag: str, sha: str, chunk_count: int) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO tag_status (tag, sha, finished_at, chunk_count) VALUES (?, ?, ?, ?)",
                (tag, sha, datetime.now(UTC).isoformat(), chunk_count),
            )

    def has_point(self, point_id: str) -> bool:
        with self._conn() as c:
            row = c.execute("SELECT 1 FROM chunk_index WHERE point_id = ?", (point_id,)).fetchone()
            return row is not None

    def record_point(self, point_id: str, tag: str, file_path: str, content_sha: str) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR IGNORE INTO chunk_index (point_id, tag, file_path, content_sha) VALUES (?, ?, ?, ?)",
                (point_id, tag, file_path, content_sha),
            )

    def known_point_ids(self) -> set[str]:
        with self._conn() as c:
            return {r[0] for r in c.execute("SELECT point_id FROM chunk_index").fetchall()}

    def tag_summary(self) -> list[tuple[str, int, str]]:
        with self._conn() as c:
            return list(
                c.execute(
                    "SELECT tag, chunk_count, finished_at FROM tag_status ORDER BY tag"
                ).fetchall()
            )

"""
SQLite persistence layer for CodeBuster.

Schema
------
scans       – one row per scanning session
files       – one row per discovered source file
comparisons – one row per file pair
"""

import sqlite3
import os
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

DB_FILENAME = "codebuster.db"


# ---------------------------------------------------------------------------
# Row dataclasses (mirrors of DB rows for type safety)
# ---------------------------------------------------------------------------

@dataclass
class ScanRow:
    id: int
    root_dir: str
    filenames: str   # comma-separated list of target filenames
    created_at: str


@dataclass
class FileRow:
    id: int
    scan_id: int
    path: str
    folder: str
    line_count: int
    word_count: int
    char_count: int
    normalized_path: str


@dataclass
class ComparisonRow:
    id: int
    scan_id: int
    file1_id: int
    file2_id: int
    similarity: float


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Public Database class
# ---------------------------------------------------------------------------

class Database:
    def __init__(self, db_dir: str = "."):
        self.path = os.path.join(db_dir, DB_FILENAME)
        self._conn = _connect(self.path)
        self._create_schema()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _create_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS scans (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                root_dir    TEXT    NOT NULL,
                filenames   TEXT    NOT NULL,
                created_at  TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS files (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id         INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
                path            TEXT    NOT NULL,
                folder          TEXT    NOT NULL,
                line_count      INTEGER NOT NULL DEFAULT 0,
                word_count      INTEGER NOT NULL DEFAULT 0,
                char_count      INTEGER NOT NULL DEFAULT 0,
                normalized_path TEXT    NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS comparisons (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id     INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
                file1_id    INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
                file2_id    INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
                similarity  REAL    NOT NULL
            );
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Scans
    # ------------------------------------------------------------------

    def insert_scan(self, root_dir: str, filenames: list[str]) -> int:
        cur = self._conn.execute(
            "INSERT INTO scans (root_dir, filenames, created_at) VALUES (?, ?, ?)",
            (root_dir, ",".join(filenames), datetime.now().isoformat(timespec="seconds")),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def get_all_scans(self) -> list[ScanRow]:
        rows = self._conn.execute("SELECT * FROM scans ORDER BY id DESC").fetchall()
        return [ScanRow(**dict(r)) for r in rows]

    def get_scan(self, scan_id: int) -> Optional[ScanRow]:
        row = self._conn.execute("SELECT * FROM scans WHERE id=?", (scan_id,)).fetchone()
        return ScanRow(**dict(row)) if row else None

    def delete_scan(self, scan_id: int) -> None:
        self._conn.execute("DELETE FROM scans WHERE id=?", (scan_id,))
        self._conn.commit()

    def get_latest_scan(self) -> Optional[ScanRow]:
        row = self._conn.execute(
            "SELECT * FROM scans ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return ScanRow(**dict(row)) if row else None

    # ------------------------------------------------------------------
    # Files
    # ------------------------------------------------------------------

    def insert_file(
        self,
        scan_id: int,
        path: str,
        folder: str,
        line_count: int,
        word_count: int,
        char_count: int,
        normalized_path: str,
    ) -> int:
        cur = self._conn.execute(
            """INSERT INTO files
               (scan_id, path, folder, line_count, word_count, char_count, normalized_path)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (scan_id, path, folder, line_count, word_count, char_count, normalized_path),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def get_files_for_scan(self, scan_id: int) -> list[FileRow]:
        rows = self._conn.execute(
            "SELECT * FROM files WHERE scan_id=? ORDER BY id", (scan_id,)
        ).fetchall()
        return [FileRow(**dict(r)) for r in rows]

    def get_file(self, file_id: int) -> Optional[FileRow]:
        row = self._conn.execute("SELECT * FROM files WHERE id=?", (file_id,)).fetchone()
        return FileRow(**dict(row)) if row else None

    # ------------------------------------------------------------------
    # Comparisons
    # ------------------------------------------------------------------

    def insert_comparison(
        self, scan_id: int, file1_id: int, file2_id: int, similarity: float
    ) -> int:
        cur = self._conn.execute(
            "INSERT INTO comparisons (scan_id, file1_id, file2_id, similarity) VALUES (?, ?, ?, ?)",
            (scan_id, file1_id, file2_id, similarity),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def get_comparisons_for_scan(self, scan_id: int) -> list[ComparisonRow]:
        rows = self._conn.execute(
            "SELECT * FROM comparisons WHERE scan_id=? ORDER BY similarity DESC",
            (scan_id,),
        ).fetchall()
        return [ComparisonRow(**dict(r)) for r in rows]

    # ------------------------------------------------------------------
    # Statistics helpers (all computed in SQL for efficiency)
    # ------------------------------------------------------------------

    def get_similarity_stats(self, scan_id: int) -> dict:
        row = self._conn.execute(
            """SELECT
                COUNT(*)        AS pair_count,
                AVG(similarity) AS mean,
                MIN(similarity) AS minimum,
                MAX(similarity) AS maximum
               FROM comparisons WHERE scan_id=?""",
            (scan_id,),
        ).fetchone()
        stats = dict(row) if row else {}

        # Median via sorting
        sims = [
            r[0]
            for r in self._conn.execute(
                "SELECT similarity FROM comparisons WHERE scan_id=? ORDER BY similarity",
                (scan_id,),
            ).fetchall()
        ]
        n = len(sims)
        if n == 0:
            stats["median"] = None
        elif n % 2 == 1:
            stats["median"] = sims[n // 2]
        else:
            stats["median"] = (sims[n // 2 - 1] + sims[n // 2]) / 2.0

        return stats

    def get_file_stats(self, scan_id: int) -> dict:
        row = self._conn.execute(
            """SELECT
                COUNT(*)         AS file_count,
                AVG(line_count)  AS avg_lines,
                AVG(word_count)  AS avg_words,
                AVG(char_count)  AS avg_chars,
                SUM(line_count)  AS total_lines
               FROM files WHERE scan_id=?""",
            (scan_id,),
        ).fetchone()
        return dict(row) if row else {}

    def count_pairs_above_threshold(self, scan_id: int, threshold: float) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM comparisons WHERE scan_id=? AND similarity>=?",
            (scan_id, threshold),
        ).fetchone()
        return row[0] if row else 0

    def get_similarity_histogram(self, scan_id: int, buckets: int = 10) -> list[tuple[str, int]]:
        """Return (label, count) tuples for a histogram with `buckets` equal-width bins."""
        sims = [
            r[0]
            for r in self._conn.execute(
                "SELECT similarity FROM comparisons WHERE scan_id=?", (scan_id,)
            ).fetchall()
        ]
        if not sims:
            return []

        step = 1.0 / buckets
        counts = [0] * buckets
        for s in sims:
            idx = min(int(s / step), buckets - 1)
            counts[idx] += 1

        return [
            (f"{int(i * step * 100)}–{int((i + 1) * step * 100)}%", counts[i])
            for i in range(buckets)
        ]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._conn.close()

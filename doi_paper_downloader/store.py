"""store.py - SQLite log of what happened to each DOI.

One row per DOI (case-insensitive) with its latest status: ``pending``,
``downloaded``, ``timeout``, ``rate_limited`` or ``error``. The table is
what lets an interrupted batch resume and what feeds the CSV report.
"""

import csv
import sqlite3
from pathlib import Path
from typing import Dict, Optional

_COLUMNS = ("doi", "status", "filename", "message", "updated_at")


class DownloadStore:
    """Context manager around the SQLite database."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._conn = sqlite3.connect(self.path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS papers (
                doi TEXT PRIMARY KEY COLLATE NOCASE,
                status TEXT NOT NULL,
                filename TEXT,
                message TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self._conn.commit()

    def __enter__(self) -> "DownloadStore":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def close(self) -> None:
        self._conn.close()

    def status(self, doi: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT status FROM papers WHERE lower(doi) = lower(?)", (doi,)
        ).fetchone()
        return row[0] if row else None

    def record(self, doi: str, status: str, filename: Optional[str] = None,
               message: Optional[str] = None) -> None:
        self._conn.execute(
            """
            INSERT INTO papers (doi, status, filename, message, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(doi) DO UPDATE SET
                status = excluded.status,
                filename = excluded.filename,
                message = excluded.message,
                updated_at = CURRENT_TIMESTAMP
            """,
            (doi, status, filename, message),
        )
        self._conn.commit()

    def counts(self) -> Dict[str, int]:
        rows = self._conn.execute(
            "SELECT status, COUNT(*) FROM papers GROUP BY status"
        ).fetchall()
        return dict(rows)

    def export_csv(self, path: Path) -> None:
        rows = self._conn.execute(
            f"SELECT {', '.join(_COLUMNS)} FROM papers ORDER BY updated_at, doi"
        ).fetchall()
        with Path(path).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(_COLUMNS)
            writer.writerows(rows)

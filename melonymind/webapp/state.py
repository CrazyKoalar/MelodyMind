"""SQLite repository for annotation state."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, List, Optional


SCHEMA_VERSION = "1"

STATUS_NEW = "new"
STATUS_OPENED = "opened"
STATUS_STEM_PICKED = "stem_picked"
STATUS_NOTES_EDITED = "notes_edited"
STATUS_CONFIRMED = "confirmed"

VALID_STATUSES = {
    STATUS_NEW,
    STATUS_OPENED,
    STATUS_STEM_PICKED,
    STATUS_NOTES_EDITED,
    STATUS_CONFIRMED,
}

NOTES_SOURCE_EXTRACTED = "extracted"
NOTES_SOURCE_EDITED = "edited"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS songs (
    id                TEXT PRIMARY KEY,
    audio_path        TEXT NOT NULL UNIQUE,
    relpath           TEXT NOT NULL,
    source_mtime_ns   INTEGER NOT NULL,
    source_size       INTEGER NOT NULL,
    duration_sec      REAL,
    status            TEXT NOT NULL DEFAULT 'new',
    picked_stem       TEXT,
    candidate_scores  TEXT,
    cache_ready       INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL,
    last_modified     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_songs_status ON songs(status);

CREATE TABLE IF NOT EXISTS song_notes (
    song_id    TEXT NOT NULL,
    stem       TEXT NOT NULL,
    notes_json TEXT NOT NULL,
    source     TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (song_id, stem),
    FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SongRow:
    id: str
    audio_path: str
    relpath: str
    source_mtime_ns: int
    source_size: int
    duration_sec: Optional[float]
    status: str
    picked_stem: Optional[str]
    candidate_scores: dict = field(default_factory=dict)
    cache_ready: bool = False
    created_at: str = ""
    last_modified: str = ""


@dataclass
class NotesRow:
    song_id: str
    stem: str
    notes: list
    source: str
    updated_at: str


class StateRepo:
    """Thin SQLite wrapper. One repo per request; connection is local."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, isolation_level=None, timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
        finally:
            conn.close()

    def initialize(self, dataset_root: str | Path) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            self._set_meta(conn, "schema_version", SCHEMA_VERSION)
            self._set_meta(conn, "dataset_root", str(Path(dataset_root).resolve()))
            if not self._get_meta(conn, "created_at"):
                self._set_meta(conn, "created_at", _now_iso())

    @staticmethod
    def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
        conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    @staticmethod
    def _get_meta(conn: sqlite3.Connection, key: str) -> Optional[str]:
        row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def upsert_song(self, song: SongRow) -> None:
        if song.status not in VALID_STATUSES:
            raise ValueError(f"invalid status: {song.status!r}")
        now = _now_iso()
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT created_at FROM songs WHERE id=?", (song.id,)
            ).fetchone()
            created_at = existing["created_at"] if existing else (song.created_at or now)
            conn.execute(
                """
                INSERT INTO songs(
                    id, audio_path, relpath, source_mtime_ns, source_size,
                    duration_sec, status, picked_stem, candidate_scores,
                    cache_ready, created_at, last_modified
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    audio_path=excluded.audio_path,
                    relpath=excluded.relpath,
                    source_mtime_ns=excluded.source_mtime_ns,
                    source_size=excluded.source_size,
                    duration_sec=excluded.duration_sec,
                    status=excluded.status,
                    picked_stem=excluded.picked_stem,
                    candidate_scores=excluded.candidate_scores,
                    cache_ready=excluded.cache_ready,
                    last_modified=excluded.last_modified
                """,
                (
                    song.id,
                    song.audio_path,
                    song.relpath,
                    song.source_mtime_ns,
                    song.source_size,
                    song.duration_sec,
                    song.status,
                    song.picked_stem,
                    json.dumps(song.candidate_scores, sort_keys=True),
                    1 if song.cache_ready else 0,
                    created_at,
                    now,
                ),
            )

    def get_song(self, song_id: str) -> Optional[SongRow]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM songs WHERE id=?", (song_id,)).fetchone()
            return _row_to_song(row) if row else None

    def get_song_by_audio_path(self, audio_path: str) -> Optional[SongRow]:
        abs_path = str(Path(audio_path).resolve())
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM songs WHERE audio_path=?",
                (abs_path,),
            ).fetchone()
            return _row_to_song(row) if row else None

    def list_songs(self) -> List[SongRow]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM songs ORDER BY relpath").fetchall()
            return [_row_to_song(row) for row in rows]

    def list_songs_by_status(self, statuses: Iterable[str]) -> List[SongRow]:
        statuses_list = list(statuses)
        if not statuses_list:
            return []
        placeholders = ",".join("?" * len(statuses_list))
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM songs WHERE status IN ({placeholders}) ORDER BY relpath",
                statuses_list,
            ).fetchall()
            return [_row_to_song(row) for row in rows]

    def update_status(self, song_id: str, status: str, picked_stem: Optional[str] = None) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid status: {status!r}")
        now = _now_iso()
        with self.connect() as conn:
            if picked_stem is None:
                conn.execute(
                    "UPDATE songs SET status=?, last_modified=? WHERE id=?",
                    (status, now, song_id),
                )
            else:
                conn.execute(
                    "UPDATE songs SET status=?, picked_stem=?, last_modified=? WHERE id=?",
                    (status, picked_stem, now, song_id),
                )

    def mark_cache_ready(
        self,
        song_id: str,
        candidate_scores: dict,
        suggested_stem: str,
    ) -> None:
        now = _now_iso()
        with self.connect() as conn:
            conn.execute(
                "UPDATE songs SET cache_ready=1, candidate_scores=?, "
                "picked_stem=COALESCE(picked_stem, ?), "
                "status=CASE WHEN status='new' THEN 'opened' ELSE status END, "
                "last_modified=? WHERE id=?",
                (
                    json.dumps(candidate_scores, sort_keys=True),
                    suggested_stem,
                    now,
                    song_id,
                ),
            )

    def upsert_notes(
        self,
        song_id: str,
        stem: str,
        notes: list,
        source: str = NOTES_SOURCE_EXTRACTED,
    ) -> None:
        if source not in (NOTES_SOURCE_EXTRACTED, NOTES_SOURCE_EDITED):
            raise ValueError(f"invalid notes source: {source!r}")
        now = _now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO song_notes(song_id, stem, notes_json, source, updated_at)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(song_id, stem) DO UPDATE SET
                    notes_json=excluded.notes_json,
                    source=excluded.source,
                    updated_at=excluded.updated_at
                """,
                (song_id, stem, json.dumps(notes), source, now),
            )

    def get_notes(self, song_id: str, stem: str) -> Optional[NotesRow]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM song_notes WHERE song_id=? AND stem=?",
                (song_id, stem),
            ).fetchone()
            if not row:
                return None
            return NotesRow(
                song_id=row["song_id"],
                stem=row["stem"],
                notes=json.loads(row["notes_json"]),
                source=row["source"],
                updated_at=row["updated_at"],
            )


def _row_to_song(row: sqlite3.Row) -> SongRow:
    return SongRow(
        id=row["id"],
        audio_path=row["audio_path"],
        relpath=row["relpath"],
        source_mtime_ns=row["source_mtime_ns"],
        source_size=row["source_size"],
        duration_sec=row["duration_sec"],
        status=row["status"],
        picked_stem=row["picked_stem"],
        candidate_scores=json.loads(row["candidate_scores"]) if row["candidate_scores"] else {},
        cache_ready=bool(row["cache_ready"]),
        created_at=row["created_at"],
        last_modified=row["last_modified"],
    )

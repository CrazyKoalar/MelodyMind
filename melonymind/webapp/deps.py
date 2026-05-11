"""FastAPI dependency functions and discovery helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, List

from fastapi import HTTPException, Request

from .config import AppConfig, SUPPORTED_AUDIO_EXTENSIONS
from .hashing import song_hash
from .state import SongRow, StateRepo, STATUS_NEW


def get_config(request: Request) -> AppConfig:
    return request.app.state.config


def get_repo(request: Request) -> StateRepo:
    config: AppConfig = request.app.state.config
    return StateRepo(config.db_path)


def scan_dataset(dataset_dir: Path) -> List[Path]:
    return sorted(
        path
        for path in dataset_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS
    )


def sync_dataset_into_repo(config: AppConfig, repo: StateRepo) -> List[SongRow]:
    """Walk the dataset directory and upsert new files into the songs table."""
    audio_paths = scan_dataset(config.dataset_dir)
    existing = {row.audio_path: row for row in repo.list_songs()}
    rows: List[SongRow] = []
    for path in audio_paths:
        abs_path = str(path.resolve())
        song_id = song_hash(path)
        stat = path.stat()

        old = existing.get(abs_path)
        if old and old.id == song_id:
            rows.append(old)
            continue

        relpath = str(path.relative_to(config.dataset_dir))
        new_row = SongRow(
            id=song_id,
            audio_path=abs_path,
            relpath=relpath,
            source_mtime_ns=stat.st_mtime_ns,
            source_size=stat.st_size,
            duration_sec=old.duration_sec if old else None,
            status=old.status if old and old.id == song_id else STATUS_NEW,
            picked_stem=old.picked_stem if old and old.id == song_id else None,
            candidate_scores=old.candidate_scores if old and old.id == song_id else {},
            cache_ready=bool(old.cache_ready) if old and old.id == song_id else False,
        )
        repo.upsert_song(new_row)
        rows.append(new_row)

    rows.sort(key=lambda r: r.relpath)
    return rows


def require_song(repo: StateRepo, song_id: str) -> SongRow:
    song = repo.get_song(song_id)
    if song is None:
        raise HTTPException(status_code=404, detail=f"unknown song id: {song_id}")
    return song


def iter_repos(config: AppConfig) -> Iterator[StateRepo]:
    yield StateRepo(config.db_path)

"""Routes for song catalog and per-song annotation state."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Request, UploadFile

from . import cache as cache_mod
from .config import STEM_NAMES, AppConfig, SUPPORTED_AUDIO_EXTENSIONS
from .deps import get_config, get_repo, require_song, sync_dataset_into_repo
from .pipeline import compute_song, computation_to_cache_payloads
from .state import (
    NOTES_SOURCE_EXTRACTED,
    STATUS_CONFIRMED,
    STATUS_OPENED,
    STATUS_STEM_PICKED,
    SongRow,
    StateRepo,
)

router = APIRouter(prefix="/api")


def _safe_upload_basename(filename: str) -> str:
    base = Path(filename).name
    if not base or base in (".", ".."):
        return "upload.wav"
    safe = re.sub(r"[^\w.\-]", "_", base)
    if not safe.strip("_"):
        return "upload.wav"
    return safe[:200]


def compute_song_internal(
    song_id: str,
    force: bool,
    request: Request,
    config: AppConfig,
    repo: StateRepo,
) -> Dict[str, Any]:
    """Run separation + pitch for one song; shared by /compute and /upload."""
    song = require_song(repo, song_id)

    if song.cache_ready and not force:
        suggested = (
            max(song.candidate_scores, key=song.candidate_scores.get)
            if song.candidate_scores
            else "mix"
        )
        return {
            "stems": list(STEM_NAMES),
            "candidate_scores": song.candidate_scores,
            "suggested_stem": suggested,
            "cached": True,
        }

    processor = getattr(request.app.state, "test_processor", None)
    detector = getattr(request.app.state, "test_detector", None)
    comp = compute_song(
        song.audio_path,
        song_id,
        config,
        processor=processor,
        detector=detector,
    )

    for stem_name in STEM_NAMES:
        stem = comp.stems[stem_name]
        cache_mod.write_stem_wav(
            config.songs_cache_dir, song_id, stem_name, stem.audio, comp.sr
        )
    note_payloads = computation_to_cache_payloads(comp)
    for stem_name, payload in note_payloads.items():
        cache_mod.write_notes_json(config.songs_cache_dir, song_id, stem_name, payload)
        repo.upsert_notes(song_id, stem_name, payload, source=NOTES_SOURCE_EXTRACTED)

    suggested = comp.selection.stem_name if comp.selection else "mix"
    cache_mod.write_source_meta(
        config.songs_cache_dir,
        song_id,
        audio_path=song.audio_path,
        sr=comp.sr,
        duration_sec=comp.duration_sec,
        candidate_scores=comp.selection.stem_scores if comp.selection else {},
        suggested_stem=suggested,
    )

    refreshed = SongRow(
        id=song.id,
        audio_path=song.audio_path,
        relpath=song.relpath,
        source_mtime_ns=song.source_mtime_ns,
        source_size=song.source_size,
        duration_sec=comp.duration_sec,
        status=STATUS_OPENED if song.status == "new" else song.status,
        picked_stem=song.picked_stem,
        candidate_scores=comp.selection.stem_scores if comp.selection else {},
        cache_ready=True,
    )
    repo.upsert_song(refreshed)

    return {
        "stems": list(STEM_NAMES),
        "candidate_scores": refreshed.candidate_scores,
        "suggested_stem": suggested,
        "cached": False,
    }


def _song_to_dict(song: SongRow, *, detailed: bool = False) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "id": song.id,
        "relpath": song.relpath,
        "filename": song.relpath.rsplit("/", 1)[-1].rsplit("\\", 1)[-1],
        "status": song.status,
        "picked_stem": song.picked_stem,
        "duration_sec": song.duration_sec,
        "last_modified": song.last_modified,
        "cache_ready": song.cache_ready,
    }
    if detailed:
        base["audio_path"] = song.audio_path
        base["candidate_scores"] = song.candidate_scores
        base["stems"] = list(STEM_NAMES)
    return base


@router.get("/songs")
def list_songs(
    config: AppConfig = Depends(get_config),
    repo: StateRepo = Depends(get_repo),
) -> Dict[str, Any]:
    repo.initialize(config.dataset_dir)
    rows = sync_dataset_into_repo(config, repo)
    return {"songs": [_song_to_dict(row) for row in rows]}


@router.get("/songs/{song_id}")
def get_song_detail(
    song_id: str,
    repo: StateRepo = Depends(get_repo),
) -> Dict[str, Any]:
    song = require_song(repo, song_id)
    return _song_to_dict(song, detailed=True)


@router.post("/songs/upload")
async def upload_song(
    request: Request,
    file: UploadFile = File(...),
    auto_compute: bool = Form(False),
    config: AppConfig = Depends(get_config),
    repo: StateRepo = Depends(get_repo),
) -> Dict[str, Any]:
    """Save an audio file under dataset/uploads and register it like a dataset scan."""
    config.ensure_dirs()
    safe_name = _safe_upload_basename(file.filename or "upload.wav")
    suffix = Path(safe_name).suffix.lower()
    if suffix not in SUPPORTED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported audio type {suffix!r}; allowed: {sorted(SUPPORTED_AUDIO_EXTENSIONS)}",
        )

    uploads_dir = config.dataset_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    dest = uploads_dir / f"{int(time.time() * 1000)}_{safe_name}"
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    dest.write_bytes(data)

    repo.initialize(config.dataset_dir)
    sync_dataset_into_repo(config, repo)

    abs_path = str(dest.resolve())
    song_row = repo.get_song_by_audio_path(abs_path)
    if song_row is None:
        raise HTTPException(status_code=500, detail="upload saved but song row missing")

    compute_result = None
    if auto_compute:
        compute_result = compute_song_internal(
            song_row.id, False, request, config, repo
        )

    song_row = require_song(repo, song_row.id)
    return {
        "song": _song_to_dict(song_row, detailed=True),
        "compute": compute_result,
    }


@router.post("/songs/{song_id}/compute")
def compute_song_endpoint(
    song_id: str,
    request: Request,
    body: Optional[Dict[str, Any]] = Body(default=None),
    config: AppConfig = Depends(get_config),
    repo: StateRepo = Depends(get_repo),
) -> Dict[str, Any]:
    force = bool((body or {}).get("force", False))
    return compute_song_internal(song_id, force, request, config, repo)


@router.post("/songs/{song_id}/stem")
def set_stem(
    song_id: str,
    body: Dict[str, Any] = Body(...),
    repo: StateRepo = Depends(get_repo),
) -> Dict[str, Any]:
    require_song(repo, song_id)
    stem = body.get("stem")
    if stem not in STEM_NAMES:
        raise HTTPException(status_code=400, detail=f"invalid stem: {stem!r}")
    repo.update_status(song_id, STATUS_STEM_PICKED, picked_stem=stem)
    return {"status": STATUS_STEM_PICKED, "picked_stem": stem}


@router.post("/songs/{song_id}/confirm")
def confirm_song(
    song_id: str,
    repo: StateRepo = Depends(get_repo),
) -> Dict[str, Any]:
    song = require_song(repo, song_id)
    if not song.picked_stem:
        raise HTTPException(
            status_code=400, detail="cannot confirm before picking a stem"
        )
    repo.update_status(song_id, STATUS_CONFIRMED)
    return {"status": STATUS_CONFIRMED}


@router.post("/songs/{song_id}/reopen")
def reopen_song(
    song_id: str,
    repo: StateRepo = Depends(get_repo),
) -> Dict[str, Any]:
    song = require_song(repo, song_id)
    new_status = STATUS_STEM_PICKED if song.picked_stem else STATUS_OPENED
    repo.update_status(song_id, new_status)
    return {"status": new_status}

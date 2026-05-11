"""Routes for melody-note GET / PUT / re-extract."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import soundfile as sf
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from . import cache as cache_mod
from .config import STEM_NAMES, AppConfig
from .deps import get_config, get_repo, require_song
from .pipeline import reextract_notes_for_stem
from .serializers import notes_to_payload
from .state import (
    NOTES_SOURCE_EDITED,
    NOTES_SOURCE_EXTRACTED,
    STATUS_NOTES_EDITED,
    StateRepo,
)

router = APIRouter(prefix="/api")


def _resolve_stem(stem: Optional[str], picked_stem: Optional[str]) -> str:
    """Default to the song's picked stem if none specified."""
    resolved = stem or picked_stem
    if not resolved:
        raise HTTPException(
            status_code=400,
            detail="no stem specified and song has no picked_stem yet",
        )
    if resolved not in STEM_NAMES:
        raise HTTPException(status_code=400, detail=f"invalid stem: {resolved!r}")
    return resolved


def _notes_payload(notes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ensure each note has an id (stable across re-fetch within one session)."""
    out = []
    for index, note in enumerate(notes):
        item = dict(note)
        item.setdefault("id", index)
        out.append(item)
    return out


def fetch_notes_payload(
    song_id: str,
    request: Request,
    config: AppConfig,
    repo: StateRepo,
    stem: Optional[str] = None,
) -> Dict[str, Any]:
    """Return the same payload as GET /notes (DB, cache, or on-demand extract)."""
    song = require_song(repo, song_id)
    resolved_stem = _resolve_stem(stem, song.picked_stem)

    row = repo.get_notes(song_id, resolved_stem)
    if row is not None:
        return {
            "stem": resolved_stem,
            "sr": config.sample_rate,
            "notes": _notes_payload(row.notes),
            "source": row.source,
        }

    cached = cache_mod.read_notes_json(config.songs_cache_dir, song_id, resolved_stem)
    if cached is not None:
        return {
            "stem": resolved_stem,
            "sr": config.sample_rate,
            "notes": _notes_payload(cached),
            "source": NOTES_SOURCE_EXTRACTED,
        }

    # Auto-extract on demand from the cached stem WAV. This covers the case
    # where the user picks a non-suggested stem — compute only eagerly extracts
    # notes for the suggested stem.
    stem_path = cache_mod.stem_wav_path(config.songs_cache_dir, song_id, resolved_stem)
    if not stem_path.exists():
        raise HTTPException(
            status_code=409,
            detail="stem audio not cached; run /compute first",
        )
    audio, sr = sf.read(stem_path)
    detector = getattr(request.app.state, "test_detector", None)
    notes = reextract_notes_for_stem(
        audio, sr, detector=detector, min_confidence=config.min_confidence
    )
    payload = notes_to_payload(notes)
    repo.upsert_notes(song_id, resolved_stem, payload, source=NOTES_SOURCE_EXTRACTED)
    cache_mod.write_notes_json(config.songs_cache_dir, song_id, resolved_stem, payload)
    return {
        "stem": resolved_stem,
        "sr": sr,
        "notes": payload,
        "source": NOTES_SOURCE_EXTRACTED,
    }


@router.get("/songs/{song_id}/notes")
def get_notes(
    song_id: str,
    request: Request,
    stem: Optional[str] = Query(default=None),
    config: AppConfig = Depends(get_config),
    repo: StateRepo = Depends(get_repo),
) -> Dict[str, Any]:
    return fetch_notes_payload(song_id, request, config, repo, stem=stem)


@router.put("/songs/{song_id}/notes")
def put_notes(
    song_id: str,
    body: Dict[str, Any] = Body(...),
    config: AppConfig = Depends(get_config),
    repo: StateRepo = Depends(get_repo),
) -> Dict[str, Any]:
    song = require_song(repo, song_id)
    resolved_stem = _resolve_stem(body.get("stem"), song.picked_stem)
    notes = body.get("notes")
    if not isinstance(notes, list):
        raise HTTPException(status_code=400, detail="`notes` must be an array")

    normalized = _notes_payload(notes)
    repo.upsert_notes(song_id, resolved_stem, normalized, source=NOTES_SOURCE_EDITED)
    cache_mod.write_notes_json(config.songs_cache_dir, song_id, resolved_stem, normalized)

    # Promote status to notes_edited only if we're past stem_picked.
    if song.status in ("stem_picked",):
        repo.update_status(song_id, STATUS_NOTES_EDITED)

    return {
        "status": STATUS_NOTES_EDITED if song.status == "stem_picked" else song.status,
        "count": len(normalized),
        "stem": resolved_stem,
    }


@router.post("/songs/{song_id}/notes/reextract")
def reextract_notes(
    song_id: str,
    request: Request,
    body: Optional[Dict[str, Any]] = Body(default=None),
    config: AppConfig = Depends(get_config),
    repo: StateRepo = Depends(get_repo),
) -> Dict[str, Any]:
    song = require_song(repo, song_id)
    resolved_stem = _resolve_stem(
        (body or {}).get("stem"), song.picked_stem
    )

    stem_path = cache_mod.stem_wav_path(config.songs_cache_dir, song_id, resolved_stem)
    if not stem_path.exists():
        raise HTTPException(
            status_code=409,
            detail="stem audio not cached; run /compute first",
        )

    audio, sr = sf.read(stem_path)
    detector = getattr(request.app.state, "test_detector", None)
    notes = reextract_notes_for_stem(
        audio, sr, detector=detector, min_confidence=config.min_confidence
    )
    payload = notes_to_payload(notes)

    repo.upsert_notes(song_id, resolved_stem, payload, source=NOTES_SOURCE_EXTRACTED)
    cache_mod.write_notes_json(config.songs_cache_dir, song_id, resolved_stem, payload)

    return {
        "stem": resolved_stem,
        "sr": sr,
        "notes": payload,
        "source": NOTES_SOURCE_EXTRACTED,
    }

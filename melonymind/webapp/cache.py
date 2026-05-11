"""Disk cache for stem WAVs and extracted notes.

Layout under {state.songs_cache_dir}/{song_id}/:
  source_meta.json
  stems/<stem_name>.wav
  notes/<stem_name>.json
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, List, Optional

import numpy as np
import soundfile as sf


def song_cache_dir(songs_cache_root: Path, song_id: str) -> Path:
    return Path(songs_cache_root) / song_id


def stems_dir(songs_cache_root: Path, song_id: str) -> Path:
    return song_cache_dir(songs_cache_root, song_id) / "stems"


def notes_dir(songs_cache_root: Path, song_id: str) -> Path:
    return song_cache_dir(songs_cache_root, song_id) / "notes"


def stem_wav_path(songs_cache_root: Path, song_id: str, stem_name: str) -> Path:
    return stems_dir(songs_cache_root, song_id) / f"{stem_name}.wav"


def notes_json_path(songs_cache_root: Path, song_id: str, stem_name: str) -> Path:
    return notes_dir(songs_cache_root, song_id) / f"{stem_name}.json"


def source_meta_path(songs_cache_root: Path, song_id: str) -> Path:
    return song_cache_dir(songs_cache_root, song_id) / "source_meta.json"


def ensure_song_cache_dir(songs_cache_root: Path, song_id: str) -> None:
    stems_dir(songs_cache_root, song_id).mkdir(parents=True, exist_ok=True)
    notes_dir(songs_cache_root, song_id).mkdir(parents=True, exist_ok=True)


def write_stem_wav(
    songs_cache_root: Path,
    song_id: str,
    stem_name: str,
    audio: np.ndarray,
    sr: int,
) -> Path:
    """Atomically write a stem WAV to the cache directory."""
    ensure_song_cache_dir(songs_cache_root, song_id)
    final = stem_wav_path(songs_cache_root, song_id, stem_name)
    tmp = final.with_suffix(final.suffix + ".tmp")
    sf.write(tmp, audio, sr, subtype="PCM_16", format="WAV")
    os.replace(tmp, final)
    return final


def write_notes_json(
    songs_cache_root: Path,
    song_id: str,
    stem_name: str,
    notes_payload: List[dict],
) -> Path:
    ensure_song_cache_dir(songs_cache_root, song_id)
    final = notes_json_path(songs_cache_root, song_id, stem_name)
    tmp = final.with_suffix(final.suffix + ".tmp")
    tmp.write_text(json.dumps(notes_payload), encoding="utf-8")
    os.replace(tmp, final)
    return final


def read_notes_json(
    songs_cache_root: Path, song_id: str, stem_name: str
) -> Optional[List[dict]]:
    path = notes_json_path(songs_cache_root, song_id, stem_name)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_source_meta(
    songs_cache_root: Path,
    song_id: str,
    audio_path: str,
    sr: int,
    duration_sec: float,
    candidate_scores: dict,
    suggested_stem: str,
) -> Path:
    ensure_song_cache_dir(songs_cache_root, song_id)
    payload = {
        "song_id": song_id,
        "audio_path": str(audio_path),
        "sample_rate": int(sr),
        "duration_sec": float(duration_sec),
        "candidate_scores": candidate_scores,
        "suggested_stem": suggested_stem,
    }
    final = source_meta_path(songs_cache_root, song_id)
    tmp = final.with_suffix(final.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    os.replace(tmp, final)
    return final


def stem_wavs_present(
    songs_cache_root: Path, song_id: str, stem_names: Iterable[str]
) -> bool:
    return all(
        stem_wav_path(songs_cache_root, song_id, name).exists() for name in stem_names
    )

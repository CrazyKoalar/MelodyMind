"""Tests for the compute_song pipeline + disk cache layout."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from melonymind.core.pitch_detector import NoteEvent
from melonymind.webapp import cache as cache_mod
from melonymind.webapp.config import AppConfig
from melonymind.webapp.pipeline import (
    SongComputation,
    compute_song,
    computation_to_cache_payloads,
    reextract_notes_for_stem,
)


class DummyDetector:
    """Return predefined notes regardless of input — keeps tests fast."""

    def detect(self, audio, sr: int, min_confidence: float = 0.5):
        return [
            NoteEvent(pitch=67.0, start_time=0.0, end_time=0.5, confidence=0.9),
            NoteEvent(pitch=69.0, start_time=0.5, end_time=1.0, confidence=0.85),
        ]


def _make_wav(path: Path, sr: int = 22050, seconds: float = 1.0) -> None:
    t = np.linspace(0.0, seconds, int(sr * seconds), endpoint=False)
    sine = 0.5 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
    sf.write(path, sine, sr)


def _make_config(local_tmp_path: Path) -> AppConfig:
    dataset = local_tmp_path / "dataset"
    state = local_tmp_path / "state"
    dataset.mkdir()
    config = AppConfig(dataset_dir=dataset, state_dir=state)
    config.ensure_dirs()
    return config


def test_compute_song_returns_all_stems(local_tmp_path):
    config = _make_config(local_tmp_path)
    wav = config.dataset_dir / "song.wav"
    _make_wav(wav)

    comp = compute_song(wav, "abc", config, detector=DummyDetector())

    assert isinstance(comp, SongComputation)
    assert set(comp.stems.keys()) == {"mix", "vocals", "accompaniment", "bass", "percussive"}
    assert comp.duration_sec > 0
    assert comp.selection is not None
    assert comp.selection.stem_name in comp.stems
    assert comp.selection.stem_name in comp.notes_by_stem


def test_compute_song_only_extracts_notes_for_suggested_stem(local_tmp_path):
    config = _make_config(local_tmp_path)
    wav = config.dataset_dir / "song.wav"
    _make_wav(wav)

    comp = compute_song(wav, "x", config, detector=DummyDetector())

    # only the suggested stem has notes precomputed
    assert len(comp.notes_by_stem) == 1
    assert comp.selection.stem_name in comp.notes_by_stem


def test_cache_write_stem_wav_is_atomic(local_tmp_path):
    config = _make_config(local_tmp_path)
    sr = 22050
    audio = np.zeros(sr, dtype=np.float32)

    path = cache_mod.write_stem_wav(config.songs_cache_dir, "song1", "vocals", audio, sr)
    assert path.exists()
    # tmp file should be gone
    assert not path.with_suffix(path.suffix + ".tmp").exists()

    # Reading it back yields the same samples
    read_audio, read_sr = sf.read(path)
    assert read_sr == sr
    assert len(read_audio) == sr


def test_cache_notes_round_trip(local_tmp_path):
    config = _make_config(local_tmp_path)
    payload = [{"id": 0, "pitch": 60, "start": 0.0, "end": 0.5, "confidence": 0.9}]
    cache_mod.write_notes_json(config.songs_cache_dir, "song2", "vocals", payload)
    assert cache_mod.read_notes_json(config.songs_cache_dir, "song2", "vocals") == payload


def test_cache_source_meta(local_tmp_path):
    config = _make_config(local_tmp_path)
    cache_mod.write_source_meta(
        config.songs_cache_dir,
        "song3",
        audio_path="/abs/path.wav",
        sr=22050,
        duration_sec=12.3,
        candidate_scores={"vocals": 0.9, "mix": 0.5},
        suggested_stem="vocals",
    )
    meta = json.loads(
        cache_mod.source_meta_path(config.songs_cache_dir, "song3").read_text("utf-8")
    )
    assert meta["suggested_stem"] == "vocals"
    assert meta["candidate_scores"]["vocals"] == 0.9
    assert meta["duration_sec"] == pytest.approx(12.3)


def test_stem_wavs_present_helper(local_tmp_path):
    config = _make_config(local_tmp_path)
    sr = 22050
    silence = np.zeros(sr, dtype=np.float32)
    cache_mod.write_stem_wav(config.songs_cache_dir, "song4", "vocals", silence, sr)
    assert not cache_mod.stem_wavs_present(
        config.songs_cache_dir, "song4", ["vocals", "mix"]
    )
    cache_mod.write_stem_wav(config.songs_cache_dir, "song4", "mix", silence, sr)
    assert cache_mod.stem_wavs_present(
        config.songs_cache_dir, "song4", ["vocals", "mix"]
    )


def test_computation_to_cache_payloads_serializes_int_pitch():
    comp = SongComputation(
        sr=22050,
        duration_sec=1.0,
        notes_by_stem={
            "vocals": [
                NoteEvent(pitch=66.7, start_time=0.0, end_time=0.5, confidence=0.8),
            ],
        },
    )
    payloads = computation_to_cache_payloads(comp)
    assert payloads["vocals"][0]["pitch"] == 67
    assert isinstance(payloads["vocals"][0]["pitch"], int)


def test_reextract_runs_detector():
    audio = np.zeros(100, dtype=np.float32)
    notes = reextract_notes_for_stem(audio, 22050, detector=DummyDetector())
    assert len(notes) == 2
    assert notes[0].pitch == 67.0

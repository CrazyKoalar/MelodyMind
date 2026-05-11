"""Unit tests for hashing, serializers, and SQLite state."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from melonymind.core.pitch_detector import NoteEvent
from melonymind.webapp.hashing import song_hash
from melonymind.webapp.serializers import (
    note_event_from_dict,
    note_event_to_dict,
    notes_from_payload,
    notes_to_payload,
)
from melonymind.webapp.state import (
    NOTES_SOURCE_EDITED,
    NOTES_SOURCE_EXTRACTED,
    STATUS_CONFIRMED,
    STATUS_NEW,
    STATUS_STEM_PICKED,
    SongRow,
    StateRepo,
)


# ---------- hashing ----------


def test_song_hash_is_stable(local_tmp_path):
    audio = local_tmp_path / "song.wav"
    audio.write_bytes(b"fake")
    assert song_hash(audio) == song_hash(audio)


def test_song_hash_changes_on_mtime_change(local_tmp_path):
    audio = local_tmp_path / "song.wav"
    audio.write_bytes(b"fake")
    first = song_hash(audio)

    # Bump mtime to a new value
    new_mtime = time.time() + 5
    os.utime(audio, (new_mtime, new_mtime))
    assert song_hash(audio) != first


def test_song_hash_changes_on_content_change(local_tmp_path):
    audio = local_tmp_path / "song.wav"
    audio.write_bytes(b"fake")
    first = song_hash(audio)
    audio.write_bytes(b"longer_fake_content")
    assert song_hash(audio) != first


# ---------- serializers ----------


def test_serializer_rounds_pitch_to_int():
    note = NoteEvent(pitch=66.7, start_time=1.0, end_time=1.5, confidence=0.9)
    payload = note_event_to_dict(note)
    assert isinstance(payload["pitch"], int)
    assert payload["pitch"] == 67
    assert payload["start"] == pytest.approx(1.0)
    assert payload["end"] == pytest.approx(1.5)


def test_serializer_adds_id_when_requested():
    note = NoteEvent(pitch=60.0, start_time=0.0, end_time=0.5, confidence=1.0)
    assert "id" not in note_event_to_dict(note)
    assert note_event_to_dict(note, note_id=7)["id"] == 7


def test_notes_to_payload_assigns_sequential_ids():
    notes = [
        NoteEvent(pitch=60.0, start_time=0.0, end_time=0.5, confidence=1.0),
        NoteEvent(pitch=62.0, start_time=0.5, end_time=1.0, confidence=1.0),
    ]
    payload = notes_to_payload(notes)
    assert [item["id"] for item in payload] == [0, 1]
    assert [item["pitch"] for item in payload] == [60, 62]


def test_round_trip_through_serializer():
    notes = [
        NoteEvent(pitch=60.0, start_time=0.0, end_time=0.5, confidence=0.9),
        NoteEvent(pitch=64.0, start_time=0.5, end_time=1.0, confidence=0.8),
    ]
    payload = notes_to_payload(notes)
    restored = notes_from_payload(payload)

    assert len(restored) == 2
    assert restored[0].pitch == 60.0
    assert restored[1].pitch == 64.0
    assert restored[1].start_time == pytest.approx(0.5)


# ---------- state repo ----------


def _make_repo(local_tmp_path: Path) -> StateRepo:
    repo = StateRepo(local_tmp_path / "state.sqlite")
    repo.initialize(local_tmp_path)
    return repo


def test_repo_initialize_creates_schema(local_tmp_path):
    repo = _make_repo(local_tmp_path)
    with repo.connect() as conn:
        names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert {"meta", "songs", "song_notes"}.issubset(names)


def test_repo_upsert_and_get_song(local_tmp_path):
    repo = _make_repo(local_tmp_path)
    song = SongRow(
        id="abc123",
        audio_path=str(local_tmp_path / "a.wav"),
        relpath="a.wav",
        source_mtime_ns=1000,
        source_size=4096,
        duration_sec=12.5,
        status=STATUS_NEW,
        picked_stem=None,
        candidate_scores={"vocals": 0.8, "mix": 0.4},
    )
    repo.upsert_song(song)

    fetched = repo.get_song("abc123")
    assert fetched is not None
    assert fetched.relpath == "a.wav"
    assert fetched.candidate_scores == {"vocals": 0.8, "mix": 0.4}
    assert fetched.status == STATUS_NEW


def test_repo_update_status_and_stem(local_tmp_path):
    repo = _make_repo(local_tmp_path)
    repo.upsert_song(
        SongRow(
            id="x",
            audio_path="/x.wav",
            relpath="x.wav",
            source_mtime_ns=0,
            source_size=0,
            duration_sec=None,
            status=STATUS_NEW,
            picked_stem=None,
        )
    )

    repo.update_status("x", STATUS_STEM_PICKED, picked_stem="vocals")
    fetched = repo.get_song("x")
    assert fetched.status == STATUS_STEM_PICKED
    assert fetched.picked_stem == "vocals"

    repo.update_status("x", STATUS_CONFIRMED)
    fetched = repo.get_song("x")
    assert fetched.status == STATUS_CONFIRMED
    assert fetched.picked_stem == "vocals"  # preserved


def test_repo_notes_round_trip(local_tmp_path):
    repo = _make_repo(local_tmp_path)
    repo.upsert_song(
        SongRow(
            id="s1",
            audio_path="/s1.wav",
            relpath="s1.wav",
            source_mtime_ns=0,
            source_size=0,
            duration_sec=None,
            status=STATUS_NEW,
            picked_stem=None,
        )
    )

    payload = [{"id": 0, "pitch": 60, "start": 0.0, "end": 0.5, "confidence": 0.9}]
    repo.upsert_notes("s1", "vocals", payload, source=NOTES_SOURCE_EXTRACTED)

    notes_row = repo.get_notes("s1", "vocals")
    assert notes_row is not None
    assert notes_row.source == NOTES_SOURCE_EXTRACTED
    assert notes_row.notes == payload

    edited = [{"id": 0, "pitch": 62, "start": 0.0, "end": 0.5, "confidence": 0.95}]
    repo.upsert_notes("s1", "vocals", edited, source=NOTES_SOURCE_EDITED)
    notes_row = repo.get_notes("s1", "vocals")
    assert notes_row.source == NOTES_SOURCE_EDITED
    assert notes_row.notes[0]["pitch"] == 62


def test_repo_mark_cache_ready_promotes_status_only_from_new(local_tmp_path):
    repo = _make_repo(local_tmp_path)
    repo.upsert_song(
        SongRow(
            id="a",
            audio_path="/a.wav",
            relpath="a.wav",
            source_mtime_ns=0,
            source_size=0,
            duration_sec=None,
            status=STATUS_NEW,
            picked_stem=None,
        )
    )
    repo.mark_cache_ready("a", {"vocals": 0.9, "mix": 0.3}, "vocals")
    fetched = repo.get_song("a")
    assert fetched.cache_ready is True
    assert fetched.candidate_scores == {"vocals": 0.9, "mix": 0.3}
    assert fetched.picked_stem == "vocals"
    assert fetched.status == "opened"

    # If already advanced, status is preserved
    repo.update_status("a", STATUS_CONFIRMED, picked_stem="vocals")
    repo.mark_cache_ready("a", {"vocals": 0.95, "mix": 0.2}, "vocals")
    fetched = repo.get_song("a")
    assert fetched.status == STATUS_CONFIRMED


def test_repo_rejects_invalid_status(local_tmp_path):
    repo = _make_repo(local_tmp_path)
    with pytest.raises(ValueError):
        repo.upsert_song(
            SongRow(
                id="bad",
                audio_path="/bad.wav",
                relpath="bad.wav",
                source_mtime_ns=0,
                source_size=0,
                duration_sec=None,
                status="bogus",
                picked_stem=None,
            )
        )

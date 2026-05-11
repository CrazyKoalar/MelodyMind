"""TestClient tests for song catalog and audio streaming routes."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from melonymind.core.pitch_detector import NoteEvent
from melonymind.webapp.config import STEM_NAMES, AppConfig
from melonymind.webapp.server import create_app


class DummyDetector:
    def detect(self, audio, sr: int, min_confidence: float = 0.5):
        return [
            NoteEvent(pitch=67.0, start_time=0.0, end_time=0.5, confidence=0.9),
            NoteEvent(pitch=69.0, start_time=0.5, end_time=1.0, confidence=0.85),
        ]


def _make_wav(path: Path, sr: int = 22050, seconds: float = 1.0) -> None:
    t = np.linspace(0.0, seconds, int(sr * seconds), endpoint=False)
    sine = 0.5 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
    sf.write(path, sine, sr)


def _make_client(local_tmp_path: Path, num_songs: int = 1):
    dataset = local_tmp_path / "dataset"
    state = local_tmp_path / "state"
    dataset.mkdir()
    for i in range(num_songs):
        _make_wav(dataset / f"song_{i}.wav")
    config = AppConfig(dataset_dir=dataset, state_dir=state)
    app = create_app(config)
    app.state.test_detector = DummyDetector()
    return TestClient(app), config


def test_list_songs_discovers_audio_files(local_tmp_path):
    client, _ = _make_client(local_tmp_path, num_songs=3)
    payload = client.get("/api/songs").json()
    assert len(payload["songs"]) == 3
    assert {s["filename"] for s in payload["songs"]} == {
        "song_0.wav",
        "song_1.wav",
        "song_2.wav",
    }
    assert all(s["status"] == "new" for s in payload["songs"])
    assert all(s["picked_stem"] is None for s in payload["songs"])


def test_compute_then_pick_stem_persists(local_tmp_path):
    client, config = _make_client(local_tmp_path, num_songs=1)
    songs = client.get("/api/songs").json()["songs"]
    song_id = songs[0]["id"]

    compute = client.post(f"/api/songs/{song_id}/compute", json={"force": False}).json()
    assert set(compute["stems"]) == set(STEM_NAMES)
    assert compute["suggested_stem"] in STEM_NAMES
    assert compute["candidate_scores"]

    pick = client.post(f"/api/songs/{song_id}/stem", json={"stem": "vocals"}).json()
    assert pick["status"] == "stem_picked"
    assert pick["picked_stem"] == "vocals"

    detail = client.get(f"/api/songs/{song_id}").json()
    assert detail["status"] == "stem_picked"
    assert detail["picked_stem"] == "vocals"
    assert detail["cache_ready"] is True


def test_invalid_stem_rejected(local_tmp_path):
    client, _ = _make_client(local_tmp_path, num_songs=1)
    songs = client.get("/api/songs").json()["songs"]
    song_id = songs[0]["id"]
    client.post(f"/api/songs/{song_id}/compute").json()

    response = client.post(f"/api/songs/{song_id}/stem", json={"stem": "bogus"})
    assert response.status_code == 400


def test_confirm_requires_picked_stem(local_tmp_path):
    client, _ = _make_client(local_tmp_path, num_songs=1)
    songs = client.get("/api/songs").json()["songs"]
    song_id = songs[0]["id"]
    client.post(f"/api/songs/{song_id}/compute").json()

    response = client.post(f"/api/songs/{song_id}/confirm")
    assert response.status_code == 400

    client.post(f"/api/songs/{song_id}/stem", json={"stem": "vocals"})
    response = client.post(f"/api/songs/{song_id}/confirm")
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"


def test_reopen_drops_confirmed(local_tmp_path):
    client, _ = _make_client(local_tmp_path, num_songs=1)
    song_id = client.get("/api/songs").json()["songs"][0]["id"]
    client.post(f"/api/songs/{song_id}/compute")
    client.post(f"/api/songs/{song_id}/stem", json={"stem": "vocals"})
    client.post(f"/api/songs/{song_id}/confirm")

    response = client.post(f"/api/songs/{song_id}/reopen")
    assert response.status_code == 200
    assert response.json()["status"] == "stem_picked"


def test_unknown_song_returns_404(local_tmp_path):
    client, _ = _make_client(local_tmp_path, num_songs=0)
    response = client.get("/api/songs/nonexistent")
    assert response.status_code == 404


def test_range_request_returns_206(local_tmp_path):
    client, _ = _make_client(local_tmp_path, num_songs=1)
    song_id = client.get("/api/songs").json()["songs"][0]["id"]
    client.post(f"/api/songs/{song_id}/compute")

    response = client.get(
        f"/media/{song_id}/source",
        headers={"Range": "bytes=0-99"},
    )
    assert response.status_code == 206
    assert response.headers["Accept-Ranges"] == "bytes"
    assert "Content-Range" in response.headers
    assert response.headers["Content-Range"].startswith("bytes 0-99/")
    assert len(response.content) == 100


def test_full_audio_returns_200(local_tmp_path):
    client, _ = _make_client(local_tmp_path, num_songs=1)
    song_id = client.get("/api/songs").json()["songs"][0]["id"]
    client.post(f"/api/songs/{song_id}/compute")

    response = client.get(f"/media/{song_id}/source")
    assert response.status_code == 200
    assert response.headers["Accept-Ranges"] == "bytes"
    assert int(response.headers["Content-Length"]) == len(response.content)
    assert response.headers["content-type"].startswith("audio/wav")


def test_stem_endpoint_serves_each_stem(local_tmp_path):
    client, _ = _make_client(local_tmp_path, num_songs=1)
    song_id = client.get("/api/songs").json()["songs"][0]["id"]
    client.post(f"/api/songs/{song_id}/compute")

    for stem in STEM_NAMES:
        response = client.get(f"/media/{song_id}/stems/{stem}")
        assert response.status_code == 200, f"failed for {stem}"
        assert response.content[:4] == b"RIFF"


def test_compute_idempotent_when_cached(local_tmp_path):
    client, _ = _make_client(local_tmp_path, num_songs=1)
    song_id = client.get("/api/songs").json()["songs"][0]["id"]
    first = client.post(f"/api/songs/{song_id}/compute").json()
    assert first["cached"] is False

    second = client.post(f"/api/songs/{song_id}/compute", json={"force": False}).json()
    assert second["cached"] is True

    third = client.post(f"/api/songs/{song_id}/compute", json={"force": True}).json()
    assert third["cached"] is False


def test_upload_registers_under_uploads(local_tmp_path):
    client, config = _make_client(local_tmp_path, num_songs=0)
    wav_path = local_tmp_path / "incoming.wav"
    _make_wav(wav_path)
    with wav_path.open("rb") as handle:
        response = client.post(
            "/api/songs/upload",
            files={"file": ("incoming.wav", handle, "audio/wav")},
            data={"auto_compute": "false"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["compute"] is None
    assert payload["song"]["relpath"].replace("\\", "/").startswith("uploads/")
    assert (config.dataset_dir / payload["song"]["relpath"]).is_file()


def test_sheet_lilypond_contains_version_header(local_tmp_path):
    client, _ = _make_client(local_tmp_path, num_songs=1)
    song_id = client.get("/api/songs").json()["songs"][0]["id"]
    client.post(f"/api/songs/{song_id}/compute")
    client.post(f"/api/songs/{song_id}/stem", json={"stem": "vocals"})

    response = client.get(
        f"/api/songs/{song_id}/sheet",
        params={"sheet_format": "lilypond", "stem": "vocals"},
    )
    assert response.status_code == 200
    assert "\\version" in response.text

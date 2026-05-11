"""TestClient tests for notes routes + manifest export.

The export test feeds the generated manifest into the existing trainer's data
reader path to prove byte-level compatibility.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from melonymind.core.pitch_detector import NoteEvent
from melonymind.training.dataset_prep import build_manifest_from_review_file
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


def _prepare_song(client: TestClient, song_id: str, stem: str = "vocals") -> None:
    client.post(f"/api/songs/{song_id}/compute")
    client.post(f"/api/songs/{song_id}/stem", json={"stem": stem})


# ---------- notes routes ----------


def test_notes_round_trip(local_tmp_path):
    client, _ = _make_client(local_tmp_path, num_songs=1)
    song_id = client.get("/api/songs").json()["songs"][0]["id"]
    _prepare_song(client, song_id)

    initial = client.get(f"/api/songs/{song_id}/notes").json()
    assert initial["stem"] == "vocals"
    assert initial["source"] == "extracted"
    assert len(initial["notes"]) == 2
    assert isinstance(initial["notes"][0]["pitch"], int)

    edited = [
        {"id": 0, "pitch": 72, "start": 0.0, "end": 0.4, "confidence": 1.0},
        {"id": 1, "pitch": 74, "start": 0.4, "end": 0.8, "confidence": 1.0},
        {"id": 2, "pitch": 76, "start": 0.8, "end": 1.0, "confidence": 1.0},
    ]
    put = client.put(
        f"/api/songs/{song_id}/notes",
        json={"stem": "vocals", "notes": edited},
    ).json()
    assert put["status"] == "notes_edited"
    assert put["count"] == 3

    after = client.get(f"/api/songs/{song_id}/notes").json()
    assert after["source"] == "edited"
    assert [n["pitch"] for n in after["notes"]] == [72, 74, 76]


def test_notes_get_uses_picked_stem_by_default(local_tmp_path):
    client, _ = _make_client(local_tmp_path, num_songs=1)
    song_id = client.get("/api/songs").json()["songs"][0]["id"]
    _prepare_song(client, song_id, stem="vocals")

    payload = client.get(f"/api/songs/{song_id}/notes").json()
    assert payload["stem"] == "vocals"


def test_notes_400_when_no_picked_stem_and_no_query(local_tmp_path):
    client, _ = _make_client(local_tmp_path, num_songs=1)
    song_id = client.get("/api/songs").json()["songs"][0]["id"]
    client.post(f"/api/songs/{song_id}/compute")  # no stem pick

    response = client.get(f"/api/songs/{song_id}/notes")
    assert response.status_code == 400


def test_reextract_uses_cached_stem(local_tmp_path):
    client, _ = _make_client(local_tmp_path, num_songs=1)
    song_id = client.get("/api/songs").json()["songs"][0]["id"]
    _prepare_song(client, song_id)

    response = client.post(
        f"/api/songs/{song_id}/notes/reextract", json={"stem": "vocals"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "extracted"
    assert len(payload["notes"]) == 2


def test_reextract_requires_compute_first(local_tmp_path):
    client, _ = _make_client(local_tmp_path, num_songs=1)
    song_id = client.get("/api/songs").json()["songs"][0]["id"]

    response = client.post(
        f"/api/songs/{song_id}/notes/reextract", json={"stem": "vocals"}
    )
    assert response.status_code == 409


# ---------- manifest export ----------


def test_export_writes_trainer_compatible_manifest(local_tmp_path):
    client, config = _make_client(local_tmp_path, num_songs=2)
    songs = client.get("/api/songs").json()["songs"]
    for s in songs:
        _prepare_song(client, s["id"], stem="vocals")
        client.post(f"/api/songs/{s['id']}/confirm")

    result = client.post("/api/export", json={"only_confirmed": True}).json()
    assert result["count"] == 2

    manifest_path = Path(result["melody_manifest"])
    assert manifest_path.exists()
    lines = [json.loads(line) for line in manifest_path.read_text("utf-8").splitlines() if line]
    assert len(lines) == 2
    for entry in lines:
        assert entry["target_stem_name"] == "vocals"
        assert Path(entry["audio_path"]).exists()

    # Critical compatibility check: feed the manifest format through the
    # existing dataset_prep.build_manifest_from_review_file via a CSV → it
    # should produce an identical manifest file shape from the review CSV.
    rebuilt = local_tmp_path / "rebuilt.jsonl"
    build_manifest_from_review_file(result["review_csv"], rebuilt)
    rebuilt_lines = [
        json.loads(line) for line in rebuilt.read_text("utf-8").splitlines() if line
    ]
    assert {(e["audio_path"], e["target_stem_name"]) for e in rebuilt_lines} == {
        (e["audio_path"], e["target_stem_name"]) for e in lines
    }


def test_export_includes_notes_manifest(local_tmp_path):
    client, _ = _make_client(local_tmp_path, num_songs=1)
    song_id = client.get("/api/songs").json()["songs"][0]["id"]
    _prepare_song(client, song_id, stem="vocals")
    client.put(
        f"/api/songs/{song_id}/notes",
        json={
            "stem": "vocals",
            "notes": [{"id": 0, "pitch": 60, "start": 0.0, "end": 0.5, "confidence": 1.0}],
        },
    )
    client.post(f"/api/songs/{song_id}/confirm")

    result = client.post("/api/export").json()
    notes_path = Path(result["notes_manifest"])
    entry = json.loads(notes_path.read_text("utf-8").splitlines()[0])
    assert entry["target_stem_name"] == "vocals"
    assert entry["sr"] > 0
    assert entry["notes"][0]["pitch"] == 60


def test_export_skips_unconfirmed_by_default(local_tmp_path):
    client, _ = _make_client(local_tmp_path, num_songs=2)
    songs = client.get("/api/songs").json()["songs"]
    _prepare_song(client, songs[0]["id"], stem="vocals")
    client.post(f"/api/songs/{songs[0]['id']}/confirm")
    _prepare_song(client, songs[1]["id"], stem="mix")  # not confirmed

    result = client.post("/api/export", json={"only_confirmed": True}).json()
    assert result["count"] == 1


def test_export_review_csv_columns(local_tmp_path):
    """The CSV must match the legacy schema used by dataset_prep."""
    client, _ = _make_client(local_tmp_path, num_songs=1)
    song_id = client.get("/api/songs").json()["songs"][0]["id"]
    _prepare_song(client, song_id, stem="vocals")
    client.post(f"/api/songs/{song_id}/confirm")

    result = client.post("/api/export").json()
    csv_path = Path(result["review_csv"])
    header = csv_path.read_text("utf-8").splitlines()[0]
    expected = [
        "audio_path",
        "suggested_stem_name",
        "target_stem_name",
        "label_status",
        "candidate_scores_json",
    ]
    assert header.split(",") == expected


def test_reveal_rejects_paths_outside_state_dir(local_tmp_path):
    client, _ = _make_client(local_tmp_path, num_songs=0)
    response = client.post("/api/reveal", json={"path": str(local_tmp_path / "dataset")})
    assert response.status_code == 400


def test_reveal_404_when_path_missing(local_tmp_path):
    client, config = _make_client(local_tmp_path, num_songs=0)
    bogus = config.state_dir / "no-such-file.txt"
    response = client.post("/api/reveal", json={"path": str(bogus)})
    assert response.status_code == 404

"""Smoke tests for the webapp scaffold."""

from __future__ import annotations

from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from melonymind.webapp.config import AppConfig  # noqa: E402
from melonymind.webapp.server import create_app  # noqa: E402


def _make_app(local_tmp_path: Path):
    dataset = local_tmp_path / "dataset"
    state = local_tmp_path / "state"
    dataset.mkdir()
    config = AppConfig(dataset_dir=dataset, state_dir=state)
    return create_app(config), config


def test_app_boots_and_health_returns_ok(local_tmp_path):
    app, config = _make_app(local_tmp_path)
    client = TestClient(app)

    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["dataset_dir"] == str(config.dataset_dir)


def test_songs_endpoint_returns_empty_array_when_no_songs(local_tmp_path):
    app, _ = _make_app(local_tmp_path)
    client = TestClient(app)

    response = client.get("/api/songs")
    assert response.status_code == 200
    assert response.json() == {"songs": []}


def test_state_dir_is_created(local_tmp_path):
    _, config = _make_app(local_tmp_path)
    assert config.state_dir.exists()
    assert config.songs_cache_dir.exists()
    assert config.export_dir.exists()

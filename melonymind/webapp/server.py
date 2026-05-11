"""FastAPI application factory for the annotation web app."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import AppConfig

STATIC_DIR = Path(__file__).parent / "static"


def create_app(config: AppConfig) -> FastAPI:
    """Build a FastAPI app bound to the given configuration."""
    config.ensure_dirs()

    app = FastAPI(title="MelodyMind Annotation", version="0.1.0")
    app.state.config = config

    from . import (
        manifest as manifest_mod,
        routes_audio,
        routes_notes,
        routes_sheet,
        routes_songs,
    )
    from .state import StateRepo

    StateRepo(config.db_path).initialize(config.dataset_dir)

    app.include_router(routes_songs.router)
    app.include_router(routes_audio.router)
    app.include_router(routes_notes.router)
    app.include_router(routes_sheet.router)
    app.include_router(manifest_mod.router)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    def root():
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return HTMLResponse(
            "<h1>MelodyMind Annotation</h1>"
            "<p>Backend is running. Static frontend not built yet.</p>"
            "<p>Try <a href='/api/songs'>/api/songs</a>.</p>"
        )

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "dataset_dir": str(config.dataset_dir)}

    return app

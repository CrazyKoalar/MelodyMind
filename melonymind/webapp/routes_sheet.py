"""Export melody notes as printable sheet music (LilyPond / HTML preview)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from ..notation.sheet_generator import SheetGenerator, SheetMusicConfig
from .config import AppConfig
from .deps import get_config, get_repo
from .routes_notes import fetch_notes_payload
from .serializers import notes_from_payload
from .state import StateRepo

router = APIRouter(prefix="/api")


def _sheet_config_from_query(
    title: str,
    composer: str,
    tempo: int,
    key: str,
    time_signature: str,
) -> SheetMusicConfig:
    return SheetMusicConfig(
        title=title or "Transcribed melody",
        composer=composer or "",
        tempo=max(1, min(tempo, 400)),
        key=key or "C major",
        time_signature=time_signature or "4/4",
    )


@router.get("/songs/{song_id}/sheet")
def get_sheet_music(
    song_id: str,
    request: Request,
    stem: Optional[str] = Query(default=None),
    sheet_format: str = Query(
        default="lilypond",
        description="lilypond (.ly text), html (VexFlow preview), or json",
    ),
    title: str = Query(default=""),
    composer: str = Query(default=""),
    tempo: int = Query(default=120),
    key: str = Query(default="C major"),
    time_signature: str = Query(default="4/4"),
    config: AppConfig = Depends(get_config),
    repo: StateRepo = Depends(get_repo),
):
    """Build notation from the same notes as the piano-roll editor (incl. edits)."""
    payload = fetch_notes_payload(song_id, request, config, repo, stem=stem)
    notes = notes_from_payload(payload["notes"])
    notes.sort(key=lambda n: n.start_time)

    cfg = _sheet_config_from_query(title, composer, tempo, key, time_signature)
    generator = SheetGenerator(cfg)

    fmt = (sheet_format or "lilypond").lower()
    if fmt == "json":
        body: Dict[str, Any] = {
            "title": cfg.title,
            "composer": cfg.composer,
            "tempo": cfg.tempo,
            "key": cfg.key,
            "time_signature": cfg.time_signature,
            "stem": payload["stem"],
            "lilypond": generator.generate_lilypond(notes),
            "vexflow_html": generator.generate_vexflow(notes),
        }
        return JSONResponse(body)

    if fmt == "html":
        html = generator.generate_vexflow(notes)
        return HTMLResponse(html)

    if fmt == "lilypond":
        lily = generator.generate_lilypond(notes)
        safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in cfg.title)[
            :80
        ] or "melody"
        return PlainTextResponse(
            lily,
            media_type="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_title}.ly"'
            },
        )

    raise HTTPException(
        status_code=400,
        detail="sheet_format must be lilypond, html, or json",
    )

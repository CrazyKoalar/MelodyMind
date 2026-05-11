"""Routes for streaming source audio and separated stem WAVs.

Implements HTTP Range so browser <audio> can scrub through the file. FastAPI's
FileResponse does not honor Range, which makes Chrome refuse to seek.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Optional, Tuple

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from . import cache as cache_mod
from .config import STEM_NAMES, AppConfig
from .deps import get_config, get_repo, require_song
from .state import StateRepo

router = APIRouter(prefix="/media")

CHUNK_SIZE = 64 * 1024  # 64 KB per read


_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


def _parse_range(header: Optional[str], file_size: int) -> Optional[Tuple[int, int]]:
    """Return (start, end_inclusive) or None for full-body."""
    if not header:
        return None
    match = _RANGE_RE.match(header.strip())
    if not match:
        return None
    raw_start, raw_end = match.group(1), match.group(2)
    if raw_start == "" and raw_end == "":
        return None
    if raw_start == "":
        # suffix range: last N bytes
        length = int(raw_end)
        if length <= 0:
            return None
        start = max(0, file_size - length)
        end = file_size - 1
    else:
        start = int(raw_start)
        end = int(raw_end) if raw_end != "" else file_size - 1
    if start > end or start >= file_size:
        return None
    end = min(end, file_size - 1)
    return start, end


def _iter_file_range(path: Path, start: int, end: int) -> Iterable[bytes]:
    with path.open("rb") as handle:
        handle.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = handle.read(min(CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def _stream_wav(path: Path, range_header: Optional[str]) -> Response:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"audio not cached: {path.name}")
    file_size = path.stat().st_size
    parsed = _parse_range(range_header, file_size)

    if parsed is None:
        return Response(
            content=path.read_bytes(),
            media_type="audio/wav",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
            },
        )

    start, end = parsed
    length = end - start + 1
    return StreamingResponse(
        _iter_file_range(path, start, end),
        status_code=206,
        media_type="audio/wav",
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
        },
    )


@router.get("/{song_id}/source")
def stream_source(
    song_id: str,
    range: Optional[str] = Header(default=None),
    config: AppConfig = Depends(get_config),
    repo: StateRepo = Depends(get_repo),
) -> Response:
    """Stream the cached `mix` stem.

    The `mix` stem is the unmodified original signal after normalize+trim, so
    we serve it as the source audio. Avoids streaming arbitrary user paths.
    """
    require_song(repo, song_id)
    path = cache_mod.stem_wav_path(config.songs_cache_dir, song_id, "mix")
    return _stream_wav(path, range)


@router.get("/{song_id}/stems/{stem}")
def stream_stem(
    song_id: str,
    stem: str,
    range: Optional[str] = Header(default=None),
    config: AppConfig = Depends(get_config),
    repo: StateRepo = Depends(get_repo),
) -> Response:
    require_song(repo, song_id)
    if stem not in STEM_NAMES:
        raise HTTPException(status_code=400, detail=f"invalid stem: {stem!r}")
    path = cache_mod.stem_wav_path(config.songs_cache_dir, song_id, stem)
    return _stream_wav(path, range)

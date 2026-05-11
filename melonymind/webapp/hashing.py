"""Stable per-song identity hashing."""

from __future__ import annotations

import hashlib
from pathlib import Path


def song_hash(audio_path: str | Path) -> str:
    """Hash that changes whenever the source file is replaced or edited.

    The hash is derived from the absolute path, last-modified time (ns) and size.
    Two different files at different paths get different ids; the same file edited
    in-place gets a new id and the cache invalidates automatically.
    """
    path = Path(audio_path).resolve()
    stat = path.stat()
    raw = f"{path}:{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]

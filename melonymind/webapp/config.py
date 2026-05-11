"""Runtime configuration for the annotation web app."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}
STEM_NAMES = ("mix", "vocals", "accompaniment", "bass", "percussive")


@dataclass
class AppConfig:
    """Configuration resolved from CLI flags before the FastAPI app is built."""

    dataset_dir: Path
    state_dir: Path
    sample_rate: int = 22050
    min_confidence: float = 0.55
    allow_remote: bool = False

    def __post_init__(self) -> None:
        self.dataset_dir = Path(self.dataset_dir).expanduser().resolve()
        self.state_dir = Path(self.state_dir).expanduser().resolve()

    @property
    def db_path(self) -> Path:
        return self.state_dir / "annotation.sqlite"

    @property
    def songs_cache_dir(self) -> Path:
        return self.state_dir / "songs"

    @property
    def export_dir(self) -> Path:
        return self.state_dir / "export"

    def ensure_dirs(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.songs_cache_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)

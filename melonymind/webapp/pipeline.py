"""Single entry point for the audio→stems→notes computation pipeline.

This is the only module in the webapp that touches AudioProcessor and PitchDetector.
Keeping it isolated lets tests monkey-patch one symbol and lets routes stay thin.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Dict, List

from ..core.audio_processor import AudioProcessor, MelodyStemSelection, SeparatedStem
from ..core.pitch_detector import DetectionMode, NoteEvent, PitchDetector
from .config import AppConfig, STEM_NAMES
from .serializers import notes_to_payload


@dataclass
class SongComputation:
    """Result of running the full pipeline once."""

    sr: int
    duration_sec: float
    stems: Dict[str, SeparatedStem] = field(default_factory=dict)
    selection: MelodyStemSelection | None = None
    notes_by_stem: Dict[str, List[NoteEvent]] = field(default_factory=dict)


_compute_locks: Dict[str, Lock] = {}
_locks_guard = Lock()


def _lock_for(song_id: str) -> Lock:
    with _locks_guard:
        lock = _compute_locks.get(song_id)
        if lock is None:
            lock = Lock()
            _compute_locks[song_id] = lock
        return lock


def compute_song(
    audio_path: str | Path,
    song_id: str,
    config: AppConfig,
    *,
    processor: AudioProcessor | None = None,
    detector: PitchDetector | None = None,
) -> SongComputation:
    """Run the full pipeline for one song.

    Serialized per-song via an in-process lock so a re-extract triggered while a
    previous compute is still running doesn't fight for the same WAV.
    """
    processor = processor or AudioProcessor(sample_rate=config.sample_rate)
    detector = detector or PitchDetector(mode=DetectionMode.PYIN)

    with _lock_for(song_id):
        audio, sr = processor.load(str(audio_path))
        audio = processor.normalize(audio)
        audio = processor.trim_silence(audio)
        duration_sec = len(audio) / float(sr) if sr else 0.0

        stems = processor.separate_sources(audio, sr)
        selection = processor.choose_melody_stem(
            stems, sr, detector, min_confidence=config.min_confidence
        )

        notes_by_stem: Dict[str, List[NoteEvent]] = {}
        # Only the suggested stem gets pitch-detected eagerly. Other stems are
        # extracted lazily on demand via reextract_notes_for_stem.
        suggested_stem = selection.stem_name
        notes_by_stem[suggested_stem] = detector.detect(
            stems[suggested_stem].audio, sr, min_confidence=config.min_confidence
        )

        return SongComputation(
            sr=sr,
            duration_sec=duration_sec,
            stems={name: stem for name, stem in stems.items() if name in STEM_NAMES},
            selection=selection,
            notes_by_stem=notes_by_stem,
        )


def reextract_notes_for_stem(
    stem_audio,
    sr: int,
    *,
    detector: PitchDetector | None = None,
    min_confidence: float = 0.5,
) -> List[NoteEvent]:
    """Re-run pitch detection on a single stem's audio."""
    detector = detector or PitchDetector(mode=DetectionMode.PYIN)
    return detector.detect(stem_audio, sr, min_confidence=min_confidence)


def computation_to_cache_payloads(comp: SongComputation) -> Dict[str, List[dict]]:
    """Convert per-stem NoteEvent lists to the JSON wire format for caching."""
    return {stem: notes_to_payload(notes) for stem, notes in comp.notes_by_stem.items()}

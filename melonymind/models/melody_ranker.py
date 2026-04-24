"""Interfaces, baseline models, and trainable models for melody-stem ranking."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Protocol

import librosa
import numpy as np

from ..core.pitch_detector import NoteEvent


@dataclass
class MelodyCandidateFeatures:
    """Features extracted from one candidate stem."""

    stem_name: str
    note_count: int
    mean_confidence: float
    pitch_range: float
    mean_duration: float
    rms_energy: float
    zero_crossing_rate: float
    spectral_centroid_mean: float
    voiced_ratio: float

    def as_dict(self) -> dict:
        return asdict(self)

    def as_vector(self) -> np.ndarray:
        return np.array(
            [
                float(self.note_count),
                self.mean_confidence,
                self.pitch_range,
                self.mean_duration,
                self.rms_energy,
                self.zero_crossing_rate,
                self.spectral_centroid_mean,
                self.voiced_ratio,
            ],
            dtype=float,
        )


class MelodyStemRanker(Protocol):
    """Protocol for a model that scores melody likelihood per stem."""

    def score_candidates(
        self, features: Iterable[MelodyCandidateFeatures]
    ) -> Dict[str, float]:
        """Return a score for each candidate stem."""


class HeuristicMelodyStemRanker:
    """Default rule-based ranker that can later be replaced by a trained model."""

    def score_candidates(
        self, features: Iterable[MelodyCandidateFeatures]
    ) -> Dict[str, float]:
        scores: Dict[str, float] = {}
        for item in features:
            note_density = min(item.note_count / 32.0, 1.0)
            pitch_range = min(item.pitch_range / 24.0, 1.0)
            duration_score = min(item.mean_duration / 0.6, 1.0)
            energy_score = min(item.rms_energy * 8.0, 1.0)
            centroid_score = min(item.spectral_centroid_mean / 2500.0, 1.0)

            scores[item.stem_name] = (
                item.mean_confidence * 0.28
                + pitch_range * 0.2
                + duration_score * 0.16
                + energy_score * 0.12
                + centroid_score * 0.08
                + note_density * 0.08
                + item.voiced_ratio * 0.08
            )
        return scores


class MelodyFeatureExtractor:
    """Extract candidate features suitable for training or inference."""

    def extract(
        self, stem_name: str, audio: np.ndarray, sr: int, notes: List[NoteEvent]
    ) -> MelodyCandidateFeatures:
        if len(audio):
            rms_energy = float(librosa.feature.rms(y=audio).mean())
            zero_crossing_rate = float(librosa.feature.zero_crossing_rate(y=audio).mean())
            spectral_centroid_mean = float(
                librosa.feature.spectral_centroid(y=audio, sr=sr).mean()
            )
        else:
            rms_energy = 0.0
            zero_crossing_rate = 0.0
            spectral_centroid_mean = 0.0

        if notes:
            confidences = np.array([float(note.confidence) for note in notes], dtype=float)
            pitches = np.array([float(note.pitch) for note in notes], dtype=float)
            durations = np.array([max(float(note.duration), 1e-3) for note in notes], dtype=float)
            song_end = max(float(note.end_time) for note in notes)
            active_time = float(durations.sum())
            voiced_ratio = min(active_time / max(song_end, 1e-3), 1.0)
            mean_confidence = float(confidences.mean())
            pitch_range = float(np.ptp(pitches))
            mean_duration = float(durations.mean())
        else:
            voiced_ratio = 0.0
            mean_confidence = 0.0
            pitch_range = 0.0
            mean_duration = 0.0

        return MelodyCandidateFeatures(
            stem_name=stem_name,
            note_count=len(notes),
            mean_confidence=mean_confidence,
            pitch_range=pitch_range,
            mean_duration=mean_duration,
            rms_energy=rms_energy,
            zero_crossing_rate=zero_crossing_rate,
            spectral_centroid_mean=spectral_centroid_mean,
            voiced_ratio=voiced_ratio,
        )


@dataclass
class TrainableMelodyStemRanker:
    """
    Lightweight learned ranker trained from feature vectors.

    The model uses z-score normalization, a linear projection, and a learned
    per-stem bias. This keeps inference simple and dependency-free while giving
    us a clean bridge to future heavier models.
    """

    feature_mean: List[float]
    feature_scale: List[float]
    weights: List[float]
    bias: float
    stem_bias: Dict[str, float]

    def score_candidates(
        self, features: Iterable[MelodyCandidateFeatures]
    ) -> Dict[str, float]:
        scores: Dict[str, float] = {}
        mean = np.array(self.feature_mean, dtype=float)
        scale = np.array(self.feature_scale, dtype=float)
        weights = np.array(self.weights, dtype=float)

        for item in features:
            normalized = (item.as_vector() - mean) / scale
            score = float(np.dot(normalized, weights) + self.bias)
            score += float(self.stem_bias.get(item.stem_name, 0.0))
            scores[item.stem_name] = score
        return scores

    def save(self, output_path: str | Path) -> str:
        path = Path(output_path)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return str(path)

    @classmethod
    def load(cls, model_path: str | Path) -> "TrainableMelodyStemRanker":
        payload = json.loads(Path(model_path).read_text(encoding="utf-8"))
        return cls(**payload)

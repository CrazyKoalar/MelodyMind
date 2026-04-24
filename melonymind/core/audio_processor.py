"""Audio preprocessing, rough source separation, and melody candidate search."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import librosa
import numpy as np

from ..models.melody_ranker import (
    HeuristicMelodyStemRanker,
    MelodyFeatureExtractor,
    MelodyStemRanker,
)


@dataclass
class SeparatedStem:
    """A coarse separated audio stem."""

    name: str
    audio: np.ndarray
    score: float = 0.0


@dataclass
class MelodyStemSelection:
    """Result of selecting the stem that most resembles the lead melody."""

    stem_name: str
    stem_audio: np.ndarray
    stem_scores: Dict[str, float]


class AudioProcessor:
    """Process audio files for transcription."""

    def __init__(
        self,
        sample_rate: int = 22050,
        melody_ranker: MelodyStemRanker | None = None,
        melody_feature_extractor: MelodyFeatureExtractor | None = None,
    ):
        """
        Initialize audio processor.

        Args:
            sample_rate: Target sample rate for processing
        """
        self.sample_rate = sample_rate
        self.melody_ranker = melody_ranker or HeuristicMelodyStemRanker()
        self.melody_feature_extractor = melody_feature_extractor or MelodyFeatureExtractor()

    def load(self, audio_path: str) -> Tuple[np.ndarray, int]:
        """
        Load audio file.

        Args:
            audio_path: Path to audio file

        Returns:
            Tuple of (audio_data, sample_rate)
        """
        audio, sr = librosa.load(audio_path, sr=self.sample_rate, mono=True)
        return audio, sr

    def normalize(self, audio: np.ndarray) -> np.ndarray:
        """Normalize audio to [-1, 1] range."""
        return librosa.util.normalize(audio)

    def trim_silence(self, audio: np.ndarray, top_db: int = 20) -> np.ndarray:
        """Trim silence from beginning and end."""
        trimmed, _ = librosa.effects.trim(audio, top_db=top_db)
        return trimmed

    def split_by_onset(self, audio: np.ndarray, sr: int) -> list:
        """
        Split audio by onset detection.

        Args:
            audio: Audio array
            sr: Sample rate

        Returns:
            List of audio segments
        """
        onset_frames = librosa.onset.onset_detect(
            y=audio, sr=sr, wait=3, pre_avg=3, post_avg=3, pre_max=3, post_max=3
        )
        onset_samples = librosa.frames_to_samples(onset_frames)
        
        segments = []
        for i in range(len(onset_samples) - 1):
            segment = audio[onset_samples[i]:onset_samples[i + 1]]
            segments.append(segment)
        
        # Add last segment
        if onset_samples.size > 0:
            segments.append(audio[onset_samples[-1]:])

        return segments

    def detect_key(self, audio: np.ndarray, sr: int) -> str:
        """
        Detect musical key of audio.

        Args:
            audio: Audio array
            sr: Sample rate

        Returns:
            Key signature (e.g., 'C major', 'A minor')
        """
        chroma = librosa.feature.chroma_cqt(y=audio, sr=sr)
        chroma_avg = np.mean(chroma, axis=1)

        # Simple key detection based on chroma profile
        keys = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        key_idx = np.argmax(chroma_avg)

        # Determine major/minor (simplified)
        third = (key_idx + 4) % 12  # Major third
        minor_third = (key_idx + 3) % 12  # Minor third

        if chroma_avg[third] > chroma_avg[minor_third]:
            return f"{keys[key_idx]} major"
        else:
            return f"{keys[key_idx]} minor"

    def estimate_tempo(self, audio: np.ndarray, sr: int) -> float:
        """
        Estimate tempo (BPM) of audio.

        Args:
            audio: Audio array
            sr: Sample rate

        Returns:
            Tempo in BPM
        """
        tempo, _ = librosa.beat.beat_track(y=audio, sr=sr)
        return float(tempo)

    def separate_sources(self, audio: np.ndarray, sr: int) -> Dict[str, SeparatedStem]:
        """
        Coarsely split the signal into vocal/instrumental-style stems.

        This is not a full-blown stem-separation model. It approximates the
        user-requested workflow with HPSS, frequency-band masking, and Kalman
        smoothing so the rest of the pipeline can reason over stem candidates.
        """
        harmonic, percussive = librosa.effects.hpss(audio)
        vocals = self._extract_band(harmonic, sr, low_hz=180.0, high_hz=3200.0)
        accompaniment = self._extract_band(harmonic, sr, low_hz=80.0, high_hz=1800.0)
        bass = self._extract_band(harmonic, sr, low_hz=40.0, high_hz=280.0)

        stems = {
            "mix": SeparatedStem(name="mix", audio=audio),
            "vocals": SeparatedStem(name="vocals", audio=vocals),
            "accompaniment": SeparatedStem(name="accompaniment", audio=accompaniment),
            "bass": SeparatedStem(name="bass", audio=bass),
            "percussive": SeparatedStem(name="percussive", audio=percussive),
        }
        return stems

    def choose_melody_stem(
        self,
        stems: Dict[str, SeparatedStem],
        sr: int,
        detector,
        min_confidence: float = 0.55,
    ) -> MelodyStemSelection:
        """
        Pick the stem that most resembles a foreground melody line.
        """
        candidate_features = []

        for stem_name, stem in stems.items():
            if stem_name == "percussive":
                continue

            notes = detector.detect(stem.audio, sr, min_confidence=min_confidence)
            feature_row = self.melody_feature_extractor.extract(
                stem_name=stem_name,
                audio=stem.audio,
                sr=sr,
                notes=notes,
            )
            candidate_features.append(feature_row)

        stem_scores = self.melody_ranker.score_candidates(candidate_features)
        best_name = max(stem_scores, key=stem_scores.get, default="mix")
        for stem_name, score in stem_scores.items():
            stems[stem_name].score = score

        selected = stems[best_name]
        return MelodyStemSelection(
            stem_name=best_name,
            stem_audio=selected.audio,
            stem_scores=stem_scores,
        )

    def _extract_band(
        self,
        audio: np.ndarray,
        sr: int,
        low_hz: float,
        high_hz: float,
        n_fft: int = 2048,
        hop_length: int = 512,
    ) -> np.ndarray:
        """Apply a soft band mask with Kalman-smoothed frame energies."""
        stft = librosa.stft(audio, n_fft=n_fft, hop_length=hop_length)
        magnitude = np.abs(stft)
        phase = np.exp(1j * np.angle(stft))
        freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

        band_mask = (freqs >= low_hz) & (freqs <= high_hz)
        if not np.any(band_mask):
            return np.zeros_like(audio)

        frame_energy = magnitude[band_mask].mean(axis=0)
        smoothed_energy = self._kalman_filter_1d(frame_energy)
        normalized_energy = smoothed_energy / (np.max(smoothed_energy) + 1e-8)

        masked = np.zeros_like(stft, dtype=np.complex128)
        masked[band_mask, :] = (
            magnitude[band_mask, :] * normalized_energy[np.newaxis, :] * phase[band_mask, :]
        )
        reconstructed = librosa.istft(masked, hop_length=hop_length, length=len(audio))
        return librosa.util.normalize(reconstructed) if np.any(reconstructed) else reconstructed

    def _kalman_filter_1d(
        self,
        observations: np.ndarray,
        process_variance: float = 1e-4,
        measurement_variance: float = 1e-2,
    ) -> np.ndarray:
        """Smooth a 1D sequence with a simple scalar Kalman filter."""
        if observations.size == 0:
            return observations

        estimates = np.zeros_like(observations, dtype=float)
        estimates[0] = float(observations[0])
        estimation_error = 1.0

        for index in range(1, len(observations)):
            prediction = estimates[index - 1]
            estimation_error += process_variance

            kalman_gain = estimation_error / (estimation_error + measurement_variance)
            estimates[index] = prediction + kalman_gain * (observations[index] - prediction)
            estimation_error = (1.0 - kalman_gain) * estimation_error

        return estimates

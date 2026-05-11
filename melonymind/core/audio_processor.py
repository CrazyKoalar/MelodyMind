"""Audio preprocessing, rough source separation, and melody candidate search."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import librosa
import numpy as np
import soundfile as sf

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
        audio, sr = sf.read(audio_path, dtype="float32", always_2d=False)
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)
        if sr != self.sample_rate:
            audio = librosa.resample(audio, orig_sr=sr, target_sr=self.sample_rate)
            sr = self.sample_rate
        return audio, sr

    def normalize(self, audio: np.ndarray) -> np.ndarray:
        """Normalize audio to [-1, 1] range."""
        peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
        if peak <= 1e-8:
            return audio
        return audio / peak

    def trim_silence(self, audio: np.ndarray, top_db: int = 20) -> np.ndarray:
        """Trim silence from beginning and end."""
        if not len(audio):
            return audio

        threshold = float(np.max(np.abs(audio))) * (10.0 ** (-top_db / 20.0))
        active = np.flatnonzero(np.abs(audio) > threshold)
        if active.size == 0:
            return audio
        return audio[active[0] : active[-1] + 1]

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
        keys = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        if not len(audio):
            return "C major"

        spectrum = np.abs(np.fft.rfft(audio))
        freqs = np.fft.rfftfreq(len(audio), d=1.0 / sr)
        chroma_avg = np.zeros(12, dtype=float)

        valid = (freqs >= 80.0) & (freqs <= 5000.0) & (spectrum > 0)
        for freq, energy in zip(freqs[valid], spectrum[valid]):
            midi = int(round(69 + 12 * np.log2(freq / 440.0)))
            chroma_avg[midi % 12] += float(energy)

        if not np.any(chroma_avg):
            return "C major"

        key_idx = int(np.argmax(chroma_avg))

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
        if len(audio) < sr // 2:
            return 120.0

        frame_length = 1024
        hop_length = 512
        frame_count = 1 + max(0, (len(audio) - frame_length) // hop_length)
        if frame_count < 4:
            return 120.0

        energy = np.array(
            [
                np.sqrt(np.mean(audio[i * hop_length : i * hop_length + frame_length] ** 2))
                for i in range(frame_count)
            ],
            dtype=float,
        )
        onset_env = np.maximum(0.0, np.diff(energy, prepend=energy[0]))
        onset_env -= onset_env.mean()
        if np.max(np.abs(onset_env)) <= 1e-8:
            return 120.0

        autocorr = np.correlate(onset_env, onset_env, mode="full")[len(onset_env) - 1 :]
        min_bpm, max_bpm = 60.0, 200.0
        min_lag = max(1, int((60.0 / max_bpm) * sr / hop_length))
        max_lag = min(len(autocorr) - 1, int((60.0 / min_bpm) * sr / hop_length))
        if max_lag <= min_lag:
            return 120.0

        lag = min_lag + int(np.argmax(autocorr[min_lag : max_lag + 1]))
        return float(60.0 * sr / (lag * hop_length))

    def separate_sources(self, audio: np.ndarray, sr: int) -> Dict[str, SeparatedStem]:
        """
        Coarsely split the signal into vocal/instrumental-style stems.

        This is not a full-blown stem-separation model. It approximates the
        user-requested workflow with HPSS, frequency-band masking, and Kalman
        smoothing so the rest of the pipeline can reason over stem candidates.
        """
        vocals = self._extract_band(audio, sr, low_hz=180.0, high_hz=3200.0)
        accompaniment = self._extract_band(audio, sr, low_hz=80.0, high_hz=1800.0)
        bass = self._extract_band(audio, sr, low_hz=40.0, high_hz=280.0)
        percussive = audio - accompaniment

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
    ) -> np.ndarray:
        """Apply a frequency-band mask with Kalman-smoothed spectral energy."""
        if not len(audio):
            return audio

        spectrum = np.fft.rfft(audio)
        magnitude = np.abs(spectrum)
        phase = np.exp(1j * np.angle(spectrum))
        freqs = np.fft.rfftfreq(len(audio), d=1.0 / sr)
        band_mask = (freqs >= low_hz) & (freqs <= high_hz)
        if not np.any(band_mask):
            return np.zeros_like(audio)

        smoothed_magnitude = self._kalman_filter_1d(magnitude[band_mask])
        masked_spectrum = np.zeros_like(spectrum, dtype=np.complex128)
        masked_spectrum[band_mask] = smoothed_magnitude * phase[band_mask]

        reconstructed = np.fft.irfft(masked_spectrum, n=len(audio)).astype(audio.dtype)
        return self.normalize(reconstructed) if np.any(reconstructed) else reconstructed

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

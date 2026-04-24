"""Training pipeline for the melody stem ranker."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

import numpy as np

from ..core.audio_processor import AudioProcessor
from ..core.pitch_detector import DetectionMode, PitchDetector
from ..models.melody_ranker import (
    MelodyCandidateFeatures,
    MelodyFeatureExtractor,
    TrainableMelodyStemRanker,
)


@dataclass
class MelodyRankingSample:
    """One supervised song example for melody stem ranking."""

    audio_path: str
    target_stem_name: str


@dataclass
class MelodyRankingDataset:
    """Feature rows and labels prepared for model training."""

    feature_rows: List[MelodyCandidateFeatures]
    labels: List[int]
    sample_ids: List[str]

    @property
    def size(self) -> int:
        return len(self.feature_rows)


class MelodyRankerTrainer:
    """Prepare supervised data and fit a lightweight linear model."""

    def __init__(
        self,
        sample_rate: int = 22050,
        detector_mode: DetectionMode = DetectionMode.PYIN,
        min_confidence: float = 0.55,
    ):
        self.sample_rate = sample_rate
        self.detector = PitchDetector(mode=detector_mode)
        self.audio_processor = AudioProcessor(sample_rate=sample_rate)
        self.feature_extractor = MelodyFeatureExtractor()
        self.min_confidence = min_confidence

    def load_manifest(self, manifest_path: str | Path) -> List[MelodyRankingSample]:
        samples: List[MelodyRankingSample] = []
        for raw_line in Path(manifest_path).read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if "audio_path" not in payload or "target_stem_name" not in payload:
                continue
            samples.append(
                MelodyRankingSample(
                    audio_path=payload["audio_path"],
                    target_stem_name=payload["target_stem_name"],
                )
            )
        return samples

    def build_dataset(self, samples: Iterable[MelodyRankingSample]) -> MelodyRankingDataset:
        feature_rows: List[MelodyCandidateFeatures] = []
        labels: List[int] = []
        sample_ids: List[str] = []

        for sample in samples:
            audio, sr = self.audio_processor.load(sample.audio_path)
            audio = self.audio_processor.normalize(audio)
            audio = self.audio_processor.trim_silence(audio)
            stems = self.audio_processor.separate_sources(audio, sr)

            for stem_name, stem in stems.items():
                if stem_name == "percussive":
                    continue

                notes = self.detector.detect(stem.audio, sr, min_confidence=self.min_confidence)
                feature_rows.append(
                    self.feature_extractor.extract(
                        stem_name=stem_name,
                        audio=stem.audio,
                        sr=sr,
                        notes=notes,
                    )
                )
                labels.append(1 if stem_name == sample.target_stem_name else 0)
                sample_ids.append(sample.audio_path)

        return MelodyRankingDataset(
            feature_rows=feature_rows,
            labels=labels,
            sample_ids=sample_ids,
        )

    def fit(
        self,
        dataset: MelodyRankingDataset,
        learning_rate: float = 0.05,
        epochs: int = 400,
        l2: float = 1e-4,
    ) -> TrainableMelodyStemRanker:
        if dataset.size == 0:
            raise ValueError("training dataset is empty")

        vectors = np.vstack([row.as_vector() for row in dataset.feature_rows]).astype(float)
        labels = np.array(dataset.labels, dtype=float)
        feature_mean = vectors.mean(axis=0)
        feature_scale = vectors.std(axis=0)
        feature_scale[feature_scale < 1e-6] = 1.0
        normalized = (vectors - feature_mean) / feature_scale

        stem_names = sorted({row.stem_name for row in dataset.feature_rows})
        stem_index = {name: idx for idx, name in enumerate(stem_names)}
        stem_matrix = np.zeros((dataset.size, len(stem_names)), dtype=float)
        for row_index, row in enumerate(dataset.feature_rows):
            stem_matrix[row_index, stem_index[row.stem_name]] = 1.0

        weights = np.zeros(normalized.shape[1], dtype=float)
        stem_bias = np.zeros(len(stem_names), dtype=float)
        bias = 0.0

        for _ in range(epochs):
            logits = normalized @ weights + stem_matrix @ stem_bias + bias
            predictions = 1.0 / (1.0 + np.exp(-np.clip(logits, -30.0, 30.0)))
            errors = predictions - labels

            grad_w = (normalized.T @ errors) / dataset.size + l2 * weights
            grad_stem = (stem_matrix.T @ errors) / dataset.size
            grad_bias = float(errors.mean())

            weights -= learning_rate * grad_w
            stem_bias -= learning_rate * grad_stem
            bias -= learning_rate * grad_bias

        return TrainableMelodyStemRanker(
            feature_mean=feature_mean.tolist(),
            feature_scale=feature_scale.tolist(),
            weights=weights.tolist(),
            bias=float(bias),
            stem_bias={name: float(stem_bias[index]) for name, index in stem_index.items()},
        )

    def evaluate(
        self, model: TrainableMelodyStemRanker, dataset: MelodyRankingDataset
    ) -> dict:
        grouped_rows: Dict[str, List[MelodyCandidateFeatures]] = {}
        grouped_labels: Dict[str, List[int]] = {}
        for sample_id, row, label in zip(
            dataset.sample_ids, dataset.feature_rows, dataset.labels
        ):
            grouped_rows.setdefault(sample_id, []).append(row)
            grouped_labels.setdefault(sample_id, []).append(label)

        correct = 0
        for sample_id, rows in grouped_rows.items():
            labels = grouped_labels[sample_id]
            scores = model.score_candidates(rows)
            predicted = max(scores, key=scores.get)
            expected_index = int(np.argmax(labels))
            expected = rows[expected_index].stem_name
            if predicted == expected:
                correct += 1

        sample_count = max(len(grouped_rows), 1)
        return {
            "sample_count": len(grouped_rows),
            "candidate_rows": dataset.size,
            "top1_accuracy": correct / sample_count,
        }


def write_training_summary(summary_path: str | Path, metrics: Dict[str, float]) -> str:
    path = Path(summary_path)
    path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return str(path)

"""Tests for melody ranker training utilities."""

import json

import numpy as np

from melonymind.models.melody_ranker import (
    MelodyCandidateFeatures,
    TrainableMelodyStemRanker,
)
from melonymind.training.melody_ranker_trainer import (
    MelodyRankingDataset,
    MelodyRankerTrainer,
    write_training_summary,
)


def test_trainable_ranker_can_save_and_load(local_tmp_path):
    model = TrainableMelodyStemRanker(
        feature_mean=[0.0] * 8,
        feature_scale=[1.0] * 8,
        weights=[0.1] * 8,
        bias=0.2,
        stem_bias={"vocals": 0.5},
    )
    model_path = local_tmp_path / "ranker.json"

    model.save(model_path)
    loaded = TrainableMelodyStemRanker.load(model_path)

    scores = loaded.score_candidates(
        [
            MelodyCandidateFeatures("mix", 1, 0.2, 1.0, 0.1, 0.02, 0.1, 300.0, 0.2),
            MelodyCandidateFeatures("vocals", 4, 0.9, 12.0, 0.5, 0.2, 0.05, 1400.0, 0.8),
        ]
    )

    assert model_path.exists()
    assert scores["vocals"] > scores["mix"]


def test_trainer_load_manifest_reads_jsonl(local_tmp_path):
    manifest_path = local_tmp_path / "manifest.jsonl"
    manifest_path.write_text(
        '\n'.join(
            [
                json.dumps({"audio_path": "song_a.wav", "target_stem_name": "vocals"}),
                json.dumps({"audio_path": "song_b.wav", "target_stem_name": "mix"}),
            ]
        ),
        encoding="utf-8",
    )

    trainer = MelodyRankerTrainer()
    samples = trainer.load_manifest(manifest_path)

    assert len(samples) == 2
    assert samples[0].target_stem_name == "vocals"
    assert samples[1].audio_path == "song_b.wav"


def test_trainer_fit_and_evaluate_on_feature_dataset():
    trainer = MelodyRankerTrainer()
    dataset = MelodyRankingDataset(
        feature_rows=[
            MelodyCandidateFeatures("mix", 2, 0.2, 2.0, 0.1, 0.02, 0.12, 200.0, 0.1),
            MelodyCandidateFeatures("vocals", 9, 0.9, 11.0, 0.4, 0.12, 0.05, 1600.0, 0.8),
            MelodyCandidateFeatures("mix", 3, 0.3, 3.0, 0.1, 0.03, 0.14, 220.0, 0.2),
            MelodyCandidateFeatures("vocals", 10, 0.88, 13.0, 0.5, 0.11, 0.05, 1500.0, 0.85),
        ],
        labels=[0, 1, 0, 1],
        sample_ids=["a", "a", "b", "b"],
    )

    model = trainer.fit(dataset, learning_rate=0.1, epochs=300)
    metrics = trainer.evaluate(model, dataset)

    assert metrics["sample_count"] == 2
    assert metrics["top1_accuracy"] >= 1.0


def test_write_training_summary_creates_json(local_tmp_path):
    summary_path = local_tmp_path / "metrics.json"
    write_training_summary(summary_path, {"top1_accuracy": 0.75})

    payload = json.loads(summary_path.read_text(encoding="utf-8"))

    assert payload["top1_accuracy"] == 0.75

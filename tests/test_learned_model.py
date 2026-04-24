"""Tests for local learned-model artifacts and loading."""

import json

from melonymind.learned_model import (
    create_melody_ranker_artifact,
    load_melody_ranker_model,
)
from melonymind.models.melody_ranker import (
    MelodyCandidateFeatures,
    TrainableMelodyStemRanker,
)


def test_create_and_load_melody_ranker_artifact(local_tmp_path):
    model = TrainableMelodyStemRanker(
        feature_mean=[0.0] * 8,
        feature_scale=[1.0] * 8,
        weights=[0.1] * 8,
        bias=0.2,
        stem_bias={"vocals": 0.5},
    )
    artifact = create_melody_ranker_artifact(model, metadata={"trainer": "unit-test"})
    artifact_path = local_tmp_path / "melody_ranker_artifact.json"

    artifact.save(artifact_path)
    loaded = load_melody_ranker_model(artifact_path)

    scores = loaded.score_candidates(
        [
            MelodyCandidateFeatures("mix", 1, 0.2, 1.0, 0.1, 0.02, 0.1, 300.0, 0.2),
            MelodyCandidateFeatures("vocals", 4, 0.9, 12.0, 0.5, 0.2, 0.05, 1400.0, 0.8),
        ]
    )

    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert payload["task"] == "melody_stem_ranking"
    assert payload["metadata"]["trainer"] == "unit-test"
    assert scores["vocals"] > scores["mix"]


def test_load_melody_ranker_model_supports_legacy_weights(local_tmp_path):
    legacy_path = local_tmp_path / "legacy_ranker.json"
    legacy_path.write_text(
        json.dumps(
            {
                "feature_mean": [0.0] * 8,
                "feature_scale": [1.0] * 8,
                "weights": [0.1] * 8,
                "bias": 0.0,
                "stem_bias": {"mix": 0.0},
            }
        ),
        encoding="utf-8",
    )

    loaded = load_melody_ranker_model(legacy_path)

    assert isinstance(loaded, TrainableMelodyStemRanker)

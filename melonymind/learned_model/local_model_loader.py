"""Load and save learned models from local artifact files."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict

from ..models.melody_ranker import TrainableMelodyStemRanker


@dataclass
class LocalModelArtifact:
    """Portable on-disk artifact description for locally trained models."""

    task: str
    model_type: str
    format_version: int = 1
    weights: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def save(self, output_path: str | Path) -> str:
        path = Path(output_path)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return str(path)

    @classmethod
    def load(cls, artifact_path: str | Path) -> "LocalModelArtifact":
        payload = json.loads(Path(artifact_path).read_text(encoding="utf-8"))
        return cls(**payload)


def create_melody_ranker_artifact(
    model: TrainableMelodyStemRanker, metadata: Dict[str, Any] | None = None
) -> LocalModelArtifact:
    return LocalModelArtifact(
        task="melody_stem_ranking",
        model_type="linear_ranker",
        weights={
            "feature_mean": model.feature_mean,
            "feature_scale": model.feature_scale,
            "weights": model.weights,
            "bias": model.bias,
            "stem_bias": model.stem_bias,
        },
        metadata=metadata or {},
    )


def load_melody_ranker_model(model_path: str | Path) -> TrainableMelodyStemRanker:
    """
    Load a melody ranker from either:

    1. the new learned-model artifact format
    2. the legacy direct TrainableMelodyStemRanker JSON payload
    """
    payload = json.loads(Path(model_path).read_text(encoding="utf-8"))

    if "task" in payload and "weights" in payload:
        if payload.get("task") != "melody_stem_ranking":
            raise ValueError(f"unsupported model task: {payload.get('task')}")
        weights = payload["weights"]
        return TrainableMelodyStemRanker(**weights)

    return TrainableMelodyStemRanker(**payload)

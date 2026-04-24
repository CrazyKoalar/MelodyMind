"""Training-oriented notes and schemas for future learned models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class MelodyRankingTrainingExample:
    """
    One song-level training example for melody stem ranking.

    target_stem_name is the stem that contains the lead melody, usually
    one of: vocals, lead, melody, solo, or a manually annotated stem id.
    """

    audio_path: str
    candidate_stem_names: List[str]
    target_stem_name: str


@dataclass
class ChordPredictionTrainingExample:
    """
    One bar-level or phrase-level training example for harmony prediction.

    melody_midi_pitches stores the melody notes that occur in the window,
    while target_root/target_quality hold the gold chord label.
    """

    key: str
    tempo: float
    time_signature: str
    melody_midi_pitches: List[int]
    target_root: int
    target_quality: str


TRAINING_GUIDE = {
    "melody_ranker": {
        "task": "classify or rank which separated stem carries the foreground melody",
        "inputs": [
            "candidate stem audio",
            "pitch track or note events per stem",
            "energy and spectral features",
        ],
        "labels": [
            "gold melody stem id",
            "optional pairwise ranking labels between stems",
        ],
        "recommended_data": [
            "multitrack songs with isolated vocals/lead stems",
            "synthetic mixtures created from melody + accompaniment stems",
            "manual annotations marking the lead stem after rough separation",
        ],
    },
    "chord_predictor": {
        "task": "predict chord root and quality from melody windows",
        "inputs": [
            "bar or phrase melody notes",
            "key",
            "tempo",
            "time signature",
        ],
        "labels": [
            "target chord root",
            "target chord quality",
        ],
        "recommended_data": [
            "MIDI files with melody and chord annotations",
            "lead sheets",
            "paired MusicXML or MIDI piano arrangements",
        ],
    },
}

"""Tests for the melody-selection and arrangement pipeline."""

import numpy as np

from melonymind.core.arranger import PianoArranger
from melonymind.core.audio_processor import AudioProcessor
from melonymind.models.chord_predictor import RuleBasedChordPredictor
from melonymind.models.melody_ranker import (
    HeuristicMelodyStemRanker,
    MelodyCandidateFeatures,
    MelodyFeatureExtractor,
)
from melonymind.core.pitch_detector import NoteEvent


class DummyDetector:
    """Return predefined note sequences per stem identity."""

    def detect(self, audio, sr: int, min_confidence: float = 0.5):
        if np.max(audio) > 0.7:
            return [
                NoteEvent(pitch=72.0, start_time=0.0, end_time=0.6, confidence=0.9),
                NoteEvent(pitch=76.0, start_time=0.6, end_time=1.2, confidence=0.85),
            ]
        return [NoteEvent(pitch=60.0, start_time=0.0, end_time=0.2, confidence=0.4)]


def test_kalman_filter_preserves_length():
    processor = AudioProcessor()
    smoothed = processor._kalman_filter_1d(np.array([0.0, 1.0, 0.5, 0.75]))
    assert len(smoothed) == 4
    assert smoothed[1] > smoothed[0]


def test_choose_melody_stem_prefers_more_melodic_candidate():
    processor = AudioProcessor()
    stems = {
        "mix": type("Stem", (), {"name": "mix", "audio": np.array([0.2, 0.3, 0.2]), "score": 0.0})(),
        "vocals": type("Stem", (), {"name": "vocals", "audio": np.array([0.1, 0.9, 0.2]), "score": 0.0})(),
    }

    selection = processor.choose_melody_stem(stems, 22050, DummyDetector())

    assert selection.stem_name == "vocals"
    assert selection.stem_scores["vocals"] > selection.stem_scores["mix"]


def test_arranger_generates_chords_and_accompaniment():
    arranger = PianoArranger()
    melody = [
        NoteEvent(pitch=60.0, start_time=0.0, end_time=0.5, confidence=0.9),
        NoteEvent(pitch=64.0, start_time=0.5, end_time=1.0, confidence=0.9),
        NoteEvent(pitch=67.0, start_time=1.0, end_time=1.5, confidence=0.9),
    ]

    arrangement = arranger.create_arrangement(melody, key="C major", tempo=120.0)

    assert arrangement.chords
    assert arrangement.accompaniment
    assert any(note.pitch < 60 for note in arrangement.accompaniment)


def test_melody_feature_extractor_returns_expected_feature_row():
    extractor = MelodyFeatureExtractor()
    notes = [NoteEvent(pitch=72.0, start_time=0.0, end_time=0.5, confidence=0.9)]

    features = extractor.extract("vocals", np.array([0.0, 0.5, -0.1, 0.3]), 22050, notes)

    assert features.stem_name == "vocals"
    assert features.note_count == 1
    assert features.mean_confidence > 0.0
    assert features.as_vector().shape == (8,)


def test_heuristic_ranker_prefers_more_confident_candidate():
    ranker = HeuristicMelodyStemRanker()
    scores = ranker.score_candidates(
        [
            MelodyCandidateFeatures("mix", 4, 0.3, 4.0, 0.1, 0.04, 0.2, 400.0, 0.1),
            MelodyCandidateFeatures("vocals", 10, 0.9, 14.0, 0.5, 0.15, 0.1, 1800.0, 0.8),
        ]
    )

    assert scores["vocals"] > scores["mix"]


def test_rule_based_chord_predictor_returns_one_chord_per_context():
    predictor = RuleBasedChordPredictor()
    contexts = [
        type(
            "Context",
            (),
            {
                "key": "C major",
                "tempo": 120.0,
                "time_signature": "4/4",
                "start_time": 0.0,
                "end_time": 2.0,
                "melody_notes": [
                    NoteEvent(pitch=60.0, start_time=0.0, end_time=0.5, confidence=0.9),
                    NoteEvent(pitch=64.0, start_time=0.5, end_time=1.0, confidence=0.9),
                ],
                "candidate_roots": [0, 2, 4, 5, 7, 9, 11],
                "candidate_qualities": ["major", "minor", "minor", "major", "major", "minor", "minor"],
            },
        )()
    ]

    chords = predictor.predict(contexts)

    assert len(chords) == 1
    assert chords[0].quality in {"major", "minor"}

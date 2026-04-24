"""Interfaces and baseline models for melody-conditioned chord prediction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable, List, Protocol

from ..core.pitch_detector import NoteEvent

if TYPE_CHECKING:
    from ..core.arranger import ChordEvent


@dataclass
class HarmonyContext:
    """Model input for one harmony decision window."""

    key: str
    tempo: float
    time_signature: str
    start_time: float
    end_time: float
    melody_notes: List[NoteEvent]
    candidate_roots: List[int]
    candidate_qualities: List[str]


class ChordPredictor(Protocol):
    """Protocol for a model that proposes one chord for each bar/window."""

    def predict(self, contexts: Iterable[HarmonyContext]) -> List["ChordEvent"]:
        """Return one chord per provided context."""


class RuleBasedChordPredictor:
    """Default harmony predictor that follows diatonic coverage heuristics."""

    def predict(self, contexts: Iterable[HarmonyContext]) -> List["ChordEvent"]:
        from ..core.arranger import ChordEvent

        chords: List[ChordEvent] = []
        for context in contexts:
            preferred_root = context.candidate_roots[0] if context.candidate_roots else 0
            best_root = preferred_root
            best_quality = (
                context.candidate_qualities[0] if context.candidate_qualities else "major"
            )
            best_score = float("-inf")
            pitch_classes = [int(round(note.pitch)) % 12 for note in context.melody_notes]

            for root, quality in zip(context.candidate_roots, context.candidate_qualities):
                intervals = [0, 4, 7] if quality == "major" else [0, 3, 7]
                chord_tones = {(root + interval) % 12 for interval in intervals}
                coverage = sum(1 for pitch_class in pitch_classes if pitch_class in chord_tones)
                root_bonus = 1 if root == preferred_root else 0
                score = coverage * 2 + root_bonus
                if score > best_score:
                    best_score = score
                    best_root = root
                    best_quality = quality

            chords.append(
                ChordEvent(
                    root=best_root,
                    quality=best_quality,
                    start_time=context.start_time,
                    end_time=context.end_time,
                )
            )

        return chords

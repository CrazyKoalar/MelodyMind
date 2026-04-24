"""Melody-first piano arrangement helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from ..models.chord_predictor import HarmonyContext, RuleBasedChordPredictor
from .pitch_detector import NoteEvent


@dataclass
class ChordEvent:
    """A harmony block inferred for a span of melody."""

    root: int
    quality: str
    start_time: float
    end_time: float

    @property
    def pitches(self) -> List[int]:
        intervals = [0, 4, 7] if self.quality == "major" else [0, 3, 7]
        return [self.root + interval for interval in intervals]


@dataclass
class PianoArrangement:
    """A simple piano reduction with melody and accompaniment voices."""

    melody: List[NoteEvent]
    accompaniment: List[NoteEvent]
    chords: List[ChordEvent]


class PianoArranger:
    """Infer basic chords from a melody and voice them for piano."""

    def __init__(self, chord_predictor=None):
        self.chord_predictor = chord_predictor or RuleBasedChordPredictor()

    def create_arrangement(
        self,
        melody: Sequence[NoteEvent],
        key: str,
        tempo: float,
        time_signature: str = "4/4",
    ) -> PianoArrangement:
        chords = self.infer_chords(melody, key=key, tempo=tempo, time_signature=time_signature)
        accompaniment = self.render_accompaniment(chords, tempo=tempo)
        return PianoArrangement(
            melody=list(melody),
            accompaniment=accompaniment,
            chords=chords,
        )

    def infer_chords(
        self,
        melody: Sequence[NoteEvent],
        key: str,
        tempo: float,
        time_signature: str = "4/4",
    ) -> List[ChordEvent]:
        """Infer one chord per bar from melody notes using a predictor interface."""
        if not melody:
            return []

        beats_per_bar = int(time_signature.split("/")[0])
        bar_duration = beats_per_bar * (60.0 / max(tempo, 1.0))
        song_end = max(note.end_time for note in melody)
        bar_count = max(1, int(song_end / bar_duration + 0.999))

        key_root, mode = self._parse_key(key)
        scale_roots = self._scale_roots(key_root, mode)
        qualities = ["major", "minor", "minor", "major", "major", "minor", "minor"]
        if mode == "minor":
            qualities = ["minor", "minor", "major", "minor", "minor", "major", "major"]

        contexts: List[HarmonyContext] = []
        for bar_index in range(bar_count):
            start = bar_index * bar_duration
            end = start + bar_duration
            bar_notes = [
                note for note in melody if note.start_time < end and note.end_time > start
            ]
            contexts.append(
                HarmonyContext(
                    key=key,
                    tempo=tempo,
                    time_signature=time_signature,
                    start_time=start,
                    end_time=end,
                    melody_notes=list(bar_notes),
                    candidate_roots=scale_roots,
                    candidate_qualities=qualities,
                )
            )

        return self.chord_predictor.predict(contexts)

    def render_accompaniment(
        self, chords: Sequence[ChordEvent], tempo: float
    ) -> List[NoteEvent]:
        """Voice block chords for the right hand and roots for the left hand."""
        accompaniment: List[NoteEvent] = []
        beat_duration = 60.0 / max(tempo, 1.0)

        for chord in chords:
            left_root = chord.root + 36
            right_pitches = [pitch + 60 for pitch in chord.pitches]

            accompaniment.append(
                NoteEvent(
                    pitch=float(left_root),
                    start_time=chord.start_time,
                    end_time=min(chord.end_time, chord.start_time + beat_duration * 2),
                    confidence=0.75,
                )
            )

            for pitch in right_pitches:
                accompaniment.append(
                    NoteEvent(
                        pitch=float(pitch),
                        start_time=chord.start_time,
                        end_time=chord.end_time,
                        confidence=0.7,
                    )
                )

        return accompaniment

    def _parse_key(self, key: str) -> tuple[int, str]:
        tonic_name, mode = key.split()
        pitch_map = {
            "C": 0,
            "C#": 1,
            "Db": 1,
            "D": 2,
            "D#": 3,
            "Eb": 3,
            "E": 4,
            "F": 5,
            "F#": 6,
            "Gb": 6,
            "G": 7,
            "G#": 8,
            "Ab": 8,
            "A": 9,
            "A#": 10,
            "Bb": 10,
            "B": 11,
        }
        return pitch_map.get(tonic_name, 0), mode

    def _scale_roots(self, key_root: int, mode: str) -> List[int]:
        intervals = [0, 2, 4, 5, 7, 9, 11] if mode == "major" else [0, 2, 3, 5, 7, 8, 10]
        return [((key_root + interval) % 12) for interval in intervals]

"""MIDI export helpers for melody and piano arrangement outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pretty_midi

from .arranger import PianoArrangement
from .pitch_detector import NoteEvent


class MidiExporter:
    """Build MIDI files from melody notes and piano arrangements."""

    def export_melody(self, notes: Iterable[NoteEvent], output_path: str, tempo: float) -> str:
        midi = pretty_midi.PrettyMIDI(initial_tempo=max(1.0, float(tempo)))
        instrument = pretty_midi.Instrument(program=0, name="Lead Melody")
        instrument.notes.extend(self._to_pretty_notes(notes))
        midi.instruments.append(instrument)
        midi.write(output_path)
        return output_path

    def export_piano_arrangement(
        self, arrangement: PianoArrangement, output_path: str, tempo: float
    ) -> str:
        midi = pretty_midi.PrettyMIDI(initial_tempo=max(1.0, float(tempo)))

        melody_track = pretty_midi.Instrument(program=0, name="Melody")
        melody_track.notes.extend(self._to_pretty_notes(arrangement.melody, velocity=100))

        piano_track = pretty_midi.Instrument(program=0, name="Piano Accompaniment")
        piano_track.notes.extend(
            self._to_pretty_notes(arrangement.accompaniment, velocity=72)
        )

        midi.instruments.extend([melody_track, piano_track])
        midi.write(output_path)
        return output_path

    def _to_pretty_notes(
        self, notes: Iterable[NoteEvent], velocity: int = 90
    ) -> list[pretty_midi.Note]:
        pretty_notes = []
        for note in notes:
            pretty_notes.append(
                pretty_midi.Note(
                    velocity=velocity,
                    pitch=int(round(note.pitch)),
                    start=max(0.0, float(note.start_time)),
                    end=max(float(note.end_time), float(note.start_time) + 0.05),
                )
            )
        return pretty_notes

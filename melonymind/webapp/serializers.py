"""Wire-format serializers for NoteEvent and stem selection structures."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from ..core.pitch_detector import NoteEvent


def note_event_to_dict(note: NoteEvent, note_id: int | None = None) -> Dict[str, Any]:
    """Convert a NoteEvent to the JSON wire format.

    pitch is rounded to int here — this is the only path notes take to the frontend,
    which edits integer semitones. Float pitches would cause subtle drift on re-save.
    """
    payload: Dict[str, Any] = {
        "pitch": int(round(note.pitch)),
        "start": float(note.start_time),
        "end": float(note.end_time),
        "confidence": float(note.confidence),
    }
    if note_id is not None:
        payload["id"] = int(note_id)
    return payload


def notes_to_payload(notes: Iterable[NoteEvent]) -> List[Dict[str, Any]]:
    """Serialize a sequence of NoteEvents with stable client-facing ids."""
    return [note_event_to_dict(note, note_id=index) for index, note in enumerate(notes)]


def note_event_from_dict(payload: Dict[str, Any]) -> NoteEvent:
    """Build a NoteEvent from a wire-format dict.

    Accepts the int pitch from the editor; we keep storing float for consistency
    with the rest of the codebase, but the int round-trip is lossless.
    """
    return NoteEvent(
        pitch=float(payload["pitch"]),
        start_time=float(payload["start"]),
        end_time=float(payload["end"]),
        confidence=float(payload.get("confidence", 1.0)),
    )


def notes_from_payload(payload: Iterable[Dict[str, Any]]) -> List[NoteEvent]:
    return [note_event_from_dict(item) for item in payload]

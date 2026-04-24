"""Core audio processing modules."""

from .arranger import ChordEvent, PianoArrangement, PianoArranger
from .audio_processor import AudioProcessor, MelodyStemSelection, SeparatedStem
from .midi_exporter import MidiExporter
from .pitch_detector import DetectionMode, NoteEvent, PitchDetector

__all__ = [
    "AudioProcessor",
    "ChordEvent",
    "DetectionMode",
    "MelodyStemSelection",
    "MidiExporter",
    "NoteEvent",
    "PianoArrangement",
    "PianoArranger",
    "PitchDetector",
    "SeparatedStem",
]

from .audio_processor import AudioProcessor
from .pitch_detector import PitchDetector

__all__ = ["AudioProcessor", "PitchDetector"]

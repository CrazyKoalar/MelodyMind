"""
MelodyMind - AI-powered music transcription library

Convert audio to sheet music for piano, guitar, and more.
"""

__version__ = "0.1.0"
__author__ = "CrazyKoalar"
__email__ = ""

from .core.audio_processor import AudioProcessor
from .core.arranger import PianoArranger
from .core.midi_exporter import MidiExporter
from .core.pitch_detector import PitchDetector
from .learned_model import load_melody_ranker_model
from .notation.sheet_generator import SheetGenerator
from .notation.jianpu_generator import JianpuGenerator

__all__ = [
    "AudioProcessor",
    "MidiExporter",
    "PianoArranger",
    "PitchDetector", 
    "load_melody_ranker_model",
    "SheetGenerator",
    "JianpuGenerator",
]

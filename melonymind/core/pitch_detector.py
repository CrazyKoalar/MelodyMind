"""
Pitch detection using various methods including Basic Pitch.
"""

import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class DetectionMode(Enum):
    """Available pitch detection modes."""
    BASIC_PITCH = "basic_pitch"
    CREPE = "crepe"
    PYIN = "pyin"


@dataclass
class NoteEvent:
    """Represents a detected note event."""
    pitch: float  # MIDI note number
    start_time: float  # seconds
    end_time: float  # seconds
    confidence: float  # 0-1
    
    @property
    def duration(self) -> float:
        """Note duration in seconds."""
        return self.end_time - self.start_time
    
    @property
    def note_name(self) -> str:
        """Convert MIDI pitch to note name."""
        notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        octave = int(self.pitch // 12) - 1
        note_idx = int(self.pitch % 12)
        return f"{notes[note_idx]}{octave}"


class PitchDetector:
    """Detect pitch from audio using multiple backends."""
    
    def __init__(self, mode: DetectionMode = DetectionMode.BASIC_PITCH):
        """
        Initialize pitch detector.
        
        Args:
            mode: Detection mode to use
        """
        self.mode = mode
        self._model = None
    
    def _load_basic_pitch(self):
        """Lazy load Basic Pitch model."""
        if self._model is None:
            try:
                from basic_pitch import ICASSP_2022_MODEL_PATH
                from basic_pitch.inference import predict
                self._model = ICASSP_2022_MODEL_PATH
                self._predict = predict
            except ImportError:
                raise ImportError(
                    "basic-pitch not installed. "
                    "Install with: pip install basic-pitch"
                )
        return self._model, self._predict
    
    def detect(
        self, 
        audio: np.ndarray, 
        sr: int,
        min_confidence: float = 0.5
    ) -> List[NoteEvent]:
        """
        Detect pitch from audio.
        
        Args:
            audio: Audio array
            sr: Sample rate
            min_confidence: Minimum confidence threshold
            
        Returns:
            List of detected note events
        """
        if self.mode == DetectionMode.BASIC_PITCH:
            return self._detect_basic_pitch(audio, sr, min_confidence)
        elif self.mode == DetectionMode.PYIN:
            return self._detect_pyin(audio, sr, min_confidence)
        else:
            raise NotImplementedError(f"Mode {self.mode} not implemented")
    
    def _detect_basic_pitch(
        self, 
        audio: np.ndarray, 
        sr: int,
        min_confidence: float
    ) -> List[NoteEvent]:
        """Detect using Basic Pitch."""
        self._load_basic_pitch()
        
        # Basic Pitch expects specific input format
        # This is a placeholder - actual implementation would use basic_pitch.predict
        # For now, return empty list as placeholder
        
        # TODO: Implement actual Basic Pitch integration
        # model_output, midi_data, note_events = self._predict(audio)
        
        return []
    
    def _detect_pyin(
        self, 
        audio: np.ndarray, 
        sr: int,
        min_confidence: float
    ) -> List[NoteEvent]:
        """Detect using pYIN algorithm via librosa."""
        import librosa
        
        f0, voiced_flag, voiced_probs = librosa.pyin(
            audio, 
            fmin=librosa.note_to_hz('C2'),
            fmax=librosa.note_to_hz('C7'),
            sr=sr
        )
        
        notes = []
        times = librosa.times_like(f0, sr=sr)
        
        # Convert continuous pitch to note events
        current_note = None
        note_start = 0
        
        for i, (time, pitch, is_voiced, conf) in enumerate(
            zip(times, f0, voiced_flag, voiced_probs)
        ):
            if not is_voiced or conf < min_confidence:
                if current_note is not None:
                    notes.append(NoteEvent(
                        pitch=current_note,
                        start_time=note_start,
                        end_time=time,
                        confidence=conf
                    ))
                    current_note = None
                continue
            
            midi_pitch = librosa.hz_to_midi(pitch)
            
            if current_note is None:
                current_note = midi_pitch
                note_start = time
            elif abs(midi_pitch - current_note) > 0.5:  # Pitch changed
                notes.append(NoteEvent(
                    pitch=current_note,
                    start_time=note_start,
                    end_time=time,
                    confidence=conf
                ))
                current_note = midi_pitch
                note_start = time
        
        # Close final note
        if current_note is not None and len(times) > 0:
            notes.append(NoteEvent(
                pitch=current_note,
                start_time=note_start,
                end_time=times[-1],
                confidence=voiced_probs[-1]
            ))
        
        return notes
    
    def quantize_notes(
        self, 
        notes: List[NoteEvent], 
        bpm: float = 120
    ) -> List[NoteEvent]:
        """
        Quantize note timings to musical grid.
        
        Args:
            notes: List of note events
            bpm: Tempo for quantization
            
        Returns:
            Quantized notes
        """
        beat_duration = 60.0 / bpm
        
        quantized = []
        for note in notes:
            # Quantize to nearest 16th note
            grid = beat_duration / 4
            start_q = round(note.start_time / grid) * grid
            end_q = round(note.end_time / grid) * grid
            
            quantized.append(NoteEvent(
                pitch=round(note.pitch),
                start_time=start_q,
                end_time=max(end_q, start_q + grid),
                confidence=note.confidence
            ))
        
        return quantized

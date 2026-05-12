"""
Pitch detection using librosa pYIN (default), optional Basic Pitch, legacy spectral peak.
"""

import numpy as np
import librosa
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum


class DetectionMode(Enum):
    """Available pitch detection modes."""

    PYIN = "pyin"
    """Probabilistic YIN via librosa — best default for monophonic vocal/instrument stems."""

    SPECTRAL_PEAK = "spectral_peak"
    """Fast FFT-peak tracker; rougher than pYIN, kept for debugging."""

    BASIC_PITCH = "basic_pitch"
    CREPE = "crepe"


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

    def __init__(self, mode: DetectionMode = DetectionMode.PYIN):
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
        if self.mode == DetectionMode.PYIN:
            return self._detect_pyin(audio, sr, min_confidence)
        if self.mode == DetectionMode.SPECTRAL_PEAK:
            return self._detect_spectral_peak(audio, sr, min_confidence)
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
        min_confidence: float,
    ) -> List[NoteEvent]:
        """Monophonic F0 with librosa.pyin (probabilistic YIN)."""
        y = np.asarray(audio, dtype=float)
        if y.ndim > 1:
            y = np.mean(y, axis=1)
        if y.size == 0:
            return []

        frame_length = 2048
        hop_length = 512
        if y.size < frame_length:
            return []

        fmin = float(librosa.note_to_hz("C2"))
        fmax = float(librosa.note_to_hz("C7"))
        f0_hz, voiced_flag, voiced_probs = librosa.pyin(
            y,
            fmin=fmin,
            fmax=fmax,
            sr=sr,
            frame_length=frame_length,
            hop_length=hop_length,
        )
        times = librosa.frames_to_time(
            np.arange(len(f0_hz)), sr=sr, hop_length=hop_length
        )
        hop_sec = hop_length / float(sr)

        notes: List[NoteEvent] = []
        current_midi: Optional[float] = None
        note_start = 0.0
        note_conf_sum = 0.0
        note_conf_n = 0

        def flush_note(end_t: float, last_conf: float) -> None:
            nonlocal current_midi, note_conf_sum, note_conf_n
            if current_midi is None or end_t <= note_start:
                return
            conf = (
                float(note_conf_sum / max(note_conf_n, 1))
                if note_conf_n
                else last_conf
            )
            notes.append(
                NoteEvent(
                    pitch=current_midi,
                    start_time=note_start,
                    end_time=end_t,
                    confidence=conf,
                )
            )
            current_midi = None
            note_conf_sum = 0.0
            note_conf_n = 0

        for t, hz, vflag, vprob in zip(times, f0_hz, voiced_flag, voiced_probs):
            conf = float(vprob) if vprob is not None and np.isfinite(vprob) else 0.0
            voiced = bool(vflag) and conf >= min_confidence and hz is not None and np.isfinite(hz) and hz > 0

            if not voiced:
                flush_note(t, conf)
                continue

            midi_pitch = float(69.0 + 12.0 * np.log2(float(hz) / 440.0))

            if current_midi is None:
                current_midi = midi_pitch
                note_start = t
                note_conf_sum = conf
                note_conf_n = 1
            elif abs(midi_pitch - current_midi) > 0.5:
                flush_note(t, conf)
                current_midi = midi_pitch
                note_start = t
                note_conf_sum = conf
                note_conf_n = 1
            else:
                note_conf_sum += conf
                note_conf_n += 1

        if current_midi is not None and times.size > 0:
            notes.append(
                NoteEvent(
                    pitch=current_midi,
                    start_time=note_start,
                    end_time=float(times[-1]) + hop_sec,
                    confidence=float(note_conf_sum / max(note_conf_n, 1)),
                )
            )

        return notes

    def _detect_spectral_peak(
        self,
        audio: np.ndarray,
        sr: int,
        min_confidence: float,
    ) -> List[NoteEvent]:
        """Legacy frame-wise spectral peak tracker."""
        frame_length = 2048
        hop_length = 512
        if len(audio) < frame_length:
            frame_length = max(256, int(2 ** np.floor(np.log2(max(len(audio), 1)))))
            hop_length = max(64, frame_length // 4)

        if len(audio) < frame_length:
            return []

        fmin = 65.406  # C2
        fmax = 2093.005  # C7
        freqs = np.fft.rfftfreq(frame_length, d=1.0 / sr)
        valid = (freqs >= fmin) & (freqs <= fmax)

        f0 = []
        voiced_flag = []
        voiced_probs = []
        times = []

        window = np.hanning(frame_length)
        frame_count = 1 + max(0, (len(audio) - frame_length) // hop_length)
        global_peak = 1e-8

        spectra = []
        for frame_index in range(frame_count):
            start = frame_index * hop_length
            frame = audio[start : start + frame_length] * window
            spectrum = np.abs(np.fft.rfft(frame))
            spectra.append(spectrum)
            if np.any(valid):
                global_peak = max(global_peak, float(np.max(spectrum[valid])))

        for frame_index, spectrum in enumerate(spectra):
            band = spectrum[valid]
            time = frame_index * hop_length / sr
            times.append(time)

            if band.size == 0:
                f0.append(np.nan)
                voiced_flag.append(False)
                voiced_probs.append(0.0)
                continue

            local_index = int(np.argmax(band))
            peak = float(band[local_index])
            confidence = float(np.clip(peak / global_peak, 0.0, 1.0))
            freq = float(freqs[valid][local_index])

            f0.append(freq)
            voiced_flag.append(confidence >= min_confidence)
            voiced_probs.append(confidence)

        notes = []

        current_note = None
        note_start = 0

        for time, pitch, is_voiced, conf in zip(times, f0, voiced_flag, voiced_probs):
            if not is_voiced or conf < min_confidence:
                if current_note is not None:
                    notes.append(
                        NoteEvent(
                            pitch=current_note,
                            start_time=note_start,
                            end_time=time,
                            confidence=conf,
                        )
                    )
                    current_note = None
                continue

            midi_pitch = 69 + 12 * np.log2(pitch / 440.0)

            if current_note is None:
                current_note = midi_pitch
                note_start = time
            elif abs(midi_pitch - current_note) > 0.5:
                notes.append(
                    NoteEvent(
                        pitch=current_note,
                        start_time=note_start,
                        end_time=time,
                        confidence=conf,
                    )
                )
                current_note = midi_pitch
                note_start = time

        if current_note is not None and len(times) > 0:
            notes.append(
                NoteEvent(
                    pitch=current_note,
                    start_time=note_start,
                    end_time=times[-1] + hop_length / sr,
                    confidence=voiced_probs[-1],
                )
            )

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

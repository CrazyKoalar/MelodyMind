"""
Wrapper for Spotify Basic Pitch model.
"""

from typing import List, Tuple, Optional
import numpy as np


class BasicPitchModel:
    """
    Wrapper for Basic Pitch transcription model.
    
    Basic Pitch is a lightweight audio-to-MIDI transcription model
    developed by Spotify.
    """
    
    def __init__(self):
        """Initialize Basic Pitch model."""
        self._model = None
        self._predict_fn = None
    
    def _load_model(self):
        """Lazy load the model."""
        if self._model is None:
            try:
                from basic_pitch import ICASSP_2022_MODEL_PATH
                from basic_pitch.inference import predict
                self._model = ICASSP_2022_MODEL_PATH
                self._predict_fn = predict
            except ImportError:
                raise ImportError(
                    "basic-pitch is required. "
                    "Install with: pip install basic-pitch"
                )
    
    def transcribe(
        self, 
        audio_path: str,
        onset_threshold: float = 0.5,
        frame_threshold: float = 0.3,
        min_note_length: float = 58.0,
        min_frequency: Optional[float] = None,
        max_frequency: Optional[float] = None,
    ) -> dict:
        """
        Transcribe audio to MIDI using Basic Pitch.
        
        Args:
            audio_path: Path to audio file
            onset_threshold: Confidence threshold for note onsets
            frame_threshold: Confidence threshold for note frames
            min_note_length: Minimum note length in milliseconds
            min_frequency: Minimum frequency to detect
            max_frequency: Maximum frequency to detect
            
        Returns:
            Dictionary containing:
            - 'midi': pretty_midi.PrettyMIDI object
            - 'notes': List of note events with pitch, start, end, confidence
        """
        self._load_model()
        
        model_output, midi_data, note_events = self._predict_fn(
            audio_path,
            onset_threshold=onset_threshold,
            frame_threshold=frame_threshold,
            minimum_note_length=min_note_length,
            minimum_frequency=min_frequency,
            maximum_frequency=max_frequency,
        )
        
        # Convert to standardized format
        notes = []
        for pitch, start, end, confidence, _ in note_events:
            notes.append({
                'pitch': int(pitch),
                'start': float(start),
                'end': float(end),
                'confidence': float(confidence),
            })
        
        return {
            'midi': midi_data,
            'notes': notes,
            'model_output': model_output,
        }
    
    def transcribe_array(
        self,
        audio: np.ndarray,
        sr: int = 22050,
        **kwargs
    ) -> dict:
        """
        Transcribe audio array to MIDI.
        
        Args:
            audio: Audio array
            sr: Sample rate
            **kwargs: Additional arguments for transcribe()
            
        Returns:
            Same as transcribe()
        """
        import soundfile as sf
        import tempfile
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            sf.write(f.name, audio, sr)
            return self.transcribe(f.name, **kwargs)
    
    @staticmethod
    def is_available() -> bool:
        """Check if Basic Pitch is installed."""
        try:
            import basic_pitch
            return True
        except ImportError:
            return False
    
    @staticmethod
    def get_model_info() -> dict:
        """Get information about the model."""
        return {
            'name': 'Basic Pitch',
            'version': 'ICASSP 2022',
            'developer': 'Spotify',
            'description': 'Lightweight audio-to-MIDI transcription model',
            'paper': 'https://arxiv.org/abs/2203.09893',
            'license': 'Apache 2.0',
        }

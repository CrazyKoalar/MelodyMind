"""
Audio preprocessing and utilities.
"""

import numpy as np
import librosa
from typing import Tuple, Optional
from pathlib import Path


class AudioProcessor:
    """Process audio files for transcription."""
    
    def __init__(self, sample_rate: int = 22050):
        """
        Initialize audio processor.
        
        Args:
            sample_rate: Target sample rate for processing
        """
        self.sample_rate = sample_rate
    
    def load(self, audio_path: str) -> Tuple[np.ndarray, int]:
        """
        Load audio file.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Tuple of (audio_data, sample_rate)
        """
        audio, sr = librosa.load(audio_path, sr=self.sample_rate, mono=True)
        return audio, sr
    
    def normalize(self, audio: np.ndarray) -> np.ndarray:
        """Normalize audio to [-1, 1] range."""
        return librosa.util.normalize(audio)
    
    def trim_silence(self, audio: np.ndarray, top_db: int = 20) -> np.ndarray:
        """Trim silence from beginning and end."""
        trimmed, _ = librosa.effects.trim(audio, top_db=top_db)
        return trimmed
    
    def split_by_onset(self, audio: np.ndarray, sr: int) -> list:
        """
        Split audio by onset detection.
        
        Args:
            audio: Audio array
            sr: Sample rate
            
        Returns:
            List of audio segments
        """
        onset_frames = librosa.onset.onset_detect(
            y=audio, sr=sr, wait=3, pre_avg=3, post_avg=3, pre_max=3, post_max=3
        )
        onset_samples = librosa.frames_to_samples(onset_frames)
        
        segments = []
        for i in range(len(onset_samples) - 1):
            segment = audio[onset_samples[i]:onset_samples[i + 1]]
            segments.append(segment)
        
        # Add last segment
        if onset_samples.size > 0:
            segments.append(audio[onset_samples[-1]:])
        
        return segments
    
    def detect_key(self, audio: np.ndarray, sr: int) -> str:
        """
        Detect musical key of audio.
        
        Args:
            audio: Audio array
            sr: Sample rate
            
        Returns:
            Key signature (e.g., 'C major', 'A minor')
        """
        chroma = librosa.feature.chroma_cqt(y=audio, sr=sr)
        chroma_avg = np.mean(chroma, axis=1)
        
        # Simple key detection based on chroma profile
        keys = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        key_idx = np.argmax(chroma_avg)
        
        # Determine major/minor (simplified)
        third = (key_idx + 4) % 12  # Major third
        minor_third = (key_idx + 3) % 12  # Minor third
        
        if chroma_avg[third] > chroma_avg[minor_third]:
            return f"{keys[key_idx]} major"
        else:
            return f"{keys[key_idx]} minor"
    
    def estimate_tempo(self, audio: np.ndarray, sr: int) -> float:
        """
        Estimate tempo (BPM) of audio.
        
        Args:
            audio: Audio array
            sr: Sample rate
            
        Returns:
            Tempo in BPM
        """
        tempo, _ = librosa.beat.beat_track(y=audio, sr=sr)
        return float(tempo)

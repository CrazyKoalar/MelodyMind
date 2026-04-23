"""
Tests for pitch detection module.
"""

import pytest

from melonymind.core.pitch_detector import DetectionMode, NoteEvent, PitchDetector


class TestPitchDetector:
    """Test cases for PitchDetector."""
    
    def test_note_event_creation(self):
        """Test NoteEvent dataclass."""
        note = NoteEvent(
            pitch=60.0,  # Middle C
            start_time=0.0,
            end_time=1.0,
            confidence=0.9
        )
        
        assert note.pitch == 60.0
        assert note.duration == 1.0
        assert note.note_name == "C4"
    
    def test_detector_initialization(self):
        """Test detector can be initialized."""
        detector = PitchDetector(mode=DetectionMode.PYIN)
        assert detector.mode == DetectionMode.PYIN

    def test_detect_raises_for_unimplemented_mode(self):
        """CREPE mode should clearly report that it is not implemented yet."""
        detector = PitchDetector(mode=DetectionMode.CREPE)

        with pytest.raises(NotImplementedError):
            detector.detect(audio=[], sr=22050)
    
    def test_quantize_notes(self):
        """Test note quantization."""
        detector = PitchDetector()
        
        notes = [
            NoteEvent(pitch=60.2, start_time=0.1, end_time=0.95, confidence=0.9),
            NoteEvent(pitch=62.1, start_time=1.0, end_time=1.9, confidence=0.8),
        ]
        
        quantized = detector.quantize_notes(notes, bpm=120)
        
        # Check pitches are rounded
        assert quantized[0].pitch == 60
        assert quantized[1].pitch == 62

        # Check timings are on the 16th-note grid at 120 BPM (0.125 seconds)
        assert quantized[0].start_time == 0.125
        assert quantized[0].end_time == 1.0
        assert quantized[1].start_time == 1.0
        assert quantized[1].end_time == 1.875


class TestNoteEvent:
    """Test cases for NoteEvent."""
    
    def test_note_name_conversion(self):
        """Test MIDI to note name conversion."""
        test_cases = [
            (60, "C4"),
            (61, "C#4"),
            (62, "D4"),
            (64, "E4"),
            (65, "F4"),
            (67, "G4"),
            (69, "A4"),
            (71, "B4"),
            (72, "C5"),
        ]
        
        for midi_pitch, expected_name in test_cases:
            note = NoteEvent(
                pitch=float(midi_pitch),
                start_time=0.0,
                end_time=1.0,
                confidence=1.0
            )
            assert note.note_name == expected_name


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

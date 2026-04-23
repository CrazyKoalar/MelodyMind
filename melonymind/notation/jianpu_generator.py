"""
Generate Jianpu (简谱) notation.
"""

from typing import List, Optional
from pathlib import Path
from dataclasses import dataclass

from ..core.pitch_detector import NoteEvent


@dataclass
class JianpuNote:
    """Represents a note in Jianpu notation."""
    number: int  # 1-7
    octave: int  # 0 = middle, positive = high, negative = low
    duration: str  # e.g., '4', '8', '8.'
    is_dotted: bool = False
    
    def __str__(self) -> str:
        """Convert to Jianpu string representation."""
        note_str = str(self.number)
        
        # Add octave markers
        if self.octave > 0:
            note_str = note_str + "'" * self.octave
        elif self.octave < 0:
            note_str = note_str + "," * abs(self.octave)
        
        # Add duration
        note_str += self.duration
        
        if self.is_dotted:
            note_str += "."
        
        return note_str


class JianpuGenerator:
    """Generate Jianpu (numbered musical notation)."""
    
    def __init__(self, key: str = "C"):
        """
        Initialize Jianpu generator.
        
        Args:
            key: Musical key (e.g., 'C', 'G', 'F')
        """
        self.key = key
        self.key_mapping = self._get_key_mapping(key)
    
    def generate(
        self, 
        notes: List[NoteEvent], 
        tempo: int = 120,
        time_signature: str = "4/4"
    ) -> str:
        """
        Generate Jianpu notation.
        
        Args:
            notes: List of note events
            tempo: Tempo in BPM
            time_signature: Time signature
            
        Returns:
            Jianpu notation as string
        """
        jianpu_notes = []
        
        for note in notes:
            jn = self._midi_to_jianpu(note.pitch, note.duration, tempo)
            jianpu_notes.append(str(jn))
        
        # Format output
        header = f"1={self.key}  {time_signature}  ♩={tempo}\n\n"
        notation = " ".join(jianpu_notes)
        
        return header + notation
    
    def generate_html(
        self, 
        notes: List[NoteEvent], 
        tempo: int = 120,
        time_signature: str = "4/4"
    ) -> str:
        """
        Generate HTML with styled Jianpu notation.
        
        Args:
            notes: List of note events
            tempo: Tempo in BPM
            time_signature: Time signature
            
        Returns:
            HTML string
        """
        jianpu_notes = []
        
        for note in notes:
            jn = self._midi_to_jianpu(note.pitch, note.duration, tempo)
            jianpu_notes.append(self._format_jianpu_html(jn))
        
        html = f'''<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    .jianpu {{
      font-family: "Courier New", monospace;
      font-size: 24px;
      line-height: 2;
    }}
    .jianpu-note {{
      display: inline-block;
      margin: 0 4px;
      position: relative;
    }}
    .jianpu-high {{ 
      border-top: 2px solid black; 
      padding-top: 4px;
    }}
    .jianpu-low {{ 
      border-bottom: 2px solid black; 
      padding-bottom: 4px;
    }}
    .jianpu-dot {{
      position: absolute;
      right: -8px;
      top: 0;
    }}
    .jianpu-header {{
      margin-bottom: 20px;
    }}
  </style>
</head>
<body>
  <div class="jianpu">
    <div class="jianpu-header">
      1={self.key} &nbsp;&nbsp; {time_signature} &nbsp;&nbsp; ♩={tempo}
    </div>
    <div class="jianpu-notes">
      {' '.join(jianpu_notes)}
    </div>
  </div>
</body>
</html>'''
        return html
    
    def export_text(
        self, 
        notes: List[NoteEvent], 
        output_path: str,
        tempo: int = 120,
        time_signature: str = "4/4"
    ) -> str:
        """
        Export Jianpu to text file.
        
        Args:
            notes: List of note events
            output_path: Output file path
            tempo: Tempo in BPM
            time_signature: Time signature
            
        Returns:
            Path to output file
        """
        notation = self.generate(notes, tempo, time_signature)
        Path(output_path).write_text(notation, encoding='utf-8')
        return output_path
    
    def _midi_to_jianpu(
        self, 
        midi_pitch: float, 
        duration_sec: float,
        tempo: int
    ) -> JianpuNote:
        """Convert MIDI pitch to Jianpu note."""
        # C4 = MIDI 60 = Jianpu 1 (in C major)
        # Map MIDI to scale degree
        
        # Get pitch class (0-11)
        pitch_class = int(midi_pitch % 12)
        
        # Map to scale degree based on key
        scale_degree = self.key_mapping.get(pitch_class)
        if scale_degree is None:
            # Not in key, use chromatic alteration
            scale_degree = self._get_chromatic_alteration(pitch_class)
        
        # Calculate octave
        # C4 (MIDI 60) is middle octave (0)
        octave = int(midi_pitch // 12) - 5
        
        # Calculate duration
        duration = self._calculate_duration(duration_sec, tempo)
        
        return JianpuNote(
            number=scale_degree,
            octave=octave,
            duration=duration
        )
    
    def _get_key_mapping(self, key: str) -> dict:
        """Get MIDI pitch class to scale degree mapping for key."""
        # C major mapping
        c_major = {0: 1, 2: 2, 4: 3, 5: 4, 7: 5, 9: 6, 11: 7}
        
        # Transpose to target key
        key_offsets = {
            'C': 0, 'G': 7, 'D': 2, 'A': 9, 'E': 4, 'B': 11,
            'F': 5, 'Bb': 10, 'Eb': 3, 'Ab': 8, 'Db': 1, 'Gb': 6
        }
        
        offset = key_offsets.get(key, 0)
        mapping = {}
        for pc, degree in c_major.items():
            transposed_pc = (pc + offset) % 12
            mapping[transposed_pc] = degree
        
        return mapping
    
    def _get_chromatic_alteration(self, pitch_class: int) -> int:
        """Handle chromatic notes not in key."""
        # Simplified: map to nearest scale degree
        # In real implementation, would use # (sharp) or b (flat) notation
        mapping = {1: 1, 3: 2, 6: 4, 8: 5, 10: 6}
        return mapping.get(pitch_class, 1)
    
    def _calculate_duration(self, seconds: float, tempo: int) -> str:
        """Calculate Jianpu duration notation."""
        beat_duration = 60.0 / tempo
        beats = seconds / beat_duration
        
        # Jianpu durations: 4 = quarter, 8 = eighth, etc.
        if beats >= 4:
            return '1'
        elif beats >= 2:
            return '2'
        elif beats >= 1:
            return '4'
        elif beats >= 0.5:
            return '8'
        elif beats >= 0.25:
            return '16'
        else:
            return '32'
    
    def _format_jianpu_html(self, note: JianpuNote) -> str:
        """Format Jianpu note as HTML."""
        css_class = "jianpu-note"
        if note.octave > 0:
            css_class += " jianpu-high"
        elif note.octave < 0:
            css_class += " jianpu-low"
        
        content = str(note.number)
        if note.octave > 0:
            content += "'" * note.octave
        elif note.octave < 0:
            content += "," * abs(note.octave)
        
        content += note.duration
        
        if note.is_dotted:
            content += '<span class="jianpu-dot">.</span>'
        
        return f'<span class="{css_class}">{content}</span>'

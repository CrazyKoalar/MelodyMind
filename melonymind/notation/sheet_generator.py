"""
Generate standard music notation (五线谱) using LilyPond or VexFlow.
"""

from typing import List, Optional
from pathlib import Path
from dataclasses import dataclass

from ..core.pitch_detector import NoteEvent


@dataclass
class SheetMusicConfig:
    """Configuration for sheet music generation."""
    title: str = "Transcribed Music"
    composer: str = ""
    tempo: int = 120
    key: str = "C major"
    time_signature: str = "4/4"


class SheetGenerator:
    """Generate standard music notation."""
    
    def __init__(self, config: Optional[SheetMusicConfig] = None):
        """
        Initialize sheet generator.
        
        Args:
            config: Sheet music configuration
        """
        self.config = config or SheetMusicConfig()
    
    def generate_lilypond(self, notes: List[NoteEvent]) -> str:
        """
        Generate LilyPond notation code.
        
        Args:
            notes: List of note events
            
        Returns:
            LilyPond source code
        """
        # Convert MIDI notes to LilyPond notation
        lily_notes = []
        
        for note in notes:
            pitch_name = self._midi_to_lilypond(note.pitch)
            duration = self._seconds_to_lilypond_duration(
                note.duration, 
                self.config.tempo
            )
            lily_notes.append(f"{pitch_name}{duration}")
        
        # Build LilyPond file
        lilypond_code = f'''\\version "2.22.0"

\\header {{
  title = "{self.config.title}"
  composer = "{self.config.composer}"
}}

\\score {{
  \\new Staff {{
    \\clef treble
    \\key {self._key_to_lilypond(self.config.key)}
    \\time {self.config.time_signature}
    \\tempo 4 = {self.config.tempo}
    
    {' '.join(lily_notes)}
  }}
}}
'''
        return lilypond_code
    
    def generate_vexflow(self, notes: List[NoteEvent]) -> str:
        """
        Generate VexFlow JavaScript code for web rendering.
        
        Args:
            notes: List of note events
            
        Returns:
            HTML/JS code for VexFlow rendering
        """
        vex_notes = []
        
        for note in notes:
            key = self._midi_to_vexflow_key(note.pitch)
            duration = self._seconds_to_vexflow_duration(
                note.duration,
                self.config.tempo
            )
            vex_notes.append(f'  new VF.StaveNote({{clef: "treble", keys: ["{key}"], duration: "{duration}"}})')
        
        html = f'''<!DOCTYPE html>
<html>
<head>
  <script src="https://unpkg.com/vexflow/releases/vexflow-min.js"></script>
</head>
<body>
  <div id="sheet-music"></div>
  <script>
    const VF = Vex.Flow;
    const div = document.getElementById('sheet-music');
    const renderer = new VF.Renderer(div, VF.Renderer.Backends.SVG);
    renderer.resize(800, 200);
    const context = renderer.getContext();
    
    const stave = new VF.Stave(10, 40, 700);
    stave.addClef('treble').addTimeSignature('{self.config.time_signature}');
    stave.setContext(context).draw();
    
    const notes = [
{','.join(vex_notes)}
    ];
    
    const voice = new VF.Voice({{num_beats: 4, beat_value: 4}});
    voice.addTickables(notes);
    
    const formatter = new VF.Formatter().joinVoices([voice]).format([voice], 600);
    voice.draw(context, stave);
  </script>
</body>
</html>'''
        return html
    
    def export_pdf(self, notes: List[NoteEvent], output_path: str) -> str:
        """
        Export sheet music to PDF using LilyPond.
        
        Args:
            notes: List of note events
            output_path: Output PDF path
            
        Returns:
            Path to generated PDF
        """
        lilypond_code = self.generate_lilypond(notes)
        
        # Write LilyPond file
        lily_path = Path(output_path).with_suffix('.ly')
        lily_path.write_text(lilypond_code, encoding='utf-8')
        
        # Compile with LilyPond (requires LilyPond installed)
        import subprocess
        try:
            subprocess.run(
                ['lilypond', '--pdf', '-o', str(Path(output_path).parent), str(lily_path)],
                check=True,
                capture_output=True
            )
            return output_path
        except (subprocess.CalledProcessError, FileNotFoundError):
            # LilyPond not installed, return the .ly file path
            return str(lily_path)
    
    def _midi_to_lilypond(self, midi_pitch: float) -> str:
        """Convert MIDI pitch to LilyPond notation."""
        notes = ['c', 'cis', 'd', 'dis', 'e', 'f', 'fis', 'g', 'gis', 'a', 'ais', 'b']
        octave = int(midi_pitch // 12) - 4
        note_idx = int(midi_pitch % 12)
        
        note = notes[note_idx]
        if octave > 0:
            note += "'" * octave
        elif octave < 0:
            note += "," * abs(octave)
        
        return note
    
    def _key_to_lilypond(self, key: str) -> str:
        """Convert key signature to LilyPond format."""
        key_map = {
            'C major': 'c \\major',
            'G major': 'g \\major',
            'D major': 'd \\major',
            'A major': 'a \\major',
            'E major': 'e \\major',
            'A minor': 'a \\minor',
            'E minor': 'e \\minor',
            'D minor': 'd \\minor',
        }
        return key_map.get(key, 'c \\major')
    
    def _seconds_to_lilypond_duration(self, seconds: float, bpm: int) -> str:
        """Convert duration in seconds to LilyPond duration."""
        beat_duration = 60.0 / bpm
        beats = seconds / beat_duration
        
        # Map to standard durations
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
    
    def _midi_to_vexflow_key(self, midi_pitch: float) -> str:
        """Convert MIDI pitch to VexFlow key format."""
        notes = ['c', 'c#', 'd', 'd#', 'e', 'f', 'f#', 'g', 'g#', 'a', 'a#', 'b']
        octave = int(midi_pitch // 12) - 4
        note_idx = int(midi_pitch % 12)
        return f"{notes[note_idx]}/{octave}"
    
    def _seconds_to_vexflow_duration(self, seconds: float, bpm: int) -> str:
        """Convert duration to VexFlow format."""
        beat_duration = 60.0 / bpm
        beats = seconds / beat_duration
        
        if beats >= 1:
            return 'q'  # quarter
        elif beats >= 0.5:
            return '8'  # eighth
        elif beats >= 0.25:
            return '16'  # sixteenth
        else:
            return '32'  # thirty-second

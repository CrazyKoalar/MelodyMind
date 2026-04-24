"""Generate single-line or piano sheet music outputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from ..core.arranger import PianoArrangement
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
        self.config = config or SheetMusicConfig()

    def generate_lilypond(self, notes: List[NoteEvent]) -> str:
        lily_notes = self._build_lily_voice(notes)
        return self._wrap_single_staff(lily_notes, clef="treble")

    def generate_piano_lilypond(self, arrangement: PianoArrangement) -> str:
        melody_notes = self._build_lily_voice(arrangement.melody)
        accompaniment_notes = self._build_lily_voice(arrangement.accompaniment)
        return f'''\\version "2.22.0"

\\header {{
  title = "{self.config.title}"
  composer = "{self.config.composer}"
}}

\\score {{
  \\new PianoStaff <<
    \\new Staff {{
      \\clef treble
      \\key {self._key_to_lilypond(self.config.key)}
      \\time {self.config.time_signature}
      \\tempo 4 = {self.config.tempo}
      {melody_notes}
    }}
    \\new Staff {{
      \\clef bass
      \\key {self._key_to_lilypond(self.config.key)}
      \\time {self.config.time_signature}
      {accompaniment_notes}
    }}
  >>
}}
'''

    def generate_vexflow(self, notes: List[NoteEvent]) -> str:
        vex_notes = []
        for note in notes:
            key = self._midi_to_vexflow_key(note.pitch)
            duration = self._seconds_to_vexflow_duration(note.duration, self.config.tempo)
            vex_notes.append(
                f'  new VF.StaveNote({{clef: "treble", keys: ["{key}"], duration: "{duration}"}})'
            )

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
        lilypond_code = self.generate_lilypond(notes)
        lily_path = Path(output_path).with_suffix(".ly")
        lily_path.write_text(lilypond_code, encoding="utf-8")

        import subprocess

        try:
            subprocess.run(
                ["lilypond", "--pdf", "-o", str(Path(output_path).parent), str(lily_path)],
                check=True,
                capture_output=True,
            )
            return output_path
        except (subprocess.CalledProcessError, FileNotFoundError):
            return str(lily_path)

    def _build_lily_voice(self, notes: List[NoteEvent]) -> str:
        lily_notes = []
        for note in notes:
            pitch_name = self._midi_to_lilypond(note.pitch)
            duration = self._seconds_to_lilypond_duration(note.duration, self.config.tempo)
            lily_notes.append(f"{pitch_name}{duration}")
        return " ".join(lily_notes) if lily_notes else "r1"

    def _wrap_single_staff(self, lily_notes: str, clef: str) -> str:
        return f'''\\version "2.22.0"

\\header {{
  title = "{self.config.title}"
  composer = "{self.config.composer}"
}}

\\score {{
  \\new Staff {{
    \\clef {clef}
    \\key {self._key_to_lilypond(self.config.key)}
    \\time {self.config.time_signature}
    \\tempo 4 = {self.config.tempo}
    {lily_notes}
  }}
}}
'''

    def _midi_to_lilypond(self, midi_pitch: float) -> str:
        notes = ["c", "cis", "d", "dis", "e", "f", "fis", "g", "gis", "a", "ais", "b"]
        octave = int(midi_pitch // 12) - 4
        note_idx = int(midi_pitch % 12)

        note = notes[note_idx]
        if octave > 0:
            note += "'" * octave
        elif octave < 0:
            note += "," * abs(octave)
        return note

    def _key_to_lilypond(self, key: str) -> str:
        key_map = {
            "C major": "c \\major",
            "G major": "g \\major",
            "D major": "d \\major",
            "A major": "a \\major",
            "E major": "e \\major",
            "F major": "f \\major",
            "A minor": "a \\minor",
            "E minor": "e \\minor",
            "D minor": "d \\minor",
            "B minor": "b \\minor",
        }
        return key_map.get(key, "c \\major")

    def _seconds_to_lilypond_duration(self, seconds: float, bpm: int) -> str:
        beat_duration = 60.0 / max(bpm, 1)
        beats = seconds / beat_duration

        if beats >= 4:
            return "1"
        if beats >= 2:
            return "2"
        if beats >= 1:
            return "4"
        if beats >= 0.5:
            return "8"
        if beats >= 0.25:
            return "16"
        return "32"

    def _midi_to_vexflow_key(self, midi_pitch: float) -> str:
        notes = ["c", "c#", "d", "d#", "e", "f", "f#", "g", "g#", "a", "a#", "b"]
        octave = int(midi_pitch // 12) - 4
        note_idx = int(midi_pitch % 12)
        return f"{notes[note_idx]}/{octave}"

    def _seconds_to_vexflow_duration(self, seconds: float, bpm: int) -> str:
        beat_duration = 60.0 / max(bpm, 1)
        beats = seconds / beat_duration

        if beats >= 1:
            return "q"
        if beats >= 0.5:
            return "8"
        if beats >= 0.25:
            return "16"
        return "32"

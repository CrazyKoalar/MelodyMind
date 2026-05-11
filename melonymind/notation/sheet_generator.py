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
        ts_parts = self.config.time_signature.split("/")
        beats_per_measure = int(ts_parts[0])
        beat_value = int(ts_parts[1])
        ticks_per_measure = beats_per_measure * (32 // beat_value)

        duration_ticks = {"w": 32, "h": 16, "q": 8, "8": 4, "16": 2, "32": 1}

        measures: List[List[dict]] = [[]]
        remaining = ticks_per_measure
        for note in notes:
            key = self._midi_to_vexflow_key(note.pitch)
            duration = self._seconds_to_vexflow_duration(note.duration, self.config.tempo)
            ticks = duration_ticks.get(duration, 1)
            if ticks > remaining and measures[-1]:
                measures.append([])
                remaining = ticks_per_measure
            measures[-1].append({"key": key, "duration": duration})
            remaining -= ticks

        measure_lines = []
        for measure in measures:
            items = ", ".join(
                f'{{keys: ["{n["key"]}"], duration: "{n["duration"]}"}}'
                for n in measure
            )
            measure_lines.append(f"      [{items}]")
        measures_js = ",\n".join(measure_lines) if measure_lines else "      []"

        measures_per_row = 4
        measure_width = 260
        row_height = 130
        clef_width = 60
        left_pad = 10
        top_pad = 40

        html = f'''<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <script src="https://unpkg.com/vexflow@3.0.9/releases/vexflow-min.js"></script>
  <style>
    body {{ margin: 20px; font-family: sans-serif; background: #fff; }}
    h1 {{ font-size: 18px; margin: 0 0 12px; }}
    #sheet-music {{ overflow-x: auto; }}
  </style>
</head>
<body>
  <h1>{self.config.title} &mdash; {self.config.key}, {self.config.tempo} BPM</h1>
  <div id="sheet-music"></div>
  <script>
    const VF = Vex.Flow;
    const measures = [
{measures_js}
    ];
    const measuresPerRow = {measures_per_row};
    const measureWidth = {measure_width};
    const rowHeight = {row_height};
    const clefWidth = {clef_width};
    const leftPad = {left_pad};
    const topPad = {top_pad};
    const numBeats = {beats_per_measure};
    const beatValue = {beat_value};
    const timeSig = "{self.config.time_signature}";

    const totalRows = Math.ceil(measures.length / measuresPerRow);
    const totalWidth = leftPad * 2 + measuresPerRow * measureWidth + clefWidth;
    const totalHeight = topPad + totalRows * rowHeight + 40;

    const div = document.getElementById('sheet-music');
    const renderer = new VF.Renderer(div, VF.Renderer.Backends.SVG);
    renderer.resize(totalWidth, totalHeight);
    const context = renderer.getContext();

    measures.forEach((measureNotes, idx) => {{
      const row = Math.floor(idx / measuresPerRow);
      const col = idx % measuresPerRow;
      const isFirstInRow = col === 0;
      const width = isFirstInRow ? measureWidth + clefWidth : measureWidth;
      const x = leftPad + col * measureWidth + (isFirstInRow ? 0 : clefWidth);
      const y = topPad + row * rowHeight;

      const stave = new VF.Stave(x, y, width);
      if (isFirstInRow) {{
        stave.addClef('treble').addTimeSignature(timeSig);
      }}
      stave.setContext(context).draw();

      if (measureNotes.length === 0) return;

      const vfNotes = measureNotes.map(n =>
        new VF.StaveNote({{clef: 'treble', keys: n.keys, duration: n.duration}})
      );
      const voice = new VF.Voice({{num_beats: numBeats, beat_value: beatValue}}).setStrict(false);
      voice.addTickables(vfNotes);
      new VF.Formatter()
        .joinVoices([voice])
        .format([voice], width - (isFirstInRow ? clefWidth + 20 : 20));
      voice.draw(context, stave);
    }});
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
        octave = int(midi_pitch // 12) - 1
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

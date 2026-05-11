"""
Tests for notation generators.
"""

from melonymind.core.pitch_detector import NoteEvent
from melonymind.core.arranger import PianoArrangement
from melonymind.notation.jianpu_generator import JianpuGenerator
from melonymind.notation.sheet_generator import SheetGenerator, SheetMusicConfig


def sample_notes():
    """Create a small note sequence for notation tests."""
    return [
        NoteEvent(pitch=60.0, start_time=0.0, end_time=0.5, confidence=0.9),
        NoteEvent(pitch=64.0, start_time=0.5, end_time=1.0, confidence=0.8),
    ]


def test_generate_lilypond_contains_header_and_notes():
    """LilyPond export should include score metadata and note content."""
    generator = SheetGenerator(
        SheetMusicConfig(
            title="Unit Test Song",
            composer="MelodyMind",
            tempo=120,
            key="C major",
            time_signature="4/4",
        )
    )

    result = generator.generate_lilypond(sample_notes())

    assert 'title = "Unit Test Song"' in result
    assert 'composer = "MelodyMind"' in result
    assert "\\tempo 4 = 120" in result
    assert "\\key c \\major" in result
    assert "c'4" in result
    assert "e'4" in result


def test_generate_vexflow_contains_expected_note_keys():
    """VexFlow output should include HTML wrapper and note keys."""
    generator = SheetGenerator(SheetMusicConfig(tempo=120, time_signature="4/4"))

    result = generator.generate_vexflow(sample_notes())

    assert "<!DOCTYPE html>" in result
    assert 'keys: ["c/4"]' in result
    assert 'keys: ["e/4"]' in result
    assert 'duration: "q"' in result


def test_generate_piano_lilypond_contains_two_staves():
    """Piano export should render melody and accompaniment into a PianoStaff."""
    generator = SheetGenerator(SheetMusicConfig(title="Piano Test", tempo=120, key="C major"))
    arrangement = PianoArrangement(
        melody=sample_notes(),
        accompaniment=[
            NoteEvent(pitch=48.0, start_time=0.0, end_time=1.0, confidence=0.7),
            NoteEvent(pitch=60.0, start_time=0.0, end_time=1.0, confidence=0.7),
            NoteEvent(pitch=64.0, start_time=0.0, end_time=1.0, confidence=0.7),
        ],
        chords=[],
    )

    result = generator.generate_piano_lilypond(arrangement)

    assert "\\new PianoStaff" in result
    assert "\\clef treble" in result
    assert "\\clef bass" in result
    assert 'title = "Piano Test"' in result


def test_export_pdf_falls_back_to_lilypond_source(local_tmp_path, monkeypatch):
    """PDF export should fall back to the .ly file when LilyPond is unavailable."""
    generator = SheetGenerator()

    def raise_missing_binary(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr("subprocess.run", raise_missing_binary)

    output_path = local_tmp_path / "score.pdf"
    returned_path = generator.export_pdf(sample_notes(), str(output_path))

    lilypond_path = local_tmp_path / "score.ly"

    assert returned_path == str(lilypond_path)
    assert lilypond_path.exists()
    assert "\\score" in lilypond_path.read_text(encoding="utf-8")


def test_generate_jianpu_contains_header_and_scale_degrees():
    """Jianpu text export should include key header and numbered notes."""
    generator = JianpuGenerator(key="C")

    result = generator.generate(sample_notes(), tempo=120, time_signature="4/4")

    assert result.startswith("1=C  4/4")
    assert "14" in result
    assert "34" in result


def test_generate_jianpu_html_contains_markup():
    """Jianpu HTML export should include the styled note container."""
    generator = JianpuGenerator(key="C")

    result = generator.generate_html(sample_notes(), tempo=120, time_signature="4/4")

    assert "<!DOCTYPE html>" in result
    assert 'class="jianpu"' in result
    assert 'class="jianpu-note"' in result
    assert "1=C" in result


def test_export_jianpu_text_writes_file(local_tmp_path):
    """Text export should write Jianpu notation to disk."""
    generator = JianpuGenerator(key="C")
    output_path = local_tmp_path / "jianpu.txt"

    returned_path = generator.export_text(sample_notes(), str(output_path), tempo=120)

    assert returned_path == str(output_path)
    assert output_path.exists()
    assert "1=C" in output_path.read_text(encoding="utf-8")

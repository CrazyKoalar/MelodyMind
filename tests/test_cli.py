"""
Tests for the MelodyMind command-line interface.
"""

import pytest

from melonymind import cli
from melonymind.core.pitch_detector import NoteEvent


class DummyAudioProcessor:
    """Test double for audio loading and analysis."""

    def __init__(self, sample_rate: int = 22050, melody_ranker=None):
        self.sample_rate = sample_rate
        self.melody_ranker = melody_ranker

    def load(self, audio_path: str):
        return [0.0, 0.1, 0.0], self.sample_rate

    def normalize(self, audio):
        return audio

    def trim_silence(self, audio):
        return audio

    def detect_key(self, audio, sr: int) -> str:
        return "C major"

    def estimate_tempo(self, audio, sr: int) -> float:
        return 120.0

    def separate_sources(self, audio, sr: int):
        return {
            "mix": type("Stem", (), {"name": "mix", "audio": audio, "score": 0.0})(),
            "vocals": type("Stem", (), {"name": "vocals", "audio": audio, "score": 0.0})(),
        }

    def choose_melody_stem(self, stems, sr: int, detector, min_confidence: float = 0.55):
        return type(
            "Selection",
            (),
            {"stem_name": "vocals", "stem_audio": stems["vocals"].audio, "stem_scores": {"vocals": 0.9}},
        )()


class DummyPitchDetector:
    """Test double for pitch detection."""

    def __init__(self, mode=None):
        self.mode = mode

    def detect(self, audio, sr: int, min_confidence: float = 0.5):
        return [
            NoteEvent(
                pitch=60.0,
                start_time=0.0,
                end_time=0.5,
                confidence=0.9,
            )
        ]

    def quantize_notes(self, notes, bpm: float = 120):
        return notes


class DummyPianoArranger:
    def create_arrangement(self, melody, key: str, tempo: float, time_signature: str = "4/4"):
        return type("Arrangement", (), {"melody": list(melody), "accompaniment": list(melody), "chords": []})()


class DummyMidiExporter:
    def export_melody(self, notes, output_path: str, tempo: float):
        from pathlib import Path

        Path(output_path).write_text("melody-midi", encoding="utf-8")
        return output_path

    def export_piano_arrangement(self, arrangement, output_path: str, tempo: float):
        from pathlib import Path

        Path(output_path).write_text("piano-midi", encoding="utf-8")
        return output_path


def test_build_parser_uses_default_output_directory():
    """CLI parser should expose the documented default output path."""
    parser = cli.build_parser()

    args = parser.parse_args(["input.wav"])

    assert args.audio_file == "input.wav"
    assert args.output == "./output"
    assert args.melody_ranker_model is None


def test_main_errors_when_audio_file_is_missing():
    """CLI should exit with an error when the audio file does not exist."""
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["missing.wav"])

    assert exc_info.value.code == 2


def test_main_delegates_to_transcribe_audio(local_tmp_path, monkeypatch):
    """CLI main should pass parsed arguments to the transcription workflow."""
    audio_path = local_tmp_path / "demo.wav"
    audio_path.write_text("placeholder", encoding="utf-8")
    calls = {}

    def fake_transcribe(
        audio_file: str,
        output_dir: str,
        melody_ranker_model: str | None = None,
    ) -> int:
        calls["audio_file"] = audio_file
        calls["output_dir"] = output_dir
        calls["melody_ranker_model"] = melody_ranker_model
        return 0

    monkeypatch.setattr(cli, "transcribe_audio", fake_transcribe)

    exit_code = cli.main(
        [str(audio_path), "-o", "custom-output", "--melody-ranker-model", "model.json"]
    )

    assert exit_code == 0
    assert calls["audio_file"] == str(audio_path)
    assert calls["output_dir"] == "custom-output"
    assert calls["melody_ranker_model"] == "model.json"


def test_transcribe_audio_loads_ranker_via_learned_model(local_tmp_path, monkeypatch):
    audio_path = local_tmp_path / "demo.wav"
    audio_path.write_text("placeholder", encoding="utf-8")
    output_dir = local_tmp_path / "generated"
    loaded = {}

    monkeypatch.setattr(cli, "AudioProcessor", DummyAudioProcessor)
    monkeypatch.setattr(cli, "PitchDetector", DummyPitchDetector)
    monkeypatch.setattr(cli, "PianoArranger", DummyPianoArranger)
    monkeypatch.setattr(cli, "MidiExporter", DummyMidiExporter)

    def fake_load_model(model_path: str):
        loaded["model_path"] = model_path
        return {"kind": "loaded-ranker"}

    monkeypatch.setattr(cli, "load_melody_ranker_model", fake_load_model)

    exit_code = cli.transcribe_audio(
        str(audio_path),
        str(output_dir),
        melody_ranker_model="trained-ranker.json",
    )

    assert exit_code == 0
    assert loaded["model_path"] == "trained-ranker.json"


def test_transcribe_audio_writes_expected_output_files(local_tmp_path, monkeypatch):
    """Transcription flow should generate the expected notation artifacts."""
    audio_path = local_tmp_path / "demo.wav"
    audio_path.write_text("placeholder", encoding="utf-8")
    output_dir = local_tmp_path / "generated"

    monkeypatch.setattr(cli, "AudioProcessor", DummyAudioProcessor)
    monkeypatch.setattr(cli, "PitchDetector", DummyPitchDetector)
    monkeypatch.setattr(cli, "PianoArranger", DummyPianoArranger)
    monkeypatch.setattr(cli, "MidiExporter", DummyMidiExporter)

    exit_code = cli.transcribe_audio(str(audio_path), str(output_dir))

    assert exit_code == 0
    assert (output_dir / "piano_score.ly").exists()
    assert (output_dir / "melody_sheet.html").exists()
    assert (output_dir / "jianpu.txt").exists()
    assert (output_dir / "jianpu.html").exists()
    assert (output_dir / "melody.mid").exists()
    assert (output_dir / "piano_arrangement.mid").exists()

    lilypond_text = (output_dir / "piano_score.ly").read_text(encoding="utf-8")
    jianpu_text = (output_dir / "jianpu.txt").read_text(encoding="utf-8")

    assert "demo" in lilypond_text
    assert "\\new PianoStaff" in lilypond_text
    assert "C major" not in jianpu_text
    assert "1=C" in jianpu_text

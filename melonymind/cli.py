"""
Command-line interface for MelodyMind.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import (
    AudioProcessor,
    JianpuGenerator,
    MidiExporter,
    PianoArranger,
    PitchDetector,
    SheetGenerator,
)
from .core.pitch_detector import DetectionMode
from .learned_model import load_melody_ranker_model
from .notation.sheet_generator import SheetMusicConfig


def transcribe_audio(
    audio_path: str,
    output_dir: str = "./output",
    melody_ranker_model: str | None = None,
) -> int:
    """
    Transcribe an audio file and write notation outputs to disk.

    Args:
        audio_path: Path to an input audio file.
        output_dir: Directory where generated files will be written.

    Returns:
        Process exit code.
    """
    print(f"Transcribing: {audio_path}")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print("Loading audio...")
    melody_ranker = (
        load_melody_ranker_model(melody_ranker_model)
        if melody_ranker_model
        else None
    )
    processor = AudioProcessor(sample_rate=22050, melody_ranker=melody_ranker)
    audio, sr = processor.load(audio_path)

    audio = processor.normalize(audio)
    audio = processor.trim_silence(audio)

    key = processor.detect_key(audio, sr)
    tempo = processor.estimate_tempo(audio, sr)
    print(f"Detected key: {key}, tempo: {tempo:.1f} BPM")

    print("Separating rough stems with Kalman-smoothed masks...")
    stems = processor.separate_sources(audio, sr)

    print("Detecting melody candidates...")
    detector = PitchDetector(mode=DetectionMode.PYIN)
    selection = processor.choose_melody_stem(stems, sr, detector, min_confidence=0.55)
    print(f"Selected melody stem: {selection.stem_name}")

    notes = detector.detect(selection.stem_audio, sr, min_confidence=0.6)
    notes = detector.quantize_notes(notes, bpm=tempo)
    print(f"Detected {len(notes)} note events")

    print("Arranging piano accompaniment from the extracted melody...")
    arranger = PianoArranger()
    arrangement = arranger.create_arrangement(
        notes,
        key=key,
        tempo=tempo,
        time_signature="4/4",
    )

    print("Generating notation outputs...")
    config = SheetMusicConfig(
        title=Path(audio_path).stem,
        composer="MelodyMind",
        tempo=max(1, int(round(tempo))),
        key=key,
        time_signature="4/4",
    )

    sheet_gen = SheetGenerator(config)
    lilypond_code = sheet_gen.generate_piano_lilypond(arrangement)
    lily_path = output_path / "piano_score.ly"
    lily_path.write_text(lilypond_code, encoding="utf-8")

    vexflow_html = sheet_gen.generate_vexflow(notes)
    sheet_html_path = output_path / "melody_sheet.html"
    sheet_html_path.write_text(vexflow_html, encoding="utf-8")

    jianpu_gen = JianpuGenerator(key=key.split()[0])
    jianpu_path = output_path / "jianpu.txt"
    jianpu_gen.export_text(notes, str(jianpu_path), tempo=config.tempo)

    jianpu_html = jianpu_gen.generate_html(notes, tempo=config.tempo)
    jianpu_html_path = output_path / "jianpu.html"
    jianpu_html_path.write_text(jianpu_html, encoding="utf-8")

    midi_exporter = MidiExporter()
    melody_midi_path = output_path / "melody.mid"
    midi_exporter.export_melody(notes, str(melody_midi_path), tempo=config.tempo)

    piano_midi_path = output_path / "piano_arrangement.mid"
    midi_exporter.export_piano_arrangement(
        arrangement,
        str(piano_midi_path),
        tempo=config.tempo,
    )

    print(f"Piano LilyPond: {lily_path}")
    print(f"Melody VexFlow HTML: {sheet_html_path}")
    print(f"Jianpu text: {jianpu_path}")
    print(f"Jianpu HTML: {jianpu_html_path}")
    print(f"Melody MIDI: {melody_midi_path}")
    print(f"Piano MIDI: {piano_midi_path}")
    print(f"Done. Output directory: {output_path.resolve()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Create the MelodyMind CLI parser."""
    parser = argparse.ArgumentParser(
        description="Transcribe monophonic audio into sheet music artifacts."
    )
    parser.add_argument(
        "audio_file",
        help="Path to the audio file to transcribe.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="./output",
        help="Directory for generated output files.",
    )
    parser.add_argument(
        "--melody-ranker-model",
        default=None,
        help="Optional path to a trained melody ranker JSON file.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not Path(args.audio_file).exists():
        parser.error(f"audio file not found: {args.audio_file}")

    return transcribe_audio(args.audio_file, args.output, args.melody_ranker_model)


if __name__ == "__main__":
    sys.exit(main())

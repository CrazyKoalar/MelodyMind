"""
Command-line interface for MelodyMind.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import AudioProcessor, JianpuGenerator, PitchDetector, SheetGenerator
from .core.pitch_detector import DetectionMode
from .notation.sheet_generator import SheetMusicConfig


def transcribe_audio(audio_path: str, output_dir: str = "./output") -> int:
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
    processor = AudioProcessor(sample_rate=22050)
    audio, sr = processor.load(audio_path)

    audio = processor.normalize(audio)
    audio = processor.trim_silence(audio)

    key = processor.detect_key(audio, sr)
    tempo = processor.estimate_tempo(audio, sr)
    print(f"Detected key: {key}, tempo: {tempo:.1f} BPM")

    print("Detecting pitch with pYIN...")
    detector = PitchDetector(mode=DetectionMode.PYIN)
    notes = detector.detect(audio, sr, min_confidence=0.6)
    notes = detector.quantize_notes(notes, bpm=tempo)
    print(f"Detected {len(notes)} note events")

    print("Generating notation outputs...")
    config = SheetMusicConfig(
        title=Path(audio_path).stem,
        composer="MelodyMind",
        tempo=max(1, int(round(tempo))),
        key=key,
        time_signature="4/4",
    )

    sheet_gen = SheetGenerator(config)
    lilypond_code = sheet_gen.generate_lilypond(notes)
    lily_path = output_path / "output.ly"
    lily_path.write_text(lilypond_code, encoding="utf-8")

    vexflow_html = sheet_gen.generate_vexflow(notes)
    sheet_html_path = output_path / "sheet_music.html"
    sheet_html_path.write_text(vexflow_html, encoding="utf-8")

    jianpu_gen = JianpuGenerator(key=key.split()[0])
    jianpu_path = output_path / "jianpu.txt"
    jianpu_gen.export_text(notes, str(jianpu_path), tempo=config.tempo)

    jianpu_html = jianpu_gen.generate_html(notes, tempo=config.tempo)
    jianpu_html_path = output_path / "jianpu.html"
    jianpu_html_path.write_text(jianpu_html, encoding="utf-8")

    print(f"LilyPond: {lily_path}")
    print(f"VexFlow HTML: {sheet_html_path}")
    print(f"Jianpu text: {jianpu_path}")
    print(f"Jianpu HTML: {jianpu_html_path}")
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
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not Path(args.audio_file).exists():
        parser.error(f"audio file not found: {args.audio_file}")

    return transcribe_audio(args.audio_file, args.output)


if __name__ == "__main__":
    sys.exit(main())

"""
Demo script for MelodyMind - Audio to Sheet Music Transcription
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from melonymind import AudioProcessor, PitchDetector, SheetGenerator, JianpuGenerator
from melonymind.core.pitch_detector import DetectionMode
from melonymind.notation.sheet_generator import SheetMusicConfig


def transcribe_audio(audio_path: str, output_dir: str = "./output"):
    """
    Transcribe audio file to sheet music.
    
    Args:
        audio_path: Path to audio file
        output_dir: Directory for output files
    """
    print(f"🎵 Transcribing: {audio_path}")
    
    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Step 1: Load and process audio
    print("📁 Loading audio...")
    processor = AudioProcessor(sample_rate=22050)
    audio, sr = processor.load(audio_path)
    
    # Normalize and trim
    audio = processor.normalize(audio)
    audio = processor.trim_silence(audio)
    
    # Detect key and tempo
    key = processor.detect_key(audio, sr)
    tempo = processor.estimate_tempo(audio, sr)
    print(f"🎹 Detected key: {key}, Tempo: {tempo:.1f} BPM")
    
    # Step 2: Detect pitch
    print("🎼 Detecting pitch...")
    detector = PitchDetector(mode=DetectionMode.PYIN)
    notes = detector.detect(audio, sr, min_confidence=0.6)
    print(f"✅ Detected {len(notes)} notes")
    
    # Quantize notes
    notes = detector.quantize_notes(notes, bpm=tempo)
    
    # Step 3: Generate sheet music
    print("📝 Generating sheet music...")
    config = SheetMusicConfig(
        title="Transcribed Piece",
        composer="MelodyMind",
        tempo=int(tempo),
        key=key,
        time_signature="4/4"
    )
    
    # Standard notation (五线谱)
    sheet_gen = SheetGenerator(config)
    
    # LilyPond
    lilypond_code = sheet_gen.generate_lilypond(notes)
    lily_path = Path(output_dir) / "output.ly"
    lily_path.write_text(lilypond_code, encoding='utf-8')
    print(f"🎼 LilyPond: {lily_path}")
    
    # VexFlow HTML
    vexflow_html = sheet_gen.generate_vexflow(notes)
    html_path = Path(output_dir) / "sheet_music.html"
    html_path.write_text(vexflow_html, encoding='utf-8')
    print(f"🌐 HTML (VexFlow): {html_path}")
    
    # Step 4: Generate Jianpu (简谱)
    print("📝 Generating Jianpu...")
    jianpu_gen = JianpuGenerator(key=key.split()[0])
    
    # Text format
    jianpu_text = jianpu_gen.generate(notes, tempo=int(tempo))
    jianpu_path = Path(output_dir) / "jianpu.txt"
    jianpu_gen.export_text(notes, str(jianpu_path), tempo=int(tempo))
    print(f"📄 Jianpu: {jianpu_path}")
    
    # HTML format
    jianpu_html = jianpu_gen.generate_html(notes, tempo=int(tempo))
    jianpu_html_path = Path(output_dir) / "jianpu.html"
    jianpu_html_path.write_text(jianpu_html, encoding='utf-8')
    print(f"🌐 Jianpu HTML: {jianpu_html_path}")
    
    print("\n✨ Transcription complete!")
    print(f"📂 Output directory: {Path(output_dir).absolute()}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Transcribe audio to sheet music"
    )
    parser.add_argument(
        "audio_file",
        help="Path to audio file (wav, mp3, etc.)"
    )
    parser.add_argument(
        "-o", "--output",
        default="./output",
        help="Output directory (default: ./output)"
    )
    
    args = parser.parse_args()
    
    if not Path(args.audio_file).exists():
        print(f"❌ Error: File not found: {args.audio_file}")
        sys.exit(1)
    
    transcribe_audio(args.audio_file, args.output)


if __name__ == "__main__":
    # Example usage without arguments
    if len(sys.argv) == 1:
        print("MelodyMind Demo")
        print("Usage: python demo.py <audio_file> [-o output_dir]")
        print("\nExample:")
        print("  python demo.py my_song.wav -o ./my_output")
    else:
        main()

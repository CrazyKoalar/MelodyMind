# MelodyMind

AI-powered music transcription library for converting monophonic audio into sheet music outputs such as LilyPond, VexFlow HTML, and Jianpu.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- Monophonic pitch detection with `librosa` pYIN
- Dual notation output: standard staff notation and Jianpu
- Web-ready rendering with VexFlow HTML export
- Text-based export with LilyPond source generation
- Extensible architecture for future transcription backends

## Current Status

The pYIN workflow is implemented today and is the recommended path.

`Basic Pitch` scaffolding exists in the codebase, but the integrated `PitchDetector` backend is still a work in progress and should not yet be considered production-ready.

## Installation

```bash
pip install -e .
```

Optional extras:

```bash
pip install -e ".[dev]"
pip install -e ".[basic-pitch]"
pip install -e ".[crepe]"
```

If you prefer installing the runtime dependencies without editable package setup, use:

```bash
pip install -r requirements.txt
```

## Quick Start

```python
from melonymind import AudioProcessor, PitchDetector, SheetGenerator
from melonymind.core.pitch_detector import DetectionMode

processor = AudioProcessor()
audio, sr = processor.load("my_song.wav")

detector = PitchDetector(mode=DetectionMode.PYIN)
notes = detector.detect(audio, sr)

generator = SheetGenerator()
lilypond_code = generator.generate_lilypond(notes)

with open("output.ly", "w", encoding="utf-8") as f:
    f.write(lilypond_code)
```

## Command Line

After installation:

```bash
melonymind my_song.wav -o ./output
```

Without installation:

```bash
python -m melonymind.cli my_song.wav -o ./output
```

## Project Structure

```text
MelodyMind/
|-- melonymind/
|   |-- core/
|   |   |-- audio_processor.py
|   |   `-- pitch_detector.py
|   |-- notation/
|   |   |-- sheet_generator.py
|   |   `-- jianpu_generator.py
|   |-- models/
|   |   `-- basic_pitch.py
|   `-- cli.py
|-- examples/
|   `-- demo.py
|-- tests/
|-- requirements.txt
`-- setup.py
```

## Supported Outputs

| Format | Description | Status |
|--------|-------------|--------|
| LilyPond | Text-based music notation | Ready |
| VexFlow | JavaScript web rendering | Ready |
| Jianpu | Numbered musical notation | Ready |
| PDF | Via LilyPond if installed locally | Partial |
| MIDI | Planned through transcription backends | In progress |
| MusicXML | Universal notation format | Planned |

## Development Notes

- `examples/demo.py` now delegates to the package CLI entry point.
- `melonymind.cli` is the canonical command-line interface.
- The repository currently focuses on a clean monophonic transcription pipeline first.

## Roadmap

- Improve note segmentation and quantization
- Finish Basic Pitch integration
- Add richer export formats such as MusicXML
- Explore real-time and multi-track workflows

## License

This project is licensed under the MIT License.

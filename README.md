# 🎵 MelodyMind

AI-powered music transcription library - Convert audio to sheet music (piano, guitar, and more)

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ Features

- 🎹 **Multi-instrument support** - Piano, guitar, and more instruments
- 🎼 **Dual notation output** - Standard sheet music (五线谱) and Jianpu (简谱)
- 🤖 **Multiple AI backends** - Basic Pitch (Spotify), pYIN, and extensible architecture
- 🌐 **Web-ready** - Generate HTML with VexFlow for browser rendering
- 📄 **Export formats** - PDF, MIDI, LilyPond, and plain text
- 🚀 **Easy to use** - Simple API for quick transcription

## 🚀 Quick Start

### Installation

```bash
# Basic installation
pip install -e .

# With Basic Pitch support (recommended)
pip install -e ".[basic-pitch]"

# Development installation
pip install -e ".[dev]"
```

### Usage

```python
from melonymind import AudioProcessor, PitchDetector, SheetGenerator
from melonymind.core.pitch_detector import DetectionMode

# Load audio
processor = AudioProcessor()
audio, sr = processor.load("my_song.wav")

# Detect pitch
detector = PitchDetector(mode=DetectionMode.PYIN)
notes = detector.detect(audio, sr)

# Generate sheet music
generator = SheetGenerator()
lilypond_code = generator.generate_lilypond(notes)

# Save to file
with open("output.ly", "w") as f:
    f.write(lilypond_code)
```

### Command Line

```bash
python examples/demo.py my_song.wav -o ./output
```

## 📁 Project Structure

```
MelodyMind/
├── melonymind/           # Main package
│   ├── core/             # Audio processing & pitch detection
│   │   ├── audio_processor.py
│   │   └── pitch_detector.py
│   ├── notation/         # Sheet music generation
│   │   ├── sheet_generator.py    # 五线谱
│   │   └── jianpu_generator.py   # 简谱
│   └── models/           # AI model wrappers
│       └── basic_pitch.py
├── examples/             # Example scripts
├── tests/                # Unit tests
├── requirements.txt      # Dependencies
└── setup.py             # Package setup
```

## 🎼 Supported Notation Formats

| Format | Description | Status |
|--------|-------------|--------|
| **LilyPond** | Text-based music notation | ✅ Ready |
| **VexFlow** | JavaScript web rendering | ✅ Ready |
| **Jianpu** | Numbered musical notation (简谱) | ✅ Ready |
| **MIDI** | Standard MIDI file | ✅ Ready |
| **PDF** | Printable sheet music | 🔄 Via LilyPond |
| **MusicXML** | Universal music format | 📋 Planned |

## 🤖 AI Backends

| Backend | Description | Installation |
|---------|-------------|--------------|
| **pYIN** | Probabilistic YIN (default) | Built-in via librosa |
| **Basic Pitch** | Spotify's transcription model | `pip install basic-pitch` |
| **CREPE** | Deep pitch estimation | `pip install crepe` |

## 🛣️ Roadmap

- [ ] Support for guitar tablature
- [ ] Multi-track transcription
- [ ] Real-time transcription
- [ ] MusicXML export
- [ ] Web API service
- [ ] Pre-trained models for specific instruments

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- [Basic Pitch](https://github.com/spotify/basic-pitch) by Spotify
- [Librosa](https://librosa.org/) for audio processing
- [VexFlow](https://vexflow.com/) for web-based notation

---

Made with ❤️ by CrazyKoalar

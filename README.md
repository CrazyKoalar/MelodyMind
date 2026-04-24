# MelodyMind

MelodyMind is an audio-to-melody and piano-arrangement toolkit.

The current pipeline is built around this flow:

1. Load and normalize audio
2. Create rough stems with harmonic/percussive separation, band masking, and Kalman smoothing
3. Rank candidate stems and choose the one that most likely carries the main melody
4. Detect melody notes with `librosa` pYIN
5. Infer simple piano chords from the melody
6. Export melody MIDI, piano MIDI, LilyPond piano score, VexFlow melody HTML, and Jianpu

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## What It Does

- Roughly separates input audio into `mix`, `vocals`, `accompaniment`, `bass`, and `percussive`
- Chooses the most melody-like stem with either:
  - a built-in heuristic ranker
  - a trained melody-ranker model
- Extracts quantized melody notes with `pYIN`
- Builds a simple piano accompaniment from the melody
- Writes:
  - `melody.mid`
  - `piano_arrangement.mid`
  - `piano_score.ly`
  - `melody_sheet.html`
  - `jianpu.txt`
  - `jianpu.html`

## Current Status

This repository is no longer just a monophonic proof of concept.

The current implemented path is:

- rough stem separation
- melody stem selection
- melody extraction
- simple chord inference
- piano arrangement export
- trainable melody-ranker pipeline

Still important to know:

- stem separation is currently heuristic, not a full source-separation neural model
- melody stem ranking can already use a trained model, but the default trainer is still a lightweight linear model
- chord generation is still rule-based
- `Basic Pitch` scaffolding exists, but is not yet the main production path here

## Installation

Editable install:

```bash
pip install -e .
```

Development extras:

```bash
pip install -e ".[dev]"
```

Optional extras:

```bash
pip install -e ".[basic-pitch]"
pip install -e ".[crepe]"
```

Or install runtime dependencies only:

```bash
pip install -r requirements.txt
```

## Quick Start

Run one transcription:

```bash
melonymind my_song.wav -o ./output
```

Use a trained melody-ranker model during transcription:

```bash
melonymind my_song.wav -o ./output --melody-ranker-model ./output/melody_ranker.json
```

Without installing the console script:

```bash
python -m melonymind.cli my_song.wav -o ./output
```

## Output Files

After a normal run, the output directory contains:

- `piano_score.ly`: LilyPond piano score
- `melody_sheet.html`: VexFlow melody rendering
- `jianpu.txt`: numbered notation text
- `jianpu.html`: numbered notation HTML
- `melody.mid`: extracted melody MIDI
- `piano_arrangement.mid`: melody plus piano accompaniment MIDI

## End-To-End Training Workflow

If you want to improve melody stem selection, the recommended workflow is:

1. Scan a folder of songs and generate draft labels
2. Review and correct the suggested labels
3. Build a finalized training manifest
4. Train a melody-ranker model
5. Use that model during transcription

### Step 1: Prepare Draft Labels

Put your songs in a folder, for example `./dataset`, then run:

```bash
melonymind-prepare-melody-data scan ./dataset
```

This creates:

- `./output/melody_label_suggestions.jsonl`
- `./output/melody_label_review.csv`

The system will auto-fill a suggested melody stem for each song.

### Step 2: Review Labels

Open `./output/melody_label_review.csv` and review each row.

Main columns:

- `audio_path`: source file
- `suggested_stem_name`: MelodyMind's current guess
- `target_stem_name`: the label you want to train on
- `label_status`: review state
- `candidate_scores_json`: current per-stem scores

For rows you approve:

1. Keep or edit `target_stem_name`
2. Set `label_status=confirmed`

Typical stem values are:

- `vocals`
- `mix`
- `accompaniment`
- `bass`

### Step 3: Build The Training Manifest

Once review is done:

```bash
melonymind-prepare-melody-data build-manifest ./output/melody_label_review.csv -o ./output/melody_manifest.jsonl
```

The generated manifest is the file the trainer consumes.

Manifest format:

```json
{"audio_path": "dataset/song_001.wav", "target_stem_name": "vocals"}
{"audio_path": "dataset/song_002.wav", "target_stem_name": "mix"}
```

### Step 4: Train The Melody Ranker

```bash
melonymind-train-melody-ranker ./output/melody_manifest.jsonl -o ./output/melody_ranker.json
```

Optional tuning:

```bash
melonymind-train-melody-ranker ./output/melody_manifest.jsonl -o ./output/melody_ranker.json --epochs 600 --learning-rate 0.03 --summary ./output/melody_ranker_metrics.json
```

Outputs:

- `melody_ranker.json`: trained weights
- `melody_ranker_metrics.json`: training metrics

### Step 5: Use The Trained Model

```bash
melonymind my_song.wav -o ./output --melody-ranker-model ./output/melody_ranker.json
```

## Recommended First Dataset

For a first training round, keep it small and clean:

- start with `30-100` songs
- prefer songs with a clear foreground melody
- avoid tracks where melody is buried in dense textures
- include both vocal-led and instrumental-led examples if you want both to work
- review labels carefully instead of trying to label a huge batch quickly

## Python Example

```python
from melonymind import AudioProcessor, PitchDetector, SheetGenerator
from melonymind.core.pitch_detector import DetectionMode

processor = AudioProcessor()
audio, sr = processor.load("my_song.wav")
audio = processor.normalize(audio)
audio = processor.trim_silence(audio)

detector = PitchDetector(mode=DetectionMode.PYIN)
notes = detector.detect(audio, sr)

generator = SheetGenerator()
lilypond_code = generator.generate_lilypond(notes)

with open("output.ly", "w", encoding="utf-8") as handle:
    handle.write(lilypond_code)
```

## Command Reference

Main transcription command:

```bash
melonymind INPUT_AUDIO -o OUTPUT_DIR [--melody-ranker-model MODEL_JSON]
```

Draft-label preparation:

```bash
melonymind-prepare-melody-data scan INPUT_DIR [--jsonl-output PATH] [--csv-output PATH]
```

Build reviewed manifest:

```bash
melonymind-prepare-melody-data build-manifest REVIEW_FILE -o OUTPUT_MANIFEST
```

Train melody ranker:

```bash
melonymind-train-melody-ranker MANIFEST_JSONL -o MODEL_JSON [--summary PATH] [--epochs N] [--learning-rate LR]
```

Module equivalents:

```bash
python -m melonymind.cli my_song.wav -o ./output
python -m melonymind.training.prepare_melody_ranker_data scan ./dataset
python -m melonymind.training.prepare_melody_ranker_data build-manifest ./output/melody_label_review.csv -o ./output/melody_manifest.jsonl
python -m melonymind.training.train_melody_ranker ./output/melody_manifest.jsonl -o ./output/melody_ranker.json
```

## Project Structure

```text
MelodyMind/
|-- melonymind/
|   |-- cli.py
|   |-- core/
|   |   |-- audio_processor.py
|   |   |-- arranger.py
|   |   |-- midi_exporter.py
|   |   `-- pitch_detector.py
|   |-- models/
|   |   |-- basic_pitch.py
|   |   |-- chord_predictor.py
|   |   |-- melody_ranker.py
|   |   `-- training_notes.py
|   |-- notation/
|   |   |-- jianpu_generator.py
|   |   `-- sheet_generator.py
|   `-- training/
|       |-- dataset_prep.py
|       |-- melody_ranker_trainer.py
|       |-- prepare_melody_ranker_data.py
|       `-- train_melody_ranker.py
|-- examples/
|-- tests/
|-- requirements.txt
`-- setup.py
```

## Roadmap

- Replace heuristic stem separation with a stronger learned separator
- Upgrade melody ranker from linear model to a stronger classifier or ranker
- Add learned chord prediction
- Add richer score exports such as MusicXML
- Improve note segmentation and phrasing

## License

This project is licensed under the MIT License.

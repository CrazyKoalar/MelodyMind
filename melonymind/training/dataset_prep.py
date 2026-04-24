"""Dataset preparation and semi-automatic labeling for melody ranker training."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

from ..core.audio_processor import AudioProcessor
from ..core.pitch_detector import DetectionMode, PitchDetector


SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}


@dataclass
class LabelSuggestion:
    """One semi-automatic annotation suggestion for a song."""

    audio_path: str
    suggested_stem_name: str
    target_stem_name: str
    label_status: str
    candidate_scores: dict

    def to_json(self) -> str:
        return json.dumps(
            {
                "audio_path": self.audio_path,
                "suggested_stem_name": self.suggested_stem_name,
                "target_stem_name": self.target_stem_name,
                "label_status": self.label_status,
                "candidate_scores": self.candidate_scores,
            },
            ensure_ascii=True,
        )


class MelodyDatasetPreparer:
    """Scan audio collections and create draft labels for human review."""

    def __init__(
        self,
        sample_rate: int = 22050,
        detector_mode: DetectionMode = DetectionMode.PYIN,
        min_confidence: float = 0.55,
    ):
        self.audio_processor = AudioProcessor(sample_rate=sample_rate)
        self.detector = PitchDetector(mode=detector_mode)
        self.min_confidence = min_confidence

    def scan_audio_files(self, root_dir: str | Path) -> List[Path]:
        root = Path(root_dir)
        files = [
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS
        ]
        return sorted(files)

    def suggest_label_for_file(self, audio_path: str | Path) -> LabelSuggestion:
        audio, sr = self.audio_processor.load(str(audio_path))
        audio = self.audio_processor.normalize(audio)
        audio = self.audio_processor.trim_silence(audio)
        stems = self.audio_processor.separate_sources(audio, sr)
        selection = self.audio_processor.choose_melody_stem(
            stems,
            sr,
            self.detector,
            min_confidence=self.min_confidence,
        )
        return LabelSuggestion(
            audio_path=str(Path(audio_path)),
            suggested_stem_name=selection.stem_name,
            target_stem_name=selection.stem_name,
            label_status="suggested",
            candidate_scores=selection.stem_scores,
        )

    def create_draft_labels(
        self, audio_paths: Sequence[str | Path]
    ) -> List[LabelSuggestion]:
        return [self.suggest_label_for_file(path) for path in audio_paths]


def write_label_suggestions_jsonl(
    suggestions: Iterable[LabelSuggestion], output_path: str | Path
) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [suggestion.to_json() for suggestion in suggestions]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return str(path)


def write_label_review_csv(
    suggestions: Iterable[LabelSuggestion], output_path: str | Path
) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "audio_path",
                "suggested_stem_name",
                "target_stem_name",
                "label_status",
                "candidate_scores_json",
            ],
        )
        writer.writeheader()
        for suggestion in suggestions:
            writer.writerow(
                {
                    "audio_path": suggestion.audio_path,
                    "suggested_stem_name": suggestion.suggested_stem_name,
                    "target_stem_name": suggestion.target_stem_name,
                    "label_status": suggestion.label_status,
                    "candidate_scores_json": json.dumps(
                        suggestion.candidate_scores, ensure_ascii=True, sort_keys=True
                    ),
                }
            )
    return str(path)


def build_manifest_from_review_file(
    review_path: str | Path,
    output_path: str | Path,
    accepted_statuses: Sequence[str] = ("confirmed", "approved", "accepted"),
) -> str:
    review = Path(review_path)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    accepted = {status.lower() for status in accepted_statuses}
    rows = _load_review_rows(review)
    manifest_lines = []
    for row in rows:
        status = row.get("label_status", "").strip().lower()
        target = row.get("target_stem_name", "").strip()
        audio_path = row.get("audio_path", "").strip()
        if status not in accepted or not target or not audio_path:
            continue
        manifest_lines.append(
            json.dumps(
                {"audio_path": audio_path, "target_stem_name": target},
                ensure_ascii=True,
            )
        )

    output.write_text("\n".join(manifest_lines) + ("\n" if manifest_lines else ""), encoding="utf-8")
    return str(output)


def _load_review_rows(review_path: Path) -> List[dict]:
    if review_path.suffix.lower() == ".jsonl":
        rows = []
        for raw_line in review_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line:
                rows.append(json.loads(line))
        return rows

    if review_path.suffix.lower() == ".csv":
        with review_path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    raise ValueError(f"unsupported review file format: {review_path.suffix}")

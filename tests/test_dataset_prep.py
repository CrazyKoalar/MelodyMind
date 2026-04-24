"""Tests for melody-ranker dataset preparation utilities."""

import csv
import json

from melonymind.training.dataset_prep import (
    LabelSuggestion,
    MelodyDatasetPreparer,
    build_manifest_from_review_file,
    write_label_review_csv,
    write_label_suggestions_jsonl,
)


def test_scan_audio_files_filters_supported_extensions(local_tmp_path):
    (local_tmp_path / "a.wav").write_text("x", encoding="utf-8")
    (local_tmp_path / "b.mp3").write_text("x", encoding="utf-8")
    (local_tmp_path / "c.txt").write_text("x", encoding="utf-8")

    preparer = MelodyDatasetPreparer()
    files = preparer.scan_audio_files(local_tmp_path)

    assert [path.name for path in files] == ["a.wav", "b.mp3"]


def test_write_label_suggestions_jsonl_creates_expected_lines(local_tmp_path):
    output_path = local_tmp_path / "suggestions.jsonl"
    suggestions = [
        LabelSuggestion(
            audio_path="song.wav",
            suggested_stem_name="vocals",
            target_stem_name="vocals",
            label_status="suggested",
            candidate_scores={"vocals": 0.9, "mix": 0.2},
        )
    ]

    write_label_suggestions_jsonl(suggestions, output_path)
    lines = output_path.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["target_stem_name"] == "vocals"


def test_write_label_review_csv_creates_reviewable_table(local_tmp_path):
    output_path = local_tmp_path / "review.csv"
    suggestions = [
        LabelSuggestion(
            audio_path="song.wav",
            suggested_stem_name="vocals",
            target_stem_name="mix",
            label_status="confirmed",
            candidate_scores={"vocals": 0.9},
        )
    ]

    write_label_review_csv(suggestions, output_path)
    with output_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows[0]["audio_path"] == "song.wav"
    assert rows[0]["label_status"] == "confirmed"


def test_build_manifest_from_review_csv_filters_confirmed_rows(local_tmp_path):
    review_path = local_tmp_path / "review.csv"
    review_path.write_text(
        "\n".join(
            [
                "audio_path,suggested_stem_name,target_stem_name,label_status,candidate_scores_json",
                'song_a.wav,vocals,vocals,confirmed,"{""vocals"": 0.9}"',
                'song_b.wav,mix,mix,suggested,"{""mix"": 0.8}"',
            ]
        ),
        encoding="utf-8",
    )
    manifest_path = local_tmp_path / "manifest.jsonl"

    build_manifest_from_review_file(review_path, manifest_path)
    lines = manifest_path.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 1
    assert json.loads(lines[0])["audio_path"] == "song_a.wav"


def test_build_manifest_from_review_jsonl_filters_confirmed_rows(local_tmp_path):
    review_path = local_tmp_path / "review.jsonl"
    review_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "audio_path": "song_a.wav",
                        "target_stem_name": "vocals",
                        "label_status": "confirmed",
                    }
                ),
                json.dumps(
                    {
                        "audio_path": "song_b.wav",
                        "target_stem_name": "mix",
                        "label_status": "suggested",
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    manifest_path = local_tmp_path / "manifest.jsonl"

    build_manifest_from_review_file(review_path, manifest_path)

    assert manifest_path.read_text(encoding="utf-8").count("\n") == 1

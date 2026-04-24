"""Tests for melody-ranker data preparation CLI."""

from melonymind.training import prepare_melody_ranker_data as prep_cli


class DummyPreparer:
    def scan_audio_files(self, input_dir):
        return ["song_a.wav", "song_b.wav"]

    def create_draft_labels(self, audio_paths):
        return [
            type(
                "Suggestion",
                (),
                {
                    "audio_path": path,
                    "suggested_stem_name": "vocals",
                    "target_stem_name": "vocals",
                    "label_status": "suggested",
                    "candidate_scores": {"vocals": 0.9},
                    "to_json": lambda self: "",
                },
            )()
            for path in audio_paths
        ]


def test_scan_command_writes_outputs(monkeypatch, local_tmp_path):
    jsonl_path = local_tmp_path / "draft.jsonl"
    csv_path = local_tmp_path / "draft.csv"
    calls = {}

    monkeypatch.setattr(prep_cli, "MelodyDatasetPreparer", DummyPreparer)

    def fake_write_jsonl(suggestions, output_path):
        calls["jsonl_count"] = len(suggestions)
        calls["jsonl_output"] = output_path
        return str(jsonl_path)

    def fake_write_csv(suggestions, output_path):
        calls["csv_count"] = len(suggestions)
        calls["csv_output"] = output_path
        return str(csv_path)

    monkeypatch.setattr(prep_cli, "write_label_suggestions_jsonl", fake_write_jsonl)
    monkeypatch.setattr(prep_cli, "write_label_review_csv", fake_write_csv)

    exit_code = prep_cli.main(
        [
            "scan",
            "dataset",
            "--jsonl-output",
            str(jsonl_path),
            "--csv-output",
            str(csv_path),
        ]
    )

    assert exit_code == 0
    assert calls["jsonl_count"] == 2
    assert calls["csv_count"] == 2


def test_build_manifest_command_calls_converter(monkeypatch, local_tmp_path):
    review_path = local_tmp_path / "review.csv"
    manifest_path = local_tmp_path / "manifest.jsonl"
    calls = {}

    def fake_build(review_file, output_path):
        calls["review_file"] = review_file
        calls["output_path"] = output_path
        return str(manifest_path)

    monkeypatch.setattr(prep_cli, "build_manifest_from_review_file", fake_build)

    exit_code = prep_cli.main(
        ["build-manifest", str(review_path), "-o", str(manifest_path)]
    )

    assert exit_code == 0
    assert calls["review_file"] == str(review_path)
    assert calls["output_path"] == str(manifest_path)

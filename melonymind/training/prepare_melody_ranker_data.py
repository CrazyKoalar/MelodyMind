"""CLI for preparing and finalizing melody-ranker training labels."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .dataset_prep import (
    MelodyDatasetPreparer,
    build_manifest_from_review_file,
    write_label_review_csv,
    write_label_suggestions_jsonl,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare draft labels and final manifests for melody-ranker training."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan an audio directory and create draft label suggestions.",
    )
    scan_parser.add_argument("input_dir", help="Directory containing audio files.")
    scan_parser.add_argument(
        "--jsonl-output",
        default="./output/melody_label_suggestions.jsonl",
        help="Path to write draft JSONL suggestions.",
    )
    scan_parser.add_argument(
        "--csv-output",
        default="./output/melody_label_review.csv",
        help="Path to write a review-friendly CSV.",
    )

    build_parser_cmd = subparsers.add_parser(
        "build-manifest",
        help="Convert reviewed labels into a training manifest.",
    )
    build_parser_cmd.add_argument(
        "review_file",
        help="Reviewed CSV or JSONL file containing target_stem_name and label_status.",
    )
    build_parser_cmd.add_argument(
        "-o",
        "--output",
        default="./output/melody_manifest.jsonl",
        help="Path to write the finalized training manifest.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "scan":
        preparer = MelodyDatasetPreparer()
        files = preparer.scan_audio_files(args.input_dir)
        suggestions = preparer.create_draft_labels(files)
        jsonl_path = write_label_suggestions_jsonl(suggestions, args.jsonl_output)
        csv_path = write_label_review_csv(suggestions, args.csv_output)
        print(f"Scanned {len(files)} audio files")
        print(f"Draft JSONL written to: {Path(jsonl_path).resolve()}")
        print(f"Review CSV written to: {Path(csv_path).resolve()}")
        print("Edit target_stem_name and set label_status=confirmed for accepted rows.")
        return 0

    if args.command == "build-manifest":
        manifest_path = build_manifest_from_review_file(args.review_file, args.output)
        print(f"Training manifest written to: {Path(manifest_path).resolve()}")
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())

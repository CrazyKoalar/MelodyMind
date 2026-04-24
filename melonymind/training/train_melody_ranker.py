"""Command-line training entry point for the melody stem ranker."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .melody_ranker_trainer import MelodyRankerTrainer, write_training_summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train MelodyMind's melody stem ranking model from a JSONL manifest."
    )
    parser.add_argument(
        "manifest",
        help="Path to a JSONL manifest. Each line must contain audio_path and target_stem_name.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="./output/melody_ranker.json",
        help="Path to save the trained melody ranker weights.",
    )
    parser.add_argument(
        "--summary",
        default="./output/melody_ranker_metrics.json",
        help="Path to save training metrics.",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=400,
        help="Number of gradient steps for the linear ranker.",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=0.05,
        help="Learning rate for the linear ranker.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        parser.error(f"manifest not found: {manifest_path}")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    summary_path = Path(args.summary)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    trainer = MelodyRankerTrainer()
    samples = trainer.load_manifest(manifest_path)
    dataset = trainer.build_dataset(samples)
    model = trainer.fit(
        dataset,
        learning_rate=args.learning_rate,
        epochs=args.epochs,
    )
    metrics = trainer.evaluate(model, dataset)

    model.save(output_path)
    write_training_summary(summary_path, metrics)

    print(f"Trained melody ranker on {metrics['sample_count']} songs")
    print(f"Top-1 training accuracy: {metrics['top1_accuracy']:.3f}")
    print(f"Model saved to: {output_path.resolve()}")
    print(f"Metrics saved to: {summary_path.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

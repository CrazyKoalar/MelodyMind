"""CLI entry point for the annotation web app."""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

from .config import AppConfig
from .server import create_app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local web tool for music professionals to review melody stem "
        "selections and correct extracted melody notes.",
    )
    parser.add_argument(
        "--dataset",
        required=True,
        help="Root folder containing audio files to annotate.",
    )
    parser.add_argument(
        "--state",
        required=True,
        help="Directory where SQLite state and stem cache will be stored.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--sample-rate", type=int, default=22050)
    parser.add_argument("--min-confidence", type=float, default=0.55)
    parser.add_argument(
        "--open",
        dest="open_browser",
        action="store_true",
        help="Open the default browser after the server is ready.",
    )
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="Allow binding to non-loopback hosts. The app has no authentication; "
        "use only on a trusted network.",
    )
    parser.add_argument("--log-level", default="info")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.host not in ("127.0.0.1", "localhost", "::1") and not args.allow_remote:
        print(
            f"Refusing to bind to {args.host} without --allow-remote (no auth).",
            file=sys.stderr,
        )
        return 2

    config = AppConfig(
        dataset_dir=Path(args.dataset),
        state_dir=Path(args.state),
        sample_rate=args.sample_rate,
        min_confidence=args.min_confidence,
        allow_remote=args.allow_remote,
    )
    config.ensure_dirs()

    try:
        import uvicorn
    except ImportError:
        print(
            "uvicorn is not installed. Install with: pip install 'uvicorn[standard]'",
            file=sys.stderr,
        )
        return 1

    app = create_app(config)
    if args.open_browser:
        webbrowser.open(f"http://{args.host}:{args.port}/")
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)
    return 0


if __name__ == "__main__":
    sys.exit(main())

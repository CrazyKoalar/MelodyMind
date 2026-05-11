"""Manifest export — writes trainer-compatible JSONL files."""

from __future__ import annotations

import csv
import json
import os
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from fastapi import APIRouter, Body, Depends
from fastapi.exceptions import HTTPException

from .config import AppConfig
from .deps import get_config, get_repo
from .state import STATUS_CONFIRMED, SongRow, StateRepo


router = APIRouter(prefix="/api")


MANIFEST_FILENAME = "melody_manifest.jsonl"
NOTES_MANIFEST_FILENAME = "melody_notes_manifest.jsonl"
REVIEW_CSV_FILENAME = "melody_review.csv"


@dataclass
class ExportResult:
    melody_manifest: Path
    notes_manifest: Path
    review_csv: Path
    count: int


def export_manifests(
    config: AppConfig,
    repo: StateRepo,
    *,
    only_confirmed: bool = True,
) -> ExportResult:
    """Write the three export files. Returns the absolute paths and exported count.

    - `melody_manifest.jsonl` matches the exact format read by
      `melonymind.training.dataset_prep.build_manifest_from_review_file`.
    - `melody_notes_manifest.jsonl` adds the edited note array — schema for a
      future note-supervised trainer.
    - `melody_review.csv` mirrors the legacy review CSV columns so existing
      tooling keeps working.
    """
    config.ensure_dirs()
    statuses = [STATUS_CONFIRMED] if only_confirmed else None
    rows = repo.list_songs_by_status(statuses) if statuses else repo.list_songs()

    melody_path = config.export_dir / MANIFEST_FILENAME
    notes_path = config.export_dir / NOTES_MANIFEST_FILENAME
    review_path = config.export_dir / REVIEW_CSV_FILENAME

    _write_melody_manifest(melody_path, rows)
    _write_notes_manifest(notes_path, rows, repo=repo, sr=config.sample_rate)
    _write_review_csv(review_path, rows)

    return ExportResult(
        melody_manifest=melody_path,
        notes_manifest=notes_path,
        review_csv=review_path,
        count=len(rows),
    )


def _write_melody_manifest(path: Path, rows: Iterable[SongRow]) -> None:
    lines: List[str] = []
    for row in rows:
        if not row.picked_stem:
            continue
        lines.append(
            json.dumps(
                {
                    "audio_path": row.audio_path,
                    "target_stem_name": row.picked_stem,
                },
                ensure_ascii=True,
            )
        )
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _write_notes_manifest(
    path: Path,
    rows: Iterable[SongRow],
    *,
    repo: StateRepo,
    sr: int,
) -> None:
    lines: List[str] = []
    for row in rows:
        if not row.picked_stem:
            continue
        notes_row = repo.get_notes(row.id, row.picked_stem)
        notes = notes_row.notes if notes_row else []
        lines.append(
            json.dumps(
                {
                    "audio_path": row.audio_path,
                    "target_stem_name": row.picked_stem,
                    "sr": sr,
                    "notes": notes,
                },
                ensure_ascii=True,
            )
        )
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _write_review_csv(path: Path, rows: Iterable[SongRow]) -> None:
    """Mirror columns used by melonymind.training.dataset_prep.write_label_review_csv."""
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
        for row in rows:
            suggested = (
                max(row.candidate_scores, key=row.candidate_scores.get)
                if row.candidate_scores
                else (row.picked_stem or "")
            )
            writer.writerow(
                {
                    "audio_path": row.audio_path,
                    "suggested_stem_name": suggested,
                    "target_stem_name": row.picked_stem or "",
                    "label_status": "confirmed" if row.status == STATUS_CONFIRMED else row.status,
                    "candidate_scores_json": json.dumps(
                        row.candidate_scores, ensure_ascii=True, sort_keys=True
                    ),
                }
            )


@router.post("/export")
def export_endpoint(
    body: dict | None = Body(default=None),
    config: AppConfig = Depends(get_config),
    repo: StateRepo = Depends(get_repo),
) -> dict:
    only_confirmed = bool((body or {}).get("only_confirmed", True))
    try:
        result = export_manifests(config, repo, only_confirmed=only_confirmed)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"export failed: {exc}")
    return {
        "melody_manifest": str(result.melody_manifest),
        "notes_manifest": str(result.notes_manifest),
        "review_csv": str(result.review_csv),
        "export_dir": str(config.export_dir),
        "count": result.count,
    }


@router.post("/reveal")
def reveal_in_explorer(
    body: dict = Body(...),
    config: AppConfig = Depends(get_config),
) -> dict:
    """Open the given path in the OS file manager.

    Local-only, no auth. Safe-guards: the path must be inside the configured
    state dir so a hostile request can't open arbitrary locations.
    """
    raw = body.get("path")
    if not raw:
        raise HTTPException(status_code=400, detail="path is required")
    target = Path(raw).resolve()
    try:
        target.relative_to(config.state_dir)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="path must live inside the state directory"
        )
    if not target.exists():
        raise HTTPException(status_code=404, detail="path does not exist")

    system = platform.system()
    folder = target if target.is_dir() else target.parent
    try:
        if system == "Windows":
            if target.is_file():
                subprocess.Popen(["explorer", "/select,", str(target)])
            else:
                os.startfile(str(folder))  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.Popen(["open", "-R", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"could not open: {exc}")
    return {"opened": str(target)}

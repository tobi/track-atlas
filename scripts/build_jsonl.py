#!/usr/bin/env python3
"""Build tracks.jsonl at the repo root -- the dataset.

One line per track: the complete tracks/<slug>/raw/track.json, compacted. This
is the headline artifact of the repo: a single newline-delimited JSON file you
can stream, grep, or load with one line of pandas / jq. Run after generate.

Usage:
    uv run python scripts/build_jsonl.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.config import TRACKS  # noqa: E402

ROOT = TRACKS.parent
OUT = ROOT / "tracks.jsonl"


def main() -> None:
    lines = []
    for p in sorted(TRACKS.iterdir()):
        tj = p / "raw" / "track.json"
        if not tj.exists():
            continue
        track = json.loads(tj.read_text())
        lines.append(json.dumps(track, ensure_ascii=False, separators=(",", ":")))
    OUT.write_text("\n".join(lines) + "\n")
    kb = OUT.stat().st_size / 1024
    print(f"tracks.jsonl written ({len(lines)} tracks, {kb:.0f} KB)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Apply measured surface geometry to raw/track.json (offline).

For every layout with a committed `raw/surface-<layout>.json` (see
measure_surface.py) this writes `raw/layers/<layout>.surface.geojson` and adds
`surface`, corner `entry`/`apex`/`exit`, layout-point `line` and range
`start_line`/`end_line` (complexes also `entry`/`exit`) to raw/track.json.
generate.py and build_layers.py call it automatically.

Usage:
    uv run python scripts/build_geometry.py road-atlanta
    uv run python scripts/build_geometry.py --all
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.config import TRACKS, raw_dir, track_json_path  # noqa: E402
from lib.surface import apply_track  # noqa: E402


def build(slug: str) -> dict:
    path = track_json_path(slug)
    track = json.loads(path.read_text())
    apply_track(raw_dir(slug), track)
    path.write_text(json.dumps(track, ensure_ascii=False, indent=2))
    for lo in track["layouts"]:
        if lo.get("surface"):
            s = lo["surface"]
            print(f"[{slug}/{lo['id']}] surface geometry applied: {s['file']} "
                  f"(width median {s['width_m']['median']} m, seen {s['seen_fraction']['both']:.0%})")
    return track


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--no-dataset", action="store_true", help="skip index/jsonl refresh")
    args = ap.parse_args()
    if args.all:
        slugs = sorted(p.name for p in TRACKS.iterdir() if track_json_path(p.name).exists())
    elif args.slug:
        slugs = [args.slug]
    else:
        ap.error("give a slug or --all")
    for slug in slugs:
        build(slug)
    if not args.no_dataset:
        import runpy
        here = Path(__file__).resolve().parent
        runpy.run_path(str(here / "build_index.py"), run_name="__main__")
        runpy.run_path(str(here / "build_jsonl.py"), run_name="__main__")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run per-track layer configs and merge produced layers into raw/track.json.

This is useful after editing tracks/<slug>/generation-config.json without
re-running the whole source import/generate step. generate.py also calls this automatically for
each track after it writes the base track.json.

Usage:
    uv run python scripts/build_layers.py watkins-glen
    uv run python scripts/build_layers.py --all
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.config import TRACKS  # noqa: E402
from lib.layer_runner import run_layer_configs  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    if args.all:
        slugs = [p.name for p in TRACKS.iterdir() if (p / "source.json").exists()]
    elif args.slug:
        slugs = [args.slug]
    else:
        ap.error("give a slug or --all")
    for slug in slugs:
        if not (TRACKS / slug / "generation-config.json").exists():
            continue
        track = run_layer_configs(slug, write=True)
        n = sum(len(lo.get("point_layers", [])) + len(lo.get("range_layers", [])) for lo in track.get("layouts", []))
        print(f"[{slug}] layer configs applied ({n} total point/range layers)")

    # Keep headline dataset fresh when this script is run directly.
    import runpy
    here = Path(__file__).resolve().parent
    runpy.run_path(str(here / "build_index.py"), run_name="__main__")
    runpy.run_path(str(here / "build_jsonl.py"), run_name="__main__")


if __name__ == "__main__":
    main()

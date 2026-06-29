#!/usr/bin/env python3
"""Check corner apexes against geometry-derived curvature apex candidates.

This is a read-only diagnostic built on scripts/layer_tools/curvature_apexes.py.
It is useful when corner names/numbers look plausible but apex coordinates or
markers feel wrong.

Usage:
    uv run python scripts/check_apexes.py watkins-glen
    uv run python scripts/check_apexes.py --all
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from layer_tools.curvature_apexes import compute_layers as compute_curvature_layers  # noqa: E402
from lib.config import TRACKS, raw_dir, track_json_path  # noqa: E402
from lib.osm import arc_lengths  # noqa: E402

WARN_M = 260.0


def circular_marker_distance(a: float, b: float) -> float:
    d = abs((a % 1.0) - (b % 1.0))
    return min(d, 1.0 - d)


def point_layer(layout: dict, layer_id: str) -> dict:
    return next((l for l in layout.get("point_layers", []) if l.get("id") == layer_id), {"items": []})


def outline_length(path: Path) -> float:
    gj = json.loads(path.read_text())
    outline = next((f for f in gj.get("features", []) if f.get("properties", {}).get("role") == "outline"), None)
    if not outline:
        return 0.0
    _, total = arc_lengths(outline["geometry"]["coordinates"])
    return total


def check(slug: str) -> int:
    track = json.loads(track_json_path(slug).read_text())
    print(f"\n== {slug} ==")
    warnings = 0
    for layout in track.get("layouts", []):
        corners = [c for c in point_layer(layout, "corners").get("items", []) if c.get("marker") is not None]
        gpath = raw_dir(slug) / (layout.get("geometry", {}).get("centerline") or "")
        if not corners or not gpath.exists():
            print(f"  [{layout.get('id')}] skipped")
            continue
        total = outline_length(gpath) or float(layout.get("length_m") or 0)
        curv = compute_curvature_layers(str(gpath), {
            "max_apexes": max(16, len(corners) * 2),
            "min_separation_m": 60.0,
            "smooth_window_m": 70.0,
            "curvature_percentile": 0.65,
        }, {"relative_path": str(gpath)})
        apexes = curv.get("point_layers", [{}])[0].get("items", [])
        print(f"  [{layout['id']}] {len(corners)} named corners, {len(apexes)} curvature apex candidates")
        print(f"    {'#':>3} {'corner':<26} {'marker':>7} {'nearest κ apex':>14} {'Δ':>6}")
        for c in sorted(corners, key=lambda x: x.get("number") or 0):
            nearest = min(apexes, key=lambda a: circular_marker_distance(c["marker"], a.get("marker", 0.0))) if apexes else None
            if nearest:
                dm = circular_marker_distance(c["marker"], nearest.get("marker", 0.0)) * total
                flag = " !" if dm > WARN_M else ""
                if flag:
                    warnings += 1
                print(f"    {str(c.get('code') or c.get('number')):>3} {str(c.get('label') or c.get('id'))[:26]:<26} "
                      f"{c['marker']:>7.4f} {nearest.get('marker', 0):>14.4f} {dm:>5.0f}m{flag}")
        ranges = curv.get("range_layers", [{}])[0].get("items", [])
        if ranges:
            print(f"    candidate ranges: " + ", ".join(f"{x['id']} {x['start']:.3f}-{x['end']:.3f}" for x in ranges[:12]))
            if len(ranges) > 12:
                print(f"    ... {len(ranges) - 12} more")
    return warnings


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    slugs = ([p.name for p in sorted(TRACKS.iterdir()) if (p / "raw" / "track.json").exists()]
             if args.all else [args.slug])
    if not slugs or slugs == [None]:
        ap.error("give a slug or --all")
    total_warnings = sum(check(slug) for slug in slugs)
    if total_warnings:
        print(f"\nWARN: {total_warnings} named corner(s) are far from the nearest curvature apex candidate")


if __name__ == "__main__":
    main()

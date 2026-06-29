#!/usr/bin/env python3
"""Preview corner phases (braking-zone start / apex / exit) for a track.

Corner phases are generated into layout.range_layers[id=corner_ranges] by
generate.py via lib/phases.py. This tool recomputes them with the same logic so
you can tune the BRAKE_M / EXIT_M distance tables in lib/phases.py and preview
the result before re-running generate. It prints a table; it writes nothing.

Usage:
    uv run python scripts/suggest_phases.py silverstone
    uv run python scripts/suggest_phases.py --all
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.config import TRACKS, raw_dir, track_json_path  # noqa: E402
from lib.osm import arc_lengths  # noqa: E402
from lib.naming import SCALE_LABELS  # noqa: E402
from lib.phases import compute_phases  # noqa: E402


def layout_length_m(layout: dict, rawd: Path) -> float | None:
    if layout.get("length_m"):
        return float(layout["length_m"])
    gpath = rawd / (layout.get("geometry", {}).get("centerline") or "")
    if gpath.exists():
        gj = json.loads(gpath.read_text())
        for f in gj.get("features", []):
            if f.get("properties", {}).get("role") == "outline":
                _, total = arc_lengths(f["geometry"]["coordinates"])
                return total
    return None


def preview(slug: str) -> None:
    rawd = raw_dir(slug)
    track = json.loads(track_json_path(slug).read_text())
    print(f"\n== {slug} ==")
    for layout in track["layouts"]:
        total = layout_length_m(layout, rawd)
        if not total:
            print(f"  [{layout['id']}] no length -- skipped")
            continue
        corners = next((l.get("items", []) for l in layout.get("point_layers", []) if l.get("id") == "corners"), [])
        # compute_phases predates range_layers and consumes a compact corner dict.
        compact = [{"number": c["number"], "code": c.get("code"), "marker": c.get("marker"),
                    "scale": c.get("scale")} for c in corners]
        by_id = {c["id"]: c for c in compact}
        for comp in next((l.get("items", []) for l in layout.get("range_layers", []) if l.get("id") == "corner_complexes"), []):
            for mid in comp.get("members", []):
                if mid in by_id:
                    by_id[mid]["complex"] = comp.get("label")
        ph = compute_phases(compact, total)
        by_num = {c["number"]: c for c in compact}
        print(f"  [{layout['id']}] {round(total)} m, {len(ph)} corners")
        print(f"    {'#':>3} {'scale':<11} {'start':>7} {'apex':>7} {'end':>7}  span  complex")
        for num, p in sorted(ph.items()):
            c = by_num[num]
            span_m = round(((p['end'] - p['start']) % 1.0) * total)
            tag = "" if p["brakes"] else "  (no brake)"
            print(f"    {c.get('code', num):>3} {SCALE_LABELS.get(c.get('scale'), ''):<11} "
                  f"{p['start']:>7.4f} {p['apex']:>7.4f} {p['end']:>7.4f}  {span_m:>4}m  "
                  f"{c.get('complex') or ''}{tag}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    slugs = ([p.name for p in sorted(TRACKS.iterdir()) if (p / "raw" / "track.json").exists()]
             if args.all else [args.slug])
    if not slugs or slugs == [None]:
        ap.error("give a slug or --all")
    for slug in slugs:
        preview(slug)


if __name__ == "__main__":
    main()

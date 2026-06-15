#!/usr/bin/env python3
"""Suggest corner phases -- braking-zone start / apex / corner-exit -- for review.

A corner doesn't begin at the apex: for anything you brake for, it starts a few
hundred metres earlier (turn-in / brake point) and ends a few seconds into the
throttle on exit. How early depends on severity: a hairpin (scale 1) has a long
braking zone; a fast kink (scale 6) has none. This script proposes start/apex/end
as lap fractions from each corner's apex marker and its severity, then resolves
neighbours so phases never overlap -- and so corners inside one complex meet
exactly (Porsche Curves: curve 1 ends where curve 2 starts).

It writes tracks/<slug>/raw/phases.suggested.json (a REVIEW artifact, not authoritative
data) and prints a table. Tune BRAKE_M / EXIT_M, then hand-edit the output.

Usage:
    uv run python scripts/suggest_phases.py silverstone
    uv run python scripts/suggest_phases.py --all
    uv run python scripts/suggest_phases.py silverstone --no-write   # print only
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

# Approximate braking distance (before apex) and exit distance (after apex), in
# metres, by corner severity. 1 = hairpin (long brake), 6 = flat-out kink (none).
# Deliberately rough -- they're starting points for human tuning.
BRAKE_M = {1: 250, 2: 180, 3: 120, 4: 70, 5: 35, 6: 0}
EXIT_M = {1: 170, 2: 130, 3: 100, 4: 70, 5: 45, 6: 0}
DEFAULT_SCALE = 3  # when a corner has no scale, assume a medium corner


def _frac(m: float) -> float:
    """Wrap a lap fraction into [0,1)."""
    return m % 1.0


def _cyc_gap(a: float, b: float) -> float:
    """Forward cyclic distance from a to b (both lap fractions)."""
    return (b - a) % 1.0


def layout_length_m(layout: dict, rawd: Path) -> float | None:
    if layout.get("length_m"):
        return float(layout["length_m"])
    gpath = rawd / (layout.get("geometry", {}).get("outline") or "")
    if gpath.exists():
        gj = json.loads(gpath.read_text())
        for f in gj.get("features", []):
            if f.get("properties", {}).get("role") == "outline":
                _, total = arc_lengths(f["geometry"]["coordinates"])
                return total
    return None


def suggest_layout(layout: dict, total_m: float) -> list[dict]:
    """Return per-corner phase suggestions (sorted by apex), overlaps resolved."""
    cs = [c for c in layout.get("corners", []) if c.get("marker") is not None]
    cs.sort(key=lambda c: c["marker"])
    if not cs:
        return []

    ph = []
    for c in cs:
        scale = c.get("scale") or DEFAULT_SCALE
        brake_m, exit_m = BRAKE_M.get(scale, 120), EXIT_M.get(scale, 100)
        apex = _frac(c["marker"])
        ph.append({
            "number": c["number"], "code": c.get("code", str(c["number"])),
            "scale": scale, "scale_label": SCALE_LABELS.get(scale, ""),
            "brakes": brake_m > 0, "complex": c.get("complex"),
            "apex": apex,
            "_brake_f": brake_m / total_m, "_exit_f": exit_m / total_m,
            "start": _frac(apex - brake_m / total_m),
            "end": _frac(apex + exit_m / total_m),
        })

    # Resolve each adjacent pair (cyclic). Two corners share a boundary when their
    # phases would overlap, OR when they belong to the same complex (they must
    # meet with no gap). The boundary sits between the apexes in proportion to the
    # leaving corner's exit vs the arriving corner's braking need.
    n = len(ph)
    for i in range(n):
        a, b = ph[i], ph[(i + 1) % n]
        gap = _cyc_gap(a["apex"], b["apex"])
        want = a["_exit_f"] + b["_brake_f"]
        same_complex = a["complex"] and a["complex"] == b["complex"]
        if want > gap or same_complex:
            split = (a["_exit_f"] / want) if want > 0 else 0.5
            boundary = _frac(a["apex"] + gap * split)
            a["end"] = boundary
            b["start"] = boundary

    for p in ph:
        p.pop("_brake_f", None)
        p.pop("_exit_f", None)
        for k in ("apex", "start", "end"):
            p[k] = round(p[k], 5)
    return ph


def suggest_track(slug: str, write: bool) -> None:
    rawd = raw_dir(slug)
    track = json.loads(track_json_path(slug).read_text())
    out = {}
    print(f"\n== {slug} ==")
    for layout in track["layouts"]:
        total = layout_length_m(layout, rawd)
        if not total:
            print(f"  [{layout['id']}] no length -- skipped")
            continue
        ph = suggest_layout(layout, total)
        out[layout["id"]] = {
            "note": ("suggested corner phases as lap fractions (start/apex/end). "
                     "Heuristic from severity; review and edit. Not authoritative."),
            "corners": {str(p["number"]): p for p in ph},
        }
        print(f"  [{layout['id']}] {layout.get('length_m') or round(total)} m, {len(ph)} corners")
        print(f"    {'#':>3} {'scale':<11} {'start':>7} {'apex':>7} {'end':>7}  span  complex")
        for p in ph:
            span_m = round(_cyc_gap(p["start"], p["end"]) * total)
            brake = "" if p["brakes"] else "  (no brake)"
            print(f"    {p['code']:>3} {p['scale_label']:<11} {p['start']:>7.4f} "
                  f"{p['apex']:>7.4f} {p['end']:>7.4f}  {span_m:>4}m  "
                  f"{p['complex'] or ''}{brake}")
    if write:
        dest = rawd / "phases.suggested.json"
        dest.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
        print(f"  -> wrote {dest.relative_to(TRACKS.parent)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--no-write", action="store_true", help="print only, don't write files")
    args = ap.parse_args()
    slugs = ([p.name for p in sorted(TRACKS.iterdir()) if (p / "raw" / "track.json").exists()]
             if args.all else [args.slug])
    if not slugs or slugs == [None]:
        ap.error("give a slug or --all")
    for slug in slugs:
        suggest_track(slug, write=not args.no_write)


if __name__ == "__main__":
    main()

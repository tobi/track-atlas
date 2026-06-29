#!/usr/bin/env python3
"""Audit corner naming/curation signals across Track Atlas.

This is deliberately read-only. It is the starting point for data-cleanup passes:
compare current labels with OSM named raceway ways by lap position, find unnamed
non-fast corners, duplicate apex markers, and corner-group coverage issues.

Usage:
    uv run python scripts/check_corner_curation.py sebring
    uv run python scripts/check_corner_curation.py --all
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.config import TRACKS, raw_dir, track_json_path  # noqa: E402
from lib.osm import arc_lengths, centroid, named_corner_ways, nearest_fraction, normalize  # noqa: E402
from layer_tools.curvature_apexes import compute_layers as compute_curvature_layers  # noqa: E402

INFRA = re.compile(
    r"(pit|lane|circuit|raceway|speedway|autodrome|autódromo|hungaroring|layout|track|course|"
    r"straight|drag|rallycross|kart|skidpad|driving center|piste|glisse|runoff|bypass|"
    r"club|moto|safety|paddock|stands|stand|sortie|voie)",
    re.I,
)
MAX_CENTERLINE_SEGMENT_M = 60.0
MAX_BACKTRACK_ANGLE_DEG = 145.0
MAX_CORNER_TO_CURVATURE_APEX_M = 180.0


def labels_for(c: dict) -> list[str]:
    return [str(v) for k, v in (c.get("labels") or {}).items() if v]


def circular_delta(a: float, b: float) -> float:
    d = abs((a % 1.0) - (b % 1.0))
    return min(d, 1.0 - d)


def centerline_anomalies(loop: list[list[float]]):
    segs = []
    for i, (a, b) in enumerate(zip(loop, loop[1:])):
        # local import keeps this script's main signal imports obvious
        from lib.osm import haversine
        d = haversine(a, b)
        if d > MAX_CENTERLINE_SEGMENT_M:
            segs.append((i, d))
    backtracks = []
    for i in range(1, len(loop) - 1):
        a, b, c = loop[i - 1], loop[i], loop[i + 1]
        lat = math.radians(b[1])
        k = math.cos(lat)
        v1 = ((b[0] - a[0]) * k * 111320, (b[1] - a[1]) * 111320)
        v2 = ((c[0] - b[0]) * k * 111320, (c[1] - b[1]) * 111320)
        l1, l2 = math.hypot(*v1), math.hypot(*v2)
        if l1 < 10 or l2 < 10:
            continue
        dot = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (l1 * l2)))
        angle = math.degrees(math.acos(dot))
        if angle > MAX_BACKTRACK_ANGLE_DEG:
            backtracks.append((i, angle, l1, l2, b))
    return segs, backtracks


def audit(slug: str) -> int:
    track = json.loads(track_json_path(slug).read_text())
    osm_path = raw_dir(slug) / "osm.json"
    osm = json.loads(osm_path.read_text()) if osm_path.exists() else {"elements": []}
    print(f"\n== {slug} ==")
    issue_count = 0
    for layout in track.get("layouts", []):
        corners = next((l.get("items", []) for l in layout.get("point_layers", []) if l.get("id") == "corners"), [])
        groups = next((l.get("items", []) for l in layout.get("range_layers", []) if l.get("id") == "corner_complexes"), [])
        print(f"  [{layout['id']}] {len(corners)} corners")

        unnamed = [c for c in corners if (c.get("scale") or 0) < 5 and not any(k != "numbered" for k in c.get("labels", {}))]
        if unnamed:
            issue_count += len(unnamed)
            print("    unnamed non-fast:", ", ".join(f"T{c.get('code', c['number'])}" for c in unnamed))

        markers = [(c.get("marker"), c) for c in corners if c.get("marker") is not None]
        dupish = []
        for i, (ma, ca) in enumerate(markers):
            for mb, cb in markers[i + 1:]:
                if circular_delta(ma, mb) < 0.003 and ca["id"] != cb["id"]:
                    dupish.append((ca, cb, circular_delta(ma, mb)))
        if dupish:
            issue_count += len(dupish)
            print("    near-duplicate apex markers:", ", ".join(f"T{a['number']}↔T{b['number']}" for a, b, _ in dupish[:8]))

        member_counts = {}
        for g in groups:
            for mid in g.get("members", []):
                member_counts[mid] = member_counts.get(mid, 0) + 1
        required = {c["id"] for c in corners if (c.get("scale") or 0) < 5}
        missing = sorted(required - set(member_counts))
        dupes = sorted(mid for mid, n in member_counts.items() if n > 1)
        if missing or dupes:
            issue_count += len(missing) + len(dupes)
            print("    corner_complexes coverage:", f"missing={missing[:8]}", f"dupes={dupes[:8]}")

        gpath = raw_dir(slug) / (layout.get("geometry", {}).get("centerline") or "")
        if not (osm.get("elements") and gpath.exists()):
            continue
        gj = json.loads(gpath.read_text())
        outline = next((f for f in gj.get("features", []) if f.get("properties", {}).get("role") == "outline"), None)
        if not outline:
            continue
        loop = outline["geometry"]["coordinates"]
        long_segments, backtracks = centerline_anomalies(loop)
        if long_segments:
            issue_count += len(long_segments)
            print("    suspicious centerline long segments:", ", ".join(f"seg{i} {d:.0f}m" for i, d in long_segments[:8]))
        if backtracks:
            issue_count += len(backtracks)
            print("    suspicious centerline backtracking kinks:")
            for i, angle, l1, l2, pt in backtracks[:8]:
                print(f"      idx{i}: {angle:.0f}° ({l1:.0f}m→{l2:.0f}m) at {pt[0]:.6f},{pt[1]:.6f}")
        cum, total = arc_lengths(loop)
        try:
            curv = compute_curvature_layers(str(gpath), {
                "max_apexes": max(16, len(corners) * 2),
                "min_separation_m": 60.0,
                "smooth_window_m": 70.0,
                "curvature_percentile": 0.65,
            }, {"relative_path": str(gpath)})
            apexes = curv.get("point_layers", [{}])[0].get("items", [])
            straightish = []
            for c in corners:
                if c.get("marker") is None or not apexes:
                    continue
                nearest = min(apexes, key=lambda a: circular_delta(c["marker"], a.get("marker", 0.0)))
                dm = circular_delta(c["marker"], nearest.get("marker", 0.0)) * total
                if dm > MAX_CORNER_TO_CURVATURE_APEX_M:
                    straightish.append((c, nearest, dm))
            if straightish:
                issue_count += len(straightish)
                print("    apex markers far from curvature peaks (possible straight-line markers):")
                for c, apex, dm in straightish[:10]:
                    print(f"      T{c.get('code', c['number'])}: {dm:.0f}m from {apex.get('label')} at {apex.get('marker'):.4f}")
        except Exception as e:
            print(f"    curvature apex check skipped: {e}")

        suggestions = []
        for name, coords in named_corner_ways(osm.get("elements", [])):
            if INFRA.search(name):
                continue
            f, off = nearest_fraction(loop, cum, total, centroid(coords))
            if off > 90:
                continue
            nearest = min(corners, key=lambda c: circular_delta(c.get("marker") or 0.0, f))
            delta_m = circular_delta(nearest.get("marker") or 0.0, f) * total
            if delta_m > 140:
                continue
            current_norms = {normalize(x) for x in labels_for(nearest)}
            if normalize(name) not in current_norms:
                suggestions.append((nearest, name, delta_m, off))
        if suggestions:
            issue_count += len(suggestions)
            print("    OSM positional label candidates:")
            for c, name, delta_m, off in suggestions[:12]:
                current = " / ".join(labels_for(c))
                print(f"      T{c.get('code', c['number'])}: OSM {name!r} Δ{delta_m:.0f}m off{off:.0f}m; current {current!r}")
    return issue_count


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    slugs = ([p.name for p in sorted(TRACKS.iterdir()) if (p / "raw" / "track.json").exists()]
             if args.all else [args.slug])
    if not slugs or slugs == [None]:
        ap.error("give a slug or --all")
    total = sum(audit(slug) for slug in slugs)
    print(f"\nissues/signals: {total}")


if __name__ == "__main__":
    main()

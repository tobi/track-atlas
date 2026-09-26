#!/usr/bin/env python3
"""Measure a layout's track surface (left/right edges) from open imagery.

Network step (like import.py): fetches orthoimagery for the lap into the
gitignored cache `tracks/<slug>/raw/imagery/<source>/`, runs the edge extractor
(`lib/edges.py`, algorithm in docs/GEOMETRY.md) seeded by the layout
centerline, registers the result to the declared lidar references and moves it
to the atlas datum (`lib/position.py`), and writes the committed measurement

    tracks/<slug>/raw/surface-<layout>.json

(edges in the driving direction from the lap origin, quality, provenance).
generate.py / build_geometry.py consume it offline; nothing downstream needs
the imagery again.

Only tracks whose source.json declares a surface are measured:

    "surface": {"imagery": "naip", "lidar": ["GA_Statewide_B3_2018", "ARRA-GA_LakeLanier_2010"]}

`imagery` is a lib/imagery.SOURCES id; `lidar` lists USGS 3DEP EPT projects
(the first-listed stated-accuracy one that registers becomes the reference; the
rest are checks). `--find-lidar` lists the EPT projects covering a lap.

Usage:
    uv run python scripts/measure_surface.py road-atlanta
    uv run python scripts/measure_surface.py --all
    uv run python scripts/measure_surface.py --find-lidar road-atlanta
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import edges, geo, lidar, position  # noqa: E402
from lib.config import TRACKS, load_source, raw_dir  # noqa: E402
from lib.imagery import SOURCES, fetch_imagery, load_raster  # noqa: E402

EDGE_SIMPLIFY_M = 0.05     # Douglas-Peucker tolerance for the stored edges


def _outline(slug: str, layout_id: str) -> np.ndarray:
    gj = json.loads((raw_dir(slug) / "layers" / f"{layout_id}.geojson").read_text())
    f = next(f for f in gj["features"] if f["properties"].get("role") == "outline")
    return np.asarray(f["geometry"]["coordinates"], dtype=float)


def _spans(flags: np.ndarray, total: float, min_len: int = 5) -> list[list[float]]:
    """Lap-fraction spans [start, end] where flags is False (not seen)."""
    n = len(flags)
    bad = ~flags
    if bad.all():
        return [[0.0, 1.0]]
    # rotate so index 0 is seen: spans never wrap in the loop below
    k = int(np.argmax(~bad))
    b = np.roll(bad, -k)
    out, i = [], 0
    while i < n:
        if b[i]:
            j = i
            while j < n and b[j]:
                j += 1
            if j - i >= min_len:
                a0 = ((i + k) % n) / n
                a1 = ((j + k) % n) / n
                out.append([round(a0, 5), round(a1, 5)])
            i = j
        else:
            i += 1
    return sorted(out)


def measure(slug: str, layout_id: str, cfg: dict) -> dict:
    source_id = cfg["imagery"]
    src = SOURCES[source_id]
    seed_ll = _outline(slug, layout_id)
    cache = raw_dir(slug) / "imagery" / source_id
    fetch_imagery(cache, seed_ll, source_id)
    R, manifest = load_raster(cache)
    F = geo.Frame.around(seed_ll)
    res = edges.extract_edges(R, F, geo.open_ring(F.to_xy(seed_ll)))
    # where the image frame really is (registration to lidar) + datum step
    pos = position.locate(R, source_id, seed_ll, cfg.get("lidar", []), raw_dir(slug) / "lidar")
    shift = np.asarray(pos["shift_m"])

    width = res.half_left + res.half_right
    seen = res.seen_left & res.seen_right
    resid = np.concatenate([res.resid_left[np.isfinite(res.resid_left)],
                            res.resid_right[np.isfinite(res.resid_right)]])
    # precision of a seen edge: robust spread of raw path vs fit, plus half a
    # ground pixel of quantisation
    precision = float(np.sqrt((1.4826 * np.median(np.abs(resid))) ** 2 + (manifest["gsd_m"] / 2) ** 2))

    loops = {}

    def ring(xy, side=None):
        if side:  # an inside edge tighter than its offset forms a swallowtail loop
            xy, loops[side] = geo.remove_loops(xy)
        return geo.lonlat_list(F.to_lonlat(geo.simplify_closed(xy, EDGE_SIMPLIFY_M) + shift))

    gsd = sorted({c["gsd_m"] for c in manifest.get("catalog", []) if c.get("gsd_m")}) \
        or [src.get("native_gsd_m", src["gsd_m"])]
    dates = sorted({c["acquisition_date"] for c in manifest.get("catalog", []) if c.get("acquisition_date")}) \
        or src.get("acquisition_dates", [])
    summary = pos["summary"]
    out = {
        "layout": layout_id,
        "method": "edges/2",
        "imagery": source_id,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "lap_length_m": round(res.total_m, 1),
        "edges": {"left": ring(res.left_xy, "left"), "right": ring(res.right_xy, "right")},
        "midline": ring(res.mid_xy),
        "quality": {
            "width_m": {"p05": round(float(np.percentile(width, 5)), 2),
                        "median": round(float(np.median(width)), 2),
                        "p95": round(float(np.percentile(width, 95)), 2)},
            "seen_fraction": {"left": round(float(res.seen_left.mean()), 3),
                              "right": round(float(res.seen_right.mean()), 3),
                              "both": round(float(seen.mean()), 3)},
            "unseen_spans": {"left": _spans(res.seen_left, res.total_m),
                             "right": _spans(res.seen_right, res.total_m)},
            "relative_precision_m": round(precision, 2),
            "loops_removed": loops,
            "absolute_accuracy_ce95_m": round(pos["ce95_m"], 2),
            "seed_offset_m": {"median_abs": round(float(np.median(np.abs(res.seed_shift_m))), 2),
                              "p95_abs": round(float(np.percentile(np.abs(res.seed_shift_m), 95)), 2)},
        },
        "position": summary,
        "sources": {
            "imagery": {
                "kind": "imagery", "id": source_id, "name": src["name"],
                "url": src["service"], "license": src["license"],
                "gsd_m": gsd, "sampled_gsd_m": manifest["gsd_m"], "acquisition_dates": dates,
                "rasters": [c["raster"] for c in manifest.get("catalog", [])],
                "request": {k: manifest[k] for k in ("crs", "x0", "y0", "px", "width", "height")},
                "frame": src["frame"],
                "horizontal_accuracy": src["accuracy_basis"],
                "stated_ce95_m": src.get("ce95_m"),
            },
            "reference": [
                {"kind": "lidar", "name": n, "url": f"{lidar.EPT_BUCKET}/{n}", "license": "public domain (US federal)",
                 "year": lidar.PROJECTS.get(n, {}).get("year"), "horizontal_accuracy": lidar.project_accuracy(n)[1]}
                for n in cfg.get("lidar", [])
            ],
            "seed": {
                "kind": "osm", "name": "layout centerline (OpenStreetMap)",
                "file": f"layers/{layout_id}.geojson", "license": "ODbL",
                "use": "seed only: fixes lap order, origin and direction; the edges are measured",
            },
        },
    }
    dest = raw_dir(slug) / f"surface-{layout_id}.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    q = out["quality"]
    print(f"[{slug}/{layout_id}] edges measured: width median {q['width_m']['median']} m "
          f"(p05 {q['width_m']['p05']}, p95 {q['width_m']['p95']}), seen L/R "
          f"{q['seen_fraction']['left']:.0%}/{q['seen_fraction']['right']:.0%}, "
          f"precision {q['relative_precision_m']} m, seed offset p95 {q['seed_offset_m']['p95_abs']} m")
    b = summary["budget_ce95_m"]
    print(f"[{slug}/{layout_id}] position: {source_id} -> {summary['reference']['kind']} {summary['reference']['name']}; "
          f"registration {summary['registration_shift_m']}, datum {summary['datum_shift_m']}; "
          f"CE95 {b['total']} m (reference {b['reference']}, registration {b['registration']}, datum {b['datum']})")
    for c in summary["checks"]:
        print(f"    check: {c}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--find-lidar", action="store_true", help="list 3DEP EPT projects covering the lap")
    args = ap.parse_args()
    if args.find_lidar:
        src = load_source(args.slug)
        for lo in src["layouts"]:
            for name, frac in lidar.find_projects(_outline(args.slug, lo["id"])):
                acc = lidar.project_accuracy(name)
                print(f"{args.slug}/{lo['id']}: {name} covers {frac:.0%} of the lap; {acc[1]}")
        return
    if args.all:
        slugs = sorted(p.name for p in TRACKS.iterdir() if (p / "source.json").exists())
    elif args.slug:
        slugs = [args.slug]
    else:
        ap.error("give a slug or --all")
    for slug in slugs:
        src = load_source(slug)
        cfg = src.get("surface") or {}
        if cfg.get("imagery") not in SOURCES:
            if args.slug:
                print(f"[{slug}] source.json declares no surface imagery; nothing to measure")
            continue
        for lo in src["layouts"]:
            if cfg.get("layouts") and lo["id"] not in cfg["layouts"]:
                continue
            measure(slug, lo["id"], cfg)


if __name__ == "__main__":
    main()

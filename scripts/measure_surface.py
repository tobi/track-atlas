#!/usr/bin/env python3
"""Measure a layout's track surface (left/right edges) from public-domain imagery.

Network step (like import.py): fetches USDA NAIP orthoimagery for the lap into
the gitignored cache `tracks/<slug>/raw/imagery/`, runs the edge extractor
(`lib/edges.py`, algorithm in docs/GEOMETRY.md) seeded by the layout
centerline, and writes the committed measurement

    tracks/<slug>/raw/surface-<layout>.json

(edges in the driving direction from the lap origin, quality, provenance).
generate.py / build_geometry.py consume it offline; nothing downstream needs
the imagery again.

Only tracks whose source.json declares `"surface": {"imagery": "naip"}` are
measured (NAIP covers the conterminous US only).

Usage:
    uv run python scripts/measure_surface.py road-atlanta
    uv run python scripts/measure_surface.py --all
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import edges, geo  # noqa: E402
from lib.config import TRACKS, load_source, raw_dir  # noqa: E402
from lib.imagery import NAIP_SERVICE, fetch_naip, load_raster  # noqa: E402

EDGE_SIMPLIFY_M = 0.05     # Douglas-Peucker tolerance for the stored edges
NAIP_CE95_M = 4.0          # NAIP contract: 95 % of well-defined points within 4 m (2016+)


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


def measure(slug: str, layout_id: str) -> dict:
    tdir = TRACKS / slug
    seed_ll = _outline(slug, layout_id)
    cache = raw_dir(slug) / "imagery"
    manifest = fetch_naip(cache, seed_ll)
    R, manifest = load_raster(cache)
    F = geo.Frame.around(seed_ll)
    res = edges.extract_edges(R, F, geo.open_ring(F.to_xy(seed_ll)))

    width = res.half_left + res.half_right
    seen = res.seen_left & res.seen_right
    resid = np.concatenate([res.resid_left[np.isfinite(res.resid_left)],
                            res.resid_right[np.isfinite(res.resid_right)]])
    # precision of a seen edge: robust spread of raw path vs fit, plus half a
    # ground pixel of quantisation
    precision = float(np.sqrt((1.4826 * np.median(np.abs(resid))) ** 2 + (manifest["gsd_m"] / 2) ** 2))

    def ring(xy):
        return geo.lonlat_list(F.to_lonlat(geo.simplify_closed(xy, EDGE_SIMPLIFY_M)))

    gsd = sorted({c["gsd_m"] for c in manifest.get("catalog", []) if c.get("gsd_m")})
    dates = sorted({c["acquisition_date"] for c in manifest.get("catalog", []) if c.get("acquisition_date")})
    out = {
        "layout": layout_id,
        "method": "naip-edges/1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "lap_length_m": round(res.total_m, 1),
        "edges": {"left": ring(res.left_xy), "right": ring(res.right_xy)},
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
            "absolute_accuracy_ce95_m": NAIP_CE95_M,
            "seed_offset_m": {"median_abs": round(float(np.median(np.abs(res.seed_shift_m))), 2),
                              "p95_abs": round(float(np.percentile(np.abs(res.seed_shift_m), 95)), 2)},
        },
        "sources": {
            "naip": {
                "kind": "imagery", "name": "USDA NAIP via USGS The National Map",
                "url": NAIP_SERVICE, "license": "public domain (US federal)",
                "gsd_m": gsd, "acquisition_dates": dates,
                "rasters": [c["raster"] for c in manifest.get("catalog", [])],
                "request": {k: manifest[k] for k in ("crs", "x0", "y0", "px", "width", "height")},
                "horizontal_accuracy": f"NAIP contract: 95% of well-defined points within {NAIP_CE95_M:g} m of true ground",
            },
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
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    if args.all:
        slugs = sorted(p.name for p in TRACKS.iterdir() if (p / "source.json").exists())
    elif args.slug:
        slugs = [args.slug]
    else:
        ap.error("give a slug or --all")
    for slug in slugs:
        src = load_source(slug)
        cfg = src.get("surface") or {}
        if cfg.get("imagery") != "naip":
            if args.slug:
                print(f"[{slug}] source.json declares no surface imagery; nothing to measure")
            continue
        for lo in src["layouts"]:
            if cfg.get("layouts") and lo["id"] not in cfg["layouts"]:
                continue
            measure(slug, lo["id"])


if __name__ == "__main__":
    main()

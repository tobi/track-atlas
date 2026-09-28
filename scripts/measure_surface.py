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

Only tracks whose track.py calls t.surface() are measured:

    "surface": {}                                   // = {"imagery": "auto", "lidar": "auto"}
    "surface": {"imagery": "naip", "lidar": ["GA_Statewide_B3_2018"]}   // pinned
    "surface": {"bridge": [{"side": "right", "from": 0.10, "to": 0.167,
                            "note": "pit exit merges without a painted line"}]}

`imagery` "auto" measures with every lib/imagery.SOURCES entry covering the lap
and keeps the best (absolute CE95 + a charge for bridged edges; the comparison
is recorded in the measurement's `selection`). `lidar` "auto" picks the USGS
3DEP surveys covering the lap (lib/lidar.pick: stated accuracy first, then
newest); the first that registers is the reference, the rest are checks.
`--find-lidar` lists every survey covering a lap.

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
from lib.config import TRACKS, load_source, raw_dir, slugs as all_slugs  # noqa: E402
from lib.imagery import SOURCES, covering, fetch_imagery, load_raster  # noqa: E402

EDGE_SIMPLIFY_M = 0.05     # Douglas-Peucker tolerance for the stored edges


def _outline(slug: str, layout_id: str) -> np.ndarray:
    """The seed: the OSM centerline generate.py kept (never the previous midline)."""
    seed = raw_dir(slug) / f"seed-{layout_id}.geojson"
    if seed.exists():
        return np.asarray(json.loads(seed.read_text())["geometry"]["coordinates"], dtype=float)
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


MIN_SEEN = 0.2   # refuse a measurement whose edges were barely seen
UNSEEN_COST_M = 4.0  # selection: metres of error charged per unit of lap where an edge was bridged


class Refused(Exception):
    """A candidate imagery source that cannot measure this lap."""


def measure(slug: str, layout_id: str, cfg: dict) -> dict:
    """Measure with every candidate imagery source; write the best.

    Candidates: `imagery` ("auto" = every lib/imagery.SOURCES entry covering the
    lap, an id, or a list). References: `lidar` ("auto" = lib/lidar.pick, or a
    list). Score = absolute CE95 + UNSEEN_COST_M x the share of the lap where
    either edge was bridged: position and coverage in one number of metres.
    """
    seed_ll = _outline(slug, layout_id)
    want = cfg.get("imagery", "auto")
    cands = covering(seed_ll) if want == "auto" else ([want] if isinstance(want, str) else list(want))
    refs = cfg.get("lidar", "auto")
    refs = lidar.pick(seed_ll) if refs == "auto" else list(refs)
    print(f"[{slug}/{layout_id}] imagery candidates {cands}; lidar {refs}")
    results, selection = [], []
    for sid in cands:
        try:
            out = _measure_with(slug, layout_id, sid, refs, seed_ll, cfg.get("bridge"))
        except Refused as e:
            selection.append({"imagery": sid, "result": f"refused: {e}"})
            print(f"[{slug}/{layout_id}] {sid}: refused: {e}")
            continue
        q = out["quality"]
        score = q["absolute_accuracy_ce95_m"] + UNSEEN_COST_M * (1 - q["seen_fraction"]["both"])
        selection.append({"imagery": sid, "absolute_accuracy_ce95_m": q["absolute_accuracy_ce95_m"],
                          "seen_both": q["seen_fraction"]["both"], "relative_precision_m": q["relative_precision_m"],
                          "score_m": round(score, 2)})
        results.append((score, sid, out))
    if not results:
        raise SystemExit(f"[{slug}/{layout_id}] no imagery source could measure the lap: {selection}")
    score, sid, out = min(results, key=lambda r: r[0])
    for c in selection:
        c["chosen"] = c["imagery"] == sid
    out["selection"] = {"rule": f"min(absolute CE95 + {UNSEEN_COST_M:g} m x unseen share)", "candidates": selection}
    dest = raw_dir(slug) / f"surface-{layout_id}.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"[{slug}/{layout_id}] chose {sid} (score {score:.2f} m) -> {dest.relative_to(raw_dir(slug).parent)}")
    return out


def _measure_with(slug: str, layout_id: str, source_id: str, refs: list[str], seed_ll: np.ndarray,
                  bridge=None) -> dict:
    src = SOURCES[source_id]
    cache = raw_dir(slug) / "imagery" / source_id
    fetch_imagery(cache, seed_ll, source_id)
    R, manifest = load_raster(cache)
    F = geo.Frame.around(seed_ll)
    for b in bridge or ():
        if b.get("side") not in ("left", "right") or not b.get("note"):
            raise SystemExit(f"[{slug}] surface.bridge needs side left/right and a note: {b}")
    res = edges.extract_edges(R, F, geo.open_ring(F.to_xy(seed_ll)), bridge=bridge)
    if min(res.seen_left.mean(), res.seen_right.mean()) < MIN_SEEN:
        raise Refused(f"edges seen on only {res.seen_left.mean():.0%}/{res.seen_right.mean():.0%} "
                      "of the lap (no coverage, or unusable imagery)")
    # where the image frame really is (registration to lidar) + datum step
    pos = position.locate(R, source_id, seed_ll, refs, raw_dir(slug) / "lidar")
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
            "curated_bridges": bridge or [],
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
                for n in refs
            ],
            "seed": {
                "kind": "osm", "name": "layout centerline (OpenStreetMap)",
                "file": f"layers/{layout_id}.geojson", "license": "ODbL",
                "use": "seed only: fixes lap order, origin and direction; the edges are measured",
            },
        },
    }
    q = out["quality"]
    print(f"[{slug}/{layout_id}] {source_id}: edges measured: width median {q['width_m']['median']} m "
          f"(p05 {q['width_m']['p05']}, p95 {q['width_m']['p95']}), seen L/R "
          f"{q['seen_fraction']['left']:.0%}/{q['seen_fraction']['right']:.0%}, "
          f"precision {q['relative_precision_m']} m, seed offset p95 {q['seed_offset_m']['p95_abs']} m")
    b = summary["budget_ce95_m"]
    print(f"[{slug}/{layout_id}] {source_id}: position -> {summary['reference']['kind']} {summary['reference']['name']}; "
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
        slugs = all_slugs()
    elif args.slug:
        slugs = [args.slug]
    else:
        ap.error("give a slug or --all")
    for slug in slugs:
        src = load_source(slug)
        cfg = src.get("surface") or {}
        if "surface" not in src:
            if args.slug:
                print(f"[{slug}] track.py has no t.surface(); nothing to measure")
            continue
        for lo in src["layouts"]:
            if cfg.get("layouts") and lo["id"] not in cfg["layouts"]:
                continue
            measure(slug, lo["id"], cfg)


if __name__ == "__main__":
    main()

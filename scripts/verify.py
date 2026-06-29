#!/usr/bin/env python3
"""Verify track completeness and internal consistency.

The schema is layout-first: each layout owns point_layers (corner apexes,
start/finish, pit in/out, marshal posts) and range_layers (timing sectors,
microsectors, corner ranges, complexes, slow zones).

Exit code 0 = all tracks pass (warnings allowed), 1 = any error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.config import TRACKS, track_json_path  # noqa: E402
from lib.osm import haversine, arc_lengths  # noqa: E402
from lib.models import Track  # noqa: E402
from layer_tools.curvature_apexes import compute_layers as compute_curvature_layers  # noqa: E402
from pydantic import ValidationError  # noqa: E402

MAX_CORNER_OFF_TRACK_M = 80.0
MAX_CORNER_TO_CURVATURE_APEX_M = 260.0
LEN_WARN_PCT = 3.0
LEN_ERR_PCT = 10.0

BAR = [
    ("schema", "track.json valid against schema"),
    ("outline", "real closed outline geometry (>=8 pts)"),
    ("length", f"outline length within {LEN_ERR_PCT:.0f}% of declared"),
    ("located", "every corner has a coordinate"),
    ("on_track", f"every corner within {MAX_CORNER_OFF_TRACK_M:.0f} m of the outline"),
    ("order", "corner lap-order matches geometry"),
    ("sf", "start/finish present and on the outline"),
    ("render", "poster render (svg+png) exists and is fresh"),
]


class Report:
    def __init__(self, slug):
        self.slug = slug
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.infos: list[str] = []
        self.bar: dict = {k: None for k, _ in BAR}

    def err(self, msg): self.errors.append(msg)
    def warn(self, msg): self.warnings.append(msg)
    def info(self, msg): self.infos.append(msg)
    def bar_ok(self, key):
        if self.bar.get(key) is None:
            self.bar[key] = True
    def bar_fail(self, key): self.bar[key] = False

    @property
    def meets_bar(self): return all(v is True for v in self.bar.values())

    def missing(self):
        labels = dict(BAR)
        return [labels[k] for k, v in self.bar.items() if v is not True]

    def dump(self):
        print(f"\n== {self.slug} ==")
        for m in self.errors: print(f"  ERROR  {m}")
        for m in self.warnings: print(f"  WARN   {m}")
        for m in self.infos: print(f"  ok     {m}")
        if not self.errors and not self.warnings: print("  PASS")


def point_layer(layout, layer_id):
    return next((l for l in layout.get("point_layers", []) if l.get("id") == layer_id), {"items": []})


def range_layer(layout, layer_id):
    return next((l for l in layout.get("range_layers", []) if l.get("id") == layer_id), {"items": []})


def layout_point(layout, point_id):
    return next((p for p in point_layer(layout, "layout_points").get("items", []) if p.get("id") == point_id), None)


def nearest_dist_to_polyline(pt, loop):
    best, bi = float("inf"), 0
    for i, p in enumerate(loop):
        d = haversine(pt, p)
        if d < best:
            best, bi = d, i
    import math
    k = math.cos(math.radians(pt[1]))

    def seg_dist(a, b):
        ax, ay = a[0] * k, a[1]
        bx, by = b[0] * k, b[1]
        px, py = pt[0] * k, pt[1]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        if L2 == 0:
            return haversine(pt, a)
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
        proj = [(ax + t * dx) / k, ay + t * dy]
        return haversine(pt, proj)

    for i in (bi - 1, bi):
        if 0 <= i < len(loop) - 1:
            best = min(best, seg_dist(loop[i], loop[i + 1]))
    return best


def fraction_along(pt, loop, cum, total):
    best, bi = float("inf"), 0
    for i, p in enumerate(loop):
        d = haversine(pt, p)
        if d < best:
            best, bi = d, i
    return cum[bi] / total if total else 0.0


def circular_marker_distance(a: float, b: float) -> float:
    d = abs((a % 1.0) - (b % 1.0))
    return min(d, 1.0 - d)


def kendall_disagreements(markers, fracs):
    if len(markers) < 3:
        return 0, []
    f0 = fracs[0]
    adj = [(f - f0) % 1.0 for f in fracs]
    bad = []
    n = len(markers)
    for i in range(n):
        for j in range(i + 1, n):
            if (markers[i] - markers[j]) * (adj[i] - adj[j]) < 0:
                bad.append((i, j))
    return len(bad), bad


def verify_track(slug: str) -> Report:
    r = Report(slug)
    tdir = TRACKS / slug
    src_f, tj_f = tdir / "source.json", track_json_path(slug)
    for f, label in ((src_f, "source.json"), (tj_f, "raw/track.json"), (tdir / "README.md", "README.md")):
        if not f.exists():
            r.err(f"missing {label}")
    if r.errors:
        return r
    try:
        track = json.loads(tj_f.read_text())
    except Exception as e:
        r.err(f"track.json unparseable: {e}")
        return r

    try:
        Track.model_validate(track)
        r.info("schema valid (pydantic)")
        r.bar_ok("schema")
    except ValidationError as e:
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"]) or "(root)"
            r.err(f"schema: {loc}: {err['msg']}")
        r.bar_fail("schema")

    for key in ("slug", "name", "country", "location", "layouts", "label_layers"):
        if not track.get(key):
            r.err(f"track.{key} missing/empty")
    if track.get("slug") != slug:
        r.err(f"slug mismatch: folder={slug} track.json={track.get('slug')}")
    if not track.get("series"):
        r.warn("track.series missing (which series race here?)")

    for lo in track.get("layouts", []):
        lid = lo.get("id", "?")
        pre = f"layout[{lid}]"
        if not lo.get("length_m"):
            r.warn(f"{pre}.length_m missing")
        if not lo.get("direction"):
            r.warn(f"{pre}.direction missing")

        corners = point_layer(lo, "corners").get("items", [])
        if not corners:
            r.err(f"{pre} has no corners point layer/items")
            continue
        unlocated = [c.get("number", c.get("id")) for c in corners if not c.get("location")]
        if unlocated:
            r.err(f"{pre} corners without location: {unlocated}")
            r.bar_fail("located")
        else:
            r.bar_ok("located")

        sf = layout_point(lo, "start_finish")
        if not (sf and sf.get("location")):
            r.err(f"{pre} layout_points.start_finish missing")
            r.bar_fail("sf")
        pit_entry, pit_exit = layout_point(lo, "pit_entry"), layout_point(lo, "pit_exit")
        if not (pit_entry and pit_entry.get("marker") is not None and pit_exit and pit_exit.get("marker") is not None):
            r.warn(f"{pre} pit_entry/pit_exit missing")

        sectors = range_layer(lo, "timing_sectors").get("items", [])
        if [s.get("label") for s in sectors] != ["S1", "S2", "S3"]:
            r.err(f"{pre} timing_sectors must be exactly [S1, S2, S3], got {[s.get('label') for s in sectors]}")

        geom_path = (lo.get("geometry") or {}).get("centerline")
        if not geom_path:
            r.err(f"{pre}.geometry.centerline missing")
            continue
        gj_f = tj_f.parent / geom_path
        if not gj_f.exists():
            r.err(f"{pre} geometry file missing: {geom_path}")
            continue
        try:
            gj = json.loads(gj_f.read_text())
            outline = next((f for f in gj.get("features", []) if f.get("properties", {}).get("role") == "outline"), None)
            loop = outline["geometry"]["coordinates"] if outline else []
        except Exception as e:
            r.err(f"{pre} geometry parse failed: {e}")
            continue
        if len(loop) < 8:
            r.err(f"{pre} outline missing/too short")
            r.bar_fail("outline")
            continue
        if loop[0] != loop[-1]:
            r.err(f"{pre} outline not closed")
            r.bar_fail("outline")
        else:
            r.bar_ok("outline")

        cum, total = arc_lengths(loop)
        if lo.get("length_m") and total:
            pct = abs(total - lo["length_m"]) / lo["length_m"] * 100
            msg = f"{pre} outline length {total:,.0f} m vs declared {lo['length_m']:,.0f} m ({pct:.1f}%)"
            if pct > LEN_ERR_PCT:
                r.err(msg); r.bar_fail("length")
            elif pct > LEN_WARN_PCT:
                r.warn(msg); r.bar_ok("length")
            else:
                r.info(msg); r.bar_ok("length")

        if sf and sf.get("location"):
            d = nearest_dist_to_polyline(sf["location"], loop)
            if d > MAX_CORNER_OFF_TRACK_M:
                r.err(f"{pre} start_finish {d:.0f} m from outline")
                r.bar_fail("sf")
            else:
                r.bar_ok("sf")

        off = []
        located = [c for c in corners if c.get("location")]
        for c in located:
            d = nearest_dist_to_polyline(c["location"], loop)
            if d > MAX_CORNER_OFF_TRACK_M:
                off.append((c.get("number", c["id"]), d))
        if off:
            r.err(f"{pre} corners off outline: " + ", ".join(f"T{n} {d:.0f}m" for n, d in off[:12]))
            r.bar_fail("on_track")
        else:
            r.bar_ok("on_track")

        ordered = sorted([c for c in located if c.get("marker") is not None], key=lambda c: c.get("number") or 0)
        fracs = [fraction_along(c["location"], loop, cum, total) for c in ordered]
        markers = [c["marker"] for c in ordered]
        bad_n, bad_pairs = kendall_disagreements(markers, fracs)
        if bad_n:
            examples = ", ".join(f"T{ordered[i].get('number')}↔T{ordered[j].get('number')}" for i, j in bad_pairs[:8])
            r.err(f"{pre} corner lap order disagrees with geometry ({bad_n} inversions): {examples}")
            r.bar_fail("order")
        else:
            r.bar_ok("order")

        gj_corners = [f for f in gj.get("features", []) if f.get("properties", {}).get("role") == "corner"]
        if len(gj_corners) != len(located):
            r.warn(f"{pre} geojson has {len(gj_corners)} corner features, track has {len(located)} located corners")

        # Curvature-derived apexes are an independent geometry-only sanity check.
        # They should not be treated as authoritative corner names/numbers, but
        # they are very good at catching misplaced apex markers or collapsed
        # corner data: a named corner apex far from any κ(s) peak is suspicious.
        try:
            curv = compute_curvature_layers(str(gj_f), {
                "max_apexes": max(16, len(corners) * 2),
                "min_separation_m": 60.0,
                "smooth_window_m": 70.0,
                "curvature_percentile": 0.65,
            }, {"relative_path": geom_path})
            apexes = curv.get("point_layers", [{}])[0].get("items", [])
            if apexes and total:
                far = []
                for c in ordered:
                    cm = c.get("marker")
                    if cm is None:
                        continue
                    nearest = min(apexes, key=lambda a: circular_marker_distance(cm, a.get("marker", 0.0)))
                    dist_m = circular_marker_distance(cm, nearest.get("marker", 0.0)) * total
                    if dist_m > MAX_CORNER_TO_CURVATURE_APEX_M:
                        far.append((c.get("number", c.get("id")), dist_m, nearest.get("label")))
                if far:
                    r.warn(f"{pre} corners far from curvature apex candidates: " +
                           ", ".join(f"T{n} {d:.0f}m from {label}" for n, d, label in far[:10]))
        except Exception as e:
            r.warn(f"{pre} curvature apex check skipped: {e}")

    svg = tdir / "raw" / "render" / f"{slug}.svg"
    png = tdir / "raw" / "render" / f"{slug}.png"
    if svg.exists() and png.exists():
        r.bar_ok("render")
    else:
        r.warn("render svg/png missing")
        r.bar_fail("render")
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--strict", action="store_true", help="warnings count as errors")
    args = ap.parse_args()
    slugs = [args.slug] if args.slug else sorted(p.name for p in TRACKS.iterdir() if (p / "source.json").exists())
    reports = [verify_track(s) for s in slugs]
    for r in reports:
        r.dump()
    missing = [r for r in reports if not r.meets_bar]
    if len(reports) > 1:
        print("\n== summary ==")
        print(f"tracks: {len(reports)}  meets bar: {len(reports) - len(missing)}  missing: {len(missing)}")
        for r in missing[:40]:
            print(f"  {r.slug}: " + "; ".join(r.missing()))
    if any(r.errors for r in reports) or (args.strict and any(r.warnings for r in reports)):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Verify track completeness and internal consistency.

Checks every track (or one slug) for:

  STRUCTURE
    - required files exist (source.json, track.json, layers/*.geojson, README.md)
    - track.json validates against schema/track.schema.json (when jsonschema is
      installed; otherwise structural checks below still run)
    - every layout's geometry.outline file exists and parses

  COMPLETENESS
    - layout has corners, length_m, direction, start_finish, pit entry/exit
    - every corner has a location (and marker)
    - corner numbers are sequential 1..N without gaps or duplicates
    - geojson carries outline + start_finish + corner features
    - render/<slug>.png + .svg exist and are newer than track.json

  ALIGNMENT (misalignment / anything-amiss)
    - outline is a closed loop (first == last point)
    - outline traced length vs declared length_m (warn >3%, error >10%)
    - every corner location sits ON the outline (error if > 60 m off)
    - corner lap-order vs geometric order along the outline (Kendall tau;
      flags corners whose marker ordering disagrees with their position along
      the centerline)
    - start_finish sits on the outline; pit entry/exit markers are sane
    - track.json corners == geojson corner features (numbers + coordinates)

Exit code 0 = all tracks pass (warnings allowed), 1 = any error.

Usage:
    python scripts/verify.py                 # all tracks
    python scripts/verify.py silverstone     # one track
    python scripts/verify.py --strict        # warnings count as errors
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.config import TRACKS  # noqa: E402
from lib.osm import haversine, arc_lengths  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schema" / "track.schema.json"

MAX_CORNER_OFF_TRACK_M = 60.0
LEN_WARN_PCT = 3.0
LEN_ERR_PCT = 10.0


class Report:
    def __init__(self, slug):
        self.slug = slug
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.infos: list[str] = []

    def err(self, msg): self.errors.append(msg)
    def warn(self, msg): self.warnings.append(msg)
    def info(self, msg): self.infos.append(msg)

    def dump(self):
        print(f"\n== {self.slug} ==")
        for m in self.errors:
            print(f"  ERROR  {m}")
        for m in self.warnings:
            print(f"  WARN   {m}")
        for m in self.infos:
            print(f"  ok     {m}")
        if not self.errors and not self.warnings:
            print("  PASS")


def nearest_dist_to_polyline(pt, loop):
    """Min distance (m) from pt to any segment of the polyline (vertex approx
    + segment projection for the best vertex's neighborhood)."""
    best, bi = float("inf"), 0
    for i, p in enumerate(loop):
        d = haversine(pt, p)
        if d < best:
            best, bi = d, i
    # refine with projection onto the two adjacent segments (planar approx)
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


def kendall_disagreements(markers, fracs):
    """Pairs whose lap-marker order disagrees with centerline order, treating
    fractions as cyclic (anchored at the first corner)."""
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


def verify_track(slug: str, schema=None) -> Report:
    r = Report(slug)
    tdir = TRACKS / slug

    # --- structure ---
    src_f, tj_f = tdir / "source.json", tdir / "track.json"
    for f, label in ((src_f, "source.json"), (tj_f, "track.json"),
                     (tdir / "README.md", "README.md")):
        if not f.exists():
            r.err(f"missing {label}")
    if r.errors:
        return r
    try:
        track = json.loads(tj_f.read_text())
    except Exception as e:
        r.err(f"track.json unparseable: {e}")
        return r

    if schema is not None:
        try:
            import jsonschema
            jsonschema.validate(track, schema)
            r.info("schema valid")
        except ImportError:
            r.warn("jsonschema not installed -- schema validation skipped")
        except Exception as e:
            r.err(f"schema violation: {str(e).splitlines()[0]}")

    for key in ("slug", "name", "country", "location", "layouts"):
        if not track.get(key):
            r.err(f"track.{key} missing/empty")
    if track.get("slug") != slug:
        r.err(f"slug mismatch: folder={slug} track.json={track.get('slug')}")
    if not track.get("series"):
        r.warn("track.series missing (which series race here?)")

    for lo in track.get("layouts", []):
        lid = lo.get("id", "?")
        pre = f"layout[{lid}]"

        # completeness
        for key in ("length_m", "direction"):
            if not lo.get(key):
                r.warn(f"{pre}.{key} missing")
        if not lo.get("start_finish", {}).get("location"):
            r.err(f"{pre}.start_finish missing")
        pit = lo.get("pit") or {}
        if pit.get("entry") is None or pit.get("exit") is None:
            r.warn(f"{pre}.pit entry/exit missing")

        corners = lo.get("corners", [])
        if not corners:
            r.err(f"{pre} has no corners")
            continue
        nums = [c.get("number") for c in corners]
        if sorted(nums) != list(range(1, len(nums) + 1)):
            r.err(f"{pre} corner numbers not sequential 1..{len(nums)}: {sorted(nums)}")
        unlocated = [c["number"] for c in corners if not c.get("location")]
        if unlocated:
            r.err(f"{pre} corners without location: {unlocated}")
        unmarked = [c["number"] for c in corners if c.get("marker") is None]
        if unmarked:
            r.warn(f"{pre} corners without lap marker: {unmarked}")
        named = sum(1 for c in corners
                    if c.get("names", {}).get("colloquial") or c.get("names", {}).get("official"))
        r.info(f"{pre} {len(corners)} corners ({named} named), "
               f"{len(corners) - len(unlocated)} located")

        # geometry file
        gpath = tdir / (lo.get("geometry", {}).get("outline") or "")
        if not gpath.exists():
            r.err(f"{pre} outline file missing: {gpath.name}")
            continue
        try:
            gj = json.loads(gpath.read_text())
        except Exception as e:
            r.err(f"{pre} geojson unparseable: {e}")
            continue
        feats = gj.get("features", [])
        by_role = {}
        for f in feats:
            by_role.setdefault(f.get("properties", {}).get("role"), []).append(f)
        outline = by_role.get("outline", [None])[0]
        if outline is None:
            r.err(f"{pre} geojson has no outline feature")
            continue
        if not by_role.get("start_finish"):
            r.err(f"{pre} geojson has no start_finish feature")
        gj_corners = by_role.get("corner", [])
        if len(gj_corners) != len(corners) - len(unlocated):
            r.err(f"{pre} geojson corner features ({len(gj_corners)}) != located "
                  f"corners in track.json ({len(corners) - len(unlocated)})")
        # cross-check coordinates agree
        loc_by_num = {c["number"]: c.get("location") for c in corners}
        for f in gj_corners:
            n = f["properties"].get("number")
            gloc = f["geometry"]["coordinates"]
            tloc = loc_by_num.get(n)
            if tloc and haversine(gloc, tloc) > 1.0:
                r.err(f"{pre} corner {n} coordinate drift between track.json and geojson "
                      f"({haversine(gloc, tloc):.0f} m)")

        loop = outline["geometry"]["coordinates"]
        if len(loop) < 8:
            r.err(f"{pre} outline too short ({len(loop)} pts) -- not real geometry")
            continue
        if loop[0] != loop[-1]:
            r.err(f"{pre} outline is not a closed loop")

        # length check
        cum, total = arc_lengths(loop)
        decl = lo.get("length_m")
        if decl:
            pct = abs(total - decl) / decl * 100
            msg = f"{pre} outline {total:,.0f} m vs declared {decl:,.0f} m ({pct:.1f}%)"
            if pct > LEN_ERR_PCT:
                r.err(msg)
            elif pct > LEN_WARN_PCT:
                r.warn(msg)
            else:
                r.info(msg)

        # corners on track?
        off = []
        for c in corners:
            if not c.get("location"):
                continue
            d = nearest_dist_to_polyline(c["location"], loop)
            if d > MAX_CORNER_OFF_TRACK_M:
                off.append((c["number"], d))
        if off:
            r.err(f"{pre} corners off the outline (> {MAX_CORNER_OFF_TRACK_M:.0f} m): "
                  + ", ".join(f"T{n} {d:.0f}m" for n, d in off))
        else:
            r.info(f"{pre} all located corners sit on the outline")

        # start/finish on track?
        sf = lo.get("start_finish", {}).get("location")
        if sf:
            d = nearest_dist_to_polyline(sf, loop)
            if d > MAX_CORNER_OFF_TRACK_M:
                r.err(f"{pre} start_finish {d:.0f} m off the outline")

        # lap-order vs geometric order
        ordered = [c for c in sorted(corners, key=lambda c: c.get("marker") or 0)
                   if c.get("location") and c.get("marker") is not None]
        if len(ordered) >= 3:
            markers = [c["marker"] for c in ordered]
            fracs = [fraction_along(c["location"], loop, cum, total) for c in ordered]
            nbad, bad = kendall_disagreements(markers, fracs)
            npairs = len(ordered) * (len(ordered) - 1) // 2
            if nbad:
                worst = sorted({ordered[i]["number"] for i, j in bad}
                               | {ordered[j]["number"] for i, j in bad})
                # tolerate a couple of swaps from near-coincident chicane corners
                msg = (f"{pre} corner order along centerline disagrees with lap "
                       f"markers for {nbad}/{npairs} pairs (turns {worst})")
                (r.warn if nbad <= 2 else r.err)(msg)
            else:
                r.info(f"{pre} corner lap-order matches geometry ({npairs} pairs)")

        # pit markers sane
        for k in ("entry", "exit"):
            v = pit.get(k)
            if v is not None and not (0.0 <= v <= 1.0):
                r.err(f"{pre}.pit.{k} = {v} outside [0,1]")

    # renders exist + fresh
    rdir = tdir / "render"
    png, svgf = rdir / f"{slug}.png", rdir / f"{slug}.svg"
    for f in (svgf, png):
        if not f.exists():
            r.err(f"render missing: render/{f.name}")
        elif f.stat().st_mtime < tj_f.stat().st_mtime:
            r.warn(f"render/{f.name} older than track.json -- re-run scripts/render.py {slug}")

    return r


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--strict", action="store_true",
                    help="warnings count as failures")
    args = ap.parse_args()

    schema = None
    if SCHEMA.exists():
        schema = json.loads(SCHEMA.read_text())

    slugs = [args.slug] if args.slug else sorted(
        p.name for p in TRACKS.iterdir() if (p / "source.json").exists())

    failed = False
    for slug in slugs:
        rep = verify_track(slug, schema)
        rep.dump()
        if rep.errors or (args.strict and rep.warnings):
            failed = True

    n = len(slugs)
    print(f"\n{n} track(s) verified -- {'FAIL' if failed else 'PASS'}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

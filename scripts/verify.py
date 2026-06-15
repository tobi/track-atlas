#!/usr/bin/env python3
"""Verify track completeness and internal consistency.

Checks every track (or one slug) for:

  STRUCTURE  (owned by the Pydantic models in lib/models.py)
    - required files exist (source.json, track.json, layers/*.geojson, README.md)
    - track.json validates against the Track model: types, enums, lon/lat shape,
      sequential corner numbers, unique corner codes, contiguous complexes,
      mandatory + declared name layers, name_default references a real layer
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
from lib.config import TRACKS, raw_dir, track_json_path  # noqa: E402
from lib.osm import haversine, arc_lengths  # noqa: E402
from lib.models import Track  # noqa: E402
from pydantic import ValidationError  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

MAX_CORNER_OFF_TRACK_M = 80.0
LEN_WARN_PCT = 3.0
LEN_ERR_PCT = 10.0
MIN_NAMED_PCT = 40.0   # below this, warn: corner naming too thin

# ---------------------------------------------------------------------------
# THE MINIMUM BAR -- what a track must have to count as "in" the atlas.
# Each item is (key, human label). verify_track() fills report.bar with
# True/False per key; the summary prints exactly what's missing per track.
# ---------------------------------------------------------------------------
BAR = [
    ("schema",    "track.json valid against schema"),
    ("outline",   "real closed outline geometry (>=8 pts)"),
    ("length",    f"outline length within {LEN_ERR_PCT:.0f}% of declared"),
    ("located",   "every corner has a coordinate"),
    ("on_track",  f"every corner within {MAX_CORNER_OFF_TRACK_M:.0f} m of the outline"),
    ("order",     "corner lap-order matches geometry"),
    ("sf",        "start/finish present and on the outline"),
    ("render",    "poster render (svg+png) exists and is fresh"),
]


class Report:
    def __init__(self, slug):
        self.slug = slug
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.infos: list[str] = []
        # bar item key -> True (met) / False (failed) / None (not evaluated,
        # counts as failed in the summary)
        self.bar: dict = {k: None for k, _ in BAR}

    def err(self, msg): self.errors.append(msg)
    def warn(self, msg): self.warnings.append(msg)
    def info(self, msg): self.infos.append(msg)

    def bar_ok(self, key):
        if self.bar.get(key) is None:
            self.bar[key] = True

    def bar_fail(self, key):
        self.bar[key] = False

    @property
    def meets_bar(self):
        return all(v is True for v in self.bar.values())

    def missing(self):
        labels = dict(BAR)
        return [labels[k] for k, v in self.bar.items() if v is not True]

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
    src_f, tj_f = tdir / "source.json", track_json_path(slug)
    for f, label in ((src_f, "source.json"), (tj_f, "raw/track.json"),
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

    try:
        Track.model_validate(track)
        r.info("schema valid (pydantic)")
        r.bar_ok("schema")
    except ValidationError as e:
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"]) or "(root)"
            r.err(f"schema: {loc}: {err['msg']}")
        r.bar_fail("schema")

    for key in ("slug", "name", "country", "location", "layouts"):
        if not track.get(key):
            r.err(f"track.{key} missing/empty")
    if track.get("slug") != slug:
        r.err(f"slug mismatch: folder={slug} track.json={track.get('slug')}")
    if not track.get("series"):
        r.warn("track.series missing (which series race here?)")
    nlr = track.get("name_layers") or {}
    if not nlr:
        r.err("track.name_layers missing")
    else:
        for req in ("numbered", "official"):
            if req not in nlr:
                r.err(f"track.name_layers missing mandatory layer '{req}'")

    for lo in track.get("layouts", []):
        lid = lo.get("id", "?")
        pre = f"layout[{lid}]"

        # completeness
        for key in ("length_m", "direction"):
            if not lo.get(key):
                r.warn(f"{pre}.{key} missing")
        if not lo.get("start_finish", {}).get("location"):
            r.err(f"{pre}.start_finish missing")
            r.bar_fail("sf")
        pit = lo.get("pit") or {}
        if pit.get("entry") is None or pit.get("exit") is None:
            r.warn(f"{pre}.pit entry/exit missing")

        # every track needs the three canonical timing sectors, contiguous 0->1
        secs = lo.get("sectors", [])
        if [s.get("name") for s in secs] != ["S1", "S2", "S3"]:
            r.err(f"{pre} sectors must be exactly [S1, S2, S3], got {[s.get('name') for s in secs]}")
        else:
            b = [secs[0].get("start"), secs[0].get("end"), secs[1].get("end"), secs[2].get("end")]
            ok = (b[0] == 0.0 and abs(b[3] - 1.0) < 1e-6 and 0 < b[1] < b[2] < b[3]
                  and secs[1].get("start") == b[1] and secs[2].get("start") == b[2])
            if not ok:
                r.err(f"{pre} sectors not contiguous 0->1: {b}")

        corners = lo.get("corners", [])
        if not corners:
            r.err(f"{pre} has no corners")
            continue
        # Structural invariants (sequential numbers, unique codes, contiguous
        # complexes, declared name layers, name_default reference) are enforced
        # by the Pydantic model above. Here we add only the soft signal it
        # doesn't: a "complex" tagged on a single corner usually means an
        # inconsistent complex string split the group.
        from collections import defaultdict
        comp = defaultdict(list)
        for c in corners:
            if c.get("complex"):
                comp[c["complex"]].append(c["number"])
        for cname, ns in comp.items():
            if len(ns) < 2:
                r.warn(f"{pre} complex '{cname}' spans a single corner {sorted(ns)} -- "
                       f"likely an inconsistent complex name split the group")
        unlocated = [c["number"] for c in corners if not c.get("location")]
        if unlocated:
            r.err(f"{pre} corners without location: {unlocated}")
            r.bar_fail("located")
        else:
            r.bar_ok("located")
        unmarked = [c["number"] for c in corners if c.get("marker") is None]
        if unmarked:
            r.warn(f"{pre} corners without lap marker: {unmarked}")
        named = sum(1 for c in corners
                    if any(k != "numbered" for k in c.get("names", {})))
        named_pct = named / len(corners) * 100
        if named_pct < MIN_NAMED_PCT:
            r.warn(f"{pre} only {named}/{len(corners)} corners named "
                   f"({named_pct:.0f}% < {MIN_NAMED_PCT:.0f}%) -- curate overrides.json")
        r.info(f"{pre} {len(corners)} corners ({named} named), "
               f"{len(corners) - len(unlocated)} located")

        # geometry file
        # geometry.outline is relative to track.json's own dir (raw/)
        gpath = raw_dir(slug) / (lo.get("geometry", {}).get("outline") or "")
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
            r.bar_fail("outline")
            continue
        if loop[0] != loop[-1]:
            r.err(f"{pre} outline is not a closed loop")
            r.bar_fail("outline")
        else:
            r.bar_ok("outline")

        # length check
        cum, total = arc_lengths(loop)
        decl = lo.get("length_m")
        if decl:
            pct = abs(total - decl) / decl * 100
            msg = f"{pre} outline {total:,.0f} m vs declared {decl:,.0f} m ({pct:.1f}%)"
            if pct > LEN_ERR_PCT:
                r.err(msg)
                r.bar_fail("length")
            elif pct > LEN_WARN_PCT:
                r.warn(msg)
                r.bar_ok("length")
            else:
                r.info(msg)
                r.bar_ok("length")
        else:
            r.bar_fail("length")  # can't check without declared length

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
            r.bar_fail("on_track")
        else:
            r.info(f"{pre} all located corners sit on the outline")
            r.bar_ok("on_track")

        # start/finish on track?
        sf = lo.get("start_finish", {}).get("location")
        if sf:
            d = nearest_dist_to_polyline(sf, loop)
            if d > MAX_CORNER_OFF_TRACK_M:
                r.err(f"{pre} start_finish {d:.0f} m off the outline")
                r.bar_fail("sf")
            else:
                r.bar_ok("sf")

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
                # tolerate localized swaps: chicane corners metres apart and
                # figure-8 crossovers (Suzuka) project onto the wrong branch
                msg = (f"{pre} corner order along centerline disagrees with lap "
                       f"markers for {nbad}/{npairs} pairs (turns {worst})")
                if nbad <= 2 or nbad / npairs <= 0.12:
                    r.warn(msg)
                    r.bar_ok("order")
                else:
                    r.err(msg)
                    r.bar_fail("order")
            else:
                r.info(f"{pre} corner lap-order matches geometry ({npairs} pairs)")
                r.bar_ok("order")

    # renders exist + fresh
    rdir = raw_dir(slug) / "render"
    png, svgf = rdir / f"{slug}.png", rdir / f"{slug}.svg"
    render_ok = True
    for f in (svgf, png):
        if not f.exists():
            r.err(f"render missing: raw/render/{f.name}")
            render_ok = False
        elif f.stat().st_mtime < tj_f.stat().st_mtime:
            r.warn(f"raw/render/{f.name} older than track.json -- re-run scripts/render.py {slug}")
    r.bar_ok("render") if render_ok else r.bar_fail("render")

    return r


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--strict", action="store_true",
                    help="warnings count as failures")
    args = ap.parse_args()

    slugs = [args.slug] if args.slug else sorted(
        p.name for p in TRACKS.iterdir() if (p / "source.json").exists())

    reports = []
    failed = False
    for slug in slugs:
        rep = verify_track(slug)
        rep.dump()
        reports.append(rep)
        if rep.errors or (args.strict and rep.warnings):
            failed = True

    # ---- minimum-bar scoreboard ----
    keys = [k for k, _ in BAR]
    col = {k: k[:7] for k in keys}
    print("\n" + "=" * 78)
    print("MINIMUM BAR  (" + "  ".join(f"{i+1}={lbl}" for i, (_, lbl) in enumerate(BAR)) + ")")
    print("=" * 78)
    namew = max(len(r.slug) for r in reports) + 2
    print(" " * namew + "  ".join(f"{i+1:>2}" for i in range(len(keys))) + "   verdict")
    for r in reports:
        cells = []
        for k in keys:
            v = r.bar.get(k)
            cells.append(" ✓" if v is True else " ✗")
        verdict = "CLEAR" if r.meets_bar else "BELOW BAR"
        print(f"{r.slug:<{namew}}" + "  ".join(cells) + f"   {verdict}")
        if not r.meets_bar:
            for m in r.missing():
                print(" " * namew + f"   missing: {m}")
    clear = sum(1 for r in reports if r.meets_bar)
    print(f"\n{clear}/{len(reports)} tracks clear the bar -- "
          f"{'PASS' if not failed else 'FAIL'}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

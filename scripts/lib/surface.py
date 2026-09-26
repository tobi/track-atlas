"""Surface geometry: edges -> crossing lines, geometric apexes, surface polygon.

Offline step. Consumes the committed measurement `raw/surface-<layout>.json`
(written by scripts/measure_surface.py) and the layout's point/range layers in
`raw/track.json`, and produces:

  * `layout.surface`              summary, quality and sources
  * `layout.geometry.surface`     -> `layers/<layout>.surface.geojson`
  * corners (`point_layers[corners].items[]`): `entry`, `apex`, `exit`
  * layout points (start/finish, pit entry/exit): `line`
  * every range item: `start_line`, `end_line`; complexes also `entry`/`exit`

The measured midline becomes the layout's geometry and lap-fraction basis: it
is written as the layout's outline (rotated to start at start/finish), and
every marker in the layout is re-expressed on it. Input markers (Lovely,
overrides, OSM, layer tools) are on the seed centerline's basis and are mapped
by projection: the point at the old fraction on the seed, projected onto the
midline. A corner with a geometric placement takes its apex as its marker and
its entry/exit as its range. Re-applying is idempotent: the midline projects
onto itself. The algorithm is documented in docs/GEOMETRY.md.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import geo

STEP = 1.0                 # m, midline station spacing
KAPPA_SIGMA_M = 5.0        # m, smoothing of midline curvature
EDGE_KAPPA_SIGMA_M = 4.0   # m, smoothing of inside-edge curvature
DETECT_SIGMA_M = 8.0       # m, smoothing of midline curvature for corner detection
KAPPA_FLOOR = 1 / 600.0    # 1/m: a lobe is where |curvature| exceeds this (R < 600 m)
MAX_RADIUS_M = 400.0       # m, a peak wider than this is a kink, never a corner
KINK_RADIUS_M = 250.0      # m, a matched peak wider than this is labelled a kink
NOTABLE_RADIUS_M = 80.0    # m, an unclaimed peak tighter than this is reported
SPLIT_DIP = 0.6            # two peaks in one lobe stay separate below this dip ratio
ONSET_FRACTION = 0.35      # turn-in / track-out at this share of the peak curvature
SEARCH_M = 150.0           # m, max distance from the legacy marker to the peak
MATCH_SCALE_M = 80.0       # m of marker distance that cost one unit (legacy markers are often 50-100 m off)
DIRECTION_PENALTY = 2.5    # cost of a peak turning the other way than declared
MISMATCH_MAX_M = 40.0      # m, a peak turning the other way is matched only this close to the marker
STRENGTH_WEIGHT = 1.5      # preference for tighter peaks (per ln of curvature)
UNMATCHED_COST = 1.0       # cost of leaving a corner without a geometric peak
APEX_REFINE_M = 15.0       # m, inside-edge peak search around the midline peak
MIN_ARM_M = 3.0            # m, apex at least this far from entry/exit
MAX_HALF_WIDTH_M = 40.0    # m, an edge hit further than this from the midline is another piece of edge
INTERPOLATED_PENALTY_M = 1.5  # m added to precision where an edge was not seen
OUTLINE_SIMPLIFY_M = 0.02  # m, Douglas-Peucker tolerance of the published midline outline
OUTLINE_MAX_SEG_M = 20.0   # m, longest segment of the published outline
PIT_NAME = r"(?i)\bpit\s*-?\s*(lane|road)?\b|pitlane"


# --- helpers ----------------------------------------------------------------
def _quality(sources: dict, q: dict, measured: bool) -> dict:
    """Quality of a feature placed on the measured edges.

    accuracy_m (95 %) = hypot(position CE95 of the whole measurement, the
    feature's relative precision); see lib/position.py for the budget.
    """
    img = sources["imagery"]
    rel = float(q["relative_precision_m"]) + (0.0 if measured else INTERPOLATED_PENALTY_M)
    ab = math.hypot(float(q["absolute_accuracy_ce95_m"]), rel)
    dates = img.get("acquisition_dates") or []
    out = {"source": img["id"], "accuracy_m": round(ab, 2), "relative_accuracy_m": round(rel, 2),
           "measured": bool(measured)}
    if dates:
        out["date"] = dates[-1]
    return out


def _ray_hits(p: np.ndarray, n: np.ndarray, seg_a: np.ndarray, seg_b: np.ndarray) -> np.ndarray:
    """Signed ray parameters t where p + t n crosses each segment (NaN if not)."""
    d = seg_b - seg_a
    denom = n[0] * d[:, 1] - n[1] * d[:, 0]
    with np.errstate(divide="ignore", invalid="ignore"):
        w = seg_a - p
        t = (w[:, 0] * d[:, 1] - w[:, 1] * d[:, 0]) / denom
        u = (w[:, 0] * n[1] - w[:, 1] * n[0]) / denom
    ok = (np.abs(denom) > 1e-12) & (u >= 0) & (u <= 1)
    return np.where(ok, t, np.nan)


def _nearest_on(p: np.ndarray, seg_a: np.ndarray, seg_b: np.ndarray) -> np.ndarray:
    """The point of the polyline segments closest to p."""
    d = seg_b - seg_a
    L2 = np.maximum((d * d).sum(1), 1e-12)
    u = np.clip(((p - seg_a) * d).sum(1) / L2, 0.0, 1.0)
    q = seg_a + d * u[:, None]
    return q[int(np.argmin(((q - p) ** 2).sum(1)))]


class LapGeometry:
    """Midline stations with the matching edge points and curvature."""

    def __init__(self, measurement: dict, centerline_ll: np.ndarray):
        self.m = measurement
        mid_ll = np.asarray(measurement["midline"], dtype=float)
        self.F = geo.Frame.around(mid_ll)
        self.mid, self.total = geo.resample_closed(self.F.to_xy(geo.open_ring(mid_ll)), STEP)
        self.N = len(self.mid)
        self.cum = geo.cumulative(self.mid)
        self.nrm = geo.left_normals(geo.circular_gaussian(self.mid, 2))
        L = self.F.to_xy(np.asarray(measurement["edges"]["left"], dtype=float))
        R = self.F.to_xy(np.asarray(measurement["edges"]["right"], dtype=float))
        self.left = self._edge_points(L, +1)
        self.right = self._edge_points(R, -1)
        self.kappa = geo.circular_gaussian(geo.curvature(self.mid, STEP), KAPPA_SIGMA_M / STEP)
        self.kappa_detect = geo.circular_gaussian(geo.curvature(self.mid, STEP), DETECT_SIGMA_M / STEP)
        self.kappa_left = self._edge_kappa(self.left)
        self.kappa_right = self._edge_kappa(self.right)
        # centerline (fraction basis) <-> midline station map
        C = geo.open_ring(self.F.to_xy(centerline_ll))
        Cs, self.c_total = geo.resample_closed(C, 1.0)
        self.C = Cs
        self.c_cum = geo.cumulative(Cs)
        st = self._stations_of(Cs)
        # unwrap into a monotone sequence starting near 0
        st = np.unwrap(st / self.total * 2 * math.pi) / (2 * math.pi) * self.total
        st = st - (st[0] // self.total) * self.total if st[0] >= self.total else st
        st = np.maximum.accumulate(st)
        self.c_frac = np.arange(len(Cs)) / len(Cs)
        self.c_station = st
        self.origin = 0.0      # station of output fraction 0 (set by rebase)
        # seen flags per station from the measurement's unseen spans
        self.seen = {side: self._seen(measurement["quality"]["unseen_spans"][side])
                     for side in ("left", "right")}

    def _seen(self, spans) -> np.ndarray:
        f = np.arange(self.N) / self.N
        ok = np.ones(self.N, dtype=bool)
        for a, b in spans:
            ok &= ~((f >= a) & (f < b)) if a <= b else ~((f >= a) | (f < b))
        return ok

    def _edge_points(self, E: np.ndarray, sign: int) -> np.ndarray:
        a, b = E[:-1], E[1:]
        out = np.zeros_like(self.mid)
        for i in range(self.N):
            t = _ray_hits(self.mid[i], self.nrm[i], a, b) * sign
            t = t[np.isfinite(t) & (t > 0) & (t < MAX_HALF_WIDTH_M)]
            if len(t):
                out[i] = self.mid[i] + self.nrm[i] * (sign * t.min())
            else:  # no edge along the normal (a removed loop, a sharp kink): nearest edge point
                out[i] = _nearest_on(self.mid[i], a, b)
        return out

    def _edge_kappa(self, E: np.ndarray) -> np.ndarray:
        d = np.roll(E, -1, axis=0) - np.roll(E, 1, axis=0)
        ds = np.maximum(np.hypot(d[:, 0], d[:, 1]) / 2, 0.05)
        ang = np.arctan2(d[:, 1], d[:, 0])
        dang = np.roll(ang, -1) - np.roll(ang, 1)
        dang = (dang + math.pi) % (2 * math.pi) - math.pi
        return geo.circular_gaussian(dang / (2 * ds), EDGE_KAPPA_SIGMA_M / STEP)

    def _stations_of(self, pts: np.ndarray) -> np.ndarray:
        out = np.empty(len(pts))
        for k, p in enumerate(pts):
            out[k] = geo.project(self.mid, self.cum, p)[0]
        return out

    # fraction (centerline basis) <-> station (midline)
    def station(self, frac: float) -> float:
        f = float(frac) % 1.0
        s = np.interp(f, np.append(self.c_frac, 1.0), np.append(self.c_station, self.c_station[0] + self.total))
        return float(s % self.total)

    def fraction(self, station: float) -> float:
        s = float(station) % self.total
        st = np.append(self.c_station, self.c_station[0] + self.total)
        fr = np.append(self.c_frac, 1.0)
        # the map may start above 0: shift s into its range
        if s < st[0]:
            s += self.total
        return float(np.interp(s, st, fr) % 1.0)

    # output basis: the midline itself, fraction 0 at `origin`
    def rebase(self, origin_station: float) -> None:
        self.origin = float(origin_station) % self.total

    def out_fraction(self, station: float) -> float:
        return ((float(station) - self.origin) % self.total) / self.total

    def remap(self, frac: float) -> float:
        """Seed-basis fraction -> output (midline) fraction (0 and 1 stay put)."""
        if float(frac) >= 1.0:
            return 1.0
        return round(self.out_fraction(self.station(frac)), 5)

    def point(self, station: float) -> list[float]:
        return geo.lonlat_list(self.F.to_lonlat(self.mid[self.idx(station)][None, :]))[0]

    def outline_lonlat(self) -> list[list[float]]:
        """The midline starting exactly at the origin, closed and simplified."""
        i = int(self.origin // STEP) % self.N
        t = (self.origin - i * STEP) / STEP
        p0 = self.mid[i] * (1 - t) + self.mid[(i + 1) % self.N] * t
        rest = np.roll(self.mid, -(i + 1), axis=0)
        ring = geo.simplify_closed(np.vstack([p0[None, :], rest]), OUTLINE_SIMPLIFY_M)
        out = [ring[0]]
        for a, b in zip(ring[:-1], ring[1:]):   # no segment longer than OUTLINE_MAX_SEG_M
            n = int(np.ceil(np.hypot(*(b - a)) / OUTLINE_MAX_SEG_M))
            out.extend(a + (b - a) * (k / n) for k in range(1, n + 1))
        return geo.lonlat_list(self.F.to_lonlat(np.asarray(out)))

    def idx(self, station: float) -> int:
        return int(round(station / STEP)) % self.N

    def crossing(self, station: float, sources: dict, frac: float | None = None) -> dict:
        i = self.idx(station)
        a, b = self.left[i], self.right[i]
        measured = bool(self.seen["left"][i] and self.seen["right"][i])
        ll = self.F.to_lonlat(np.stack([a, b]))
        return {
            "marker": round(self.out_fraction(station) if frac is None else float(frac), 5),
            "line": geo.lonlat_list(ll),
            "width_m": round(float(np.hypot(*(a - b))), 2),
            "quality": _quality(sources, self.m["quality"], measured),
        }


# --- corners ------------------------------------------------------------------
@dataclass
class Candidate:
    """A geometric corner: one curvature peak with its turn-in/track-out bounds."""
    peak: int          # station index of the midline curvature peak
    sign: int          # +1 left, -1 right
    kappa: float       # |curvature| at the peak, 1/m
    lo: int            # first index of the peak's share of its lobe (unwrapped)
    hi: int            # last index (unwrapped, may exceed N)


def candidates(G: LapGeometry) -> list[Candidate]:
    """Curvature peaks along the midline, in lap order.

    A lobe is a run of one turning sign with |kappa| above KAPPA_FLOOR. Every
    local maximum of |kappa| in a lobe whose radius is below MAX_RADIUS_M and
    whose dip to the next accepted peak is at least SPLIT_DIP deep becomes one
    candidate; a lobe with several such peaks is split at the minima between them.
    """
    k = G.kappa_detect
    N = G.N
    sign = np.where(k > KAPPA_FLOOR, 1, np.where(k < -KAPPA_FLOOR, -1, 0))
    if (sign == 0).sum() == 0:
        return []
    start = int(np.argmax(sign == 0))       # rotate so the scan starts off-lobe
    order = (np.arange(N) + start) % N
    out: list[Candidate] = []
    i = 0
    while i < N:
        s = sign[order[i]]
        if s == 0:
            i += 1
            continue
        j = i
        while j < N and sign[order[j]] == s:
            j += 1
        seg = np.abs(k[order[i:j]])
        # local maxima, then merge any pair whose dip is shallow
        peaks = [m for m in range(len(seg))
                 if (m == 0 or seg[m] >= seg[m - 1]) and (m == len(seg) - 1 or seg[m] > seg[m + 1])]
        merged = True
        while merged and len(peaks) > 1:
            merged = False
            for a in range(len(peaks) - 1):
                p, q = peaks[a], peaks[a + 1]
                dip = seg[p:q + 1].min()
                if dip > SPLIT_DIP * min(seg[p], seg[q]):
                    peaks.pop(a + 1 if seg[p] >= seg[q] else a)
                    merged = True
                    break
        bounds = [0]
        for p, q in zip(peaks, peaks[1:]):
            bounds.append(p + int(np.argmin(seg[p:q + 1])))
        bounds.append(len(seg) - 1)
        for n, p in enumerate(peaks):
            if 1 / seg[p] > MAX_RADIUS_M:
                continue
            base = i + start
            out.append(Candidate(peak=(base + p) % N, sign=int(s), kappa=float(seg[p]),
                                 lo=base + bounds[n], hi=base + bounds[n + 1]))
        i = j
    out.sort(key=lambda c: c.peak)
    return out


def _match(G: LapGeometry, corners: list[dict], cands: list[Candidate]) -> list[int | None]:
    """Order-preserving assignment of atlas corners to geometric peaks (DP).

    cost(corner, peak) = |distance from the corner's marker| / MATCH_SCALE_M
                         + DIRECTION_PENALTY if the declared direction disagrees
                           (never matched beyond MISMATCH_MAX_M)
                         - STRENGTH_WEIGHT * ln(kappa / KAPPA_FLOOR)
    A corner may stay unmatched at UNMATCHED_COST; a peak serves one corner;
    peaks further than SEARCH_M from the marker are never matched.
    """
    K, J = len(corners), len(cands)
    s_c = [G.station(c["marker"]) for c in corners]
    INF = float("inf")

    def cost(k: int, j: int) -> float:
        d = abs(geo.unwrap_wrapped(s_c[k], cands[j].peak * STEP, G.total))
        if d > SEARCH_M:
            return INF
        decl = {"left": 1, "right": -1}.get(corners[k].get("direction"))
        pen = 0.0
        if decl is not None and decl != cands[j].sign:
            if d > MISMATCH_MAX_M:
                return INF
            pen = DIRECTION_PENALTY
        return d / MATCH_SCALE_M + pen - STRENGTH_WEIGHT * math.log(cands[j].kappa / KAPPA_FLOOR)

    # D[k][j]: best cost for corners[:k] using peaks[:j]
    D = np.full((K + 1, J + 1), INF)
    D[0, :] = 0.0
    back = {}
    for k in range(1, K + 1):
        for j in range(0, J + 1):
            best, arg = D[k - 1, j] + UNMATCHED_COST, ("skip_corner", j)
            if j > 0 and D[k, j - 1] < best:
                best, arg = D[k, j - 1], ("skip_peak", j - 1)
            if j > 0:
                c = cost(k - 1, j - 1)
                if D[k - 1, j - 1] + c < best:
                    best, arg = D[k - 1, j - 1] + c, ("match", j - 1)
            D[k, j] = best
            back[k, j] = arg
    out: list[int | None] = [None] * K
    k, j = K, J
    while k > 0:
        kind, jj = back[k, j]
        if kind == "match":
            out[k - 1] = jj
            k, j = k - 1, jj
        elif kind == "skip_peak":
            j = jj
        else:
            k -= 1
    return out


def place_corners(G: LapGeometry, corners: list[dict]) -> tuple[list[dict | None], list[dict]]:
    """Geometric entry / apex / exit stations for corners in lap order.

    Returns (per-corner placement or None, unclaimed strong peaks).
    """
    # the matcher is order-preserving over the lap, so peaks must be in the
    # centerline's lap order: the midline may start elsewhere (a pinned
    # start/finish moves the centerline origin, not the measurement)
    s0 = G.station(0.0)
    cands = sorted(candidates(G), key=lambda cd: (cd.peak * STEP - s0) % G.total)
    have = [k for k, c in enumerate(corners) if c.get("marker") is not None]
    m = _match(G, [corners[k] for k in have], cands)
    match: list[int | None] = [None] * len(corners)
    for k, j in zip(have, m):
        match[k] = j
    out: list[dict | None] = []
    for k, c in enumerate(corners):
        j = match[k]
        if j is None:
            out.append(None)
            continue
        cd = cands[j]
        d = cd.sign
        s_peak = cd.peak * STEP
        edge_k = G.kappa_left if d > 0 else G.kappa_right
        r_off = np.arange(-APEX_REFINE_M, APEX_REFINE_M + 1)
        ri = np.array([G.idx(s_peak + o) for o in r_off])
        s_apex = s_peak + r_off[int(np.argmax(d * edge_k[ri]))]
        level = max(KAPPA_FLOOR, ONSET_FRACTION * cd.kappa)
        # walk out from the peak (within its share of the lobe) to the onset level
        p_un = cd.lo + ((cd.peak - cd.lo) % G.N)
        e = p_un
        while e - 1 >= cd.lo and d * G.kappa_detect[(e - 1) % G.N] >= level:
            e -= 1
        x = p_un
        while x + 1 <= cd.hi and d * G.kappa_detect[(x + 1) % G.N] >= level:
            x += 1
        entry = s_peak - (p_un - e) * STEP
        exit_ = s_peak + (x - p_un) * STEP
        decl = c.get("direction")
        meas = "left" if d > 0 else "right"
        out.append({
            "apex": s_apex, "entry": min(entry, s_apex - MIN_ARM_M), "exit": max(exit_, s_apex + MIN_ARM_M),
            "direction": meas, "basis": "curvature", "radius_m": round(1 / cd.kappa, 1),
            "marker_offset_m": round(geo.unwrap_wrapped(G.station(c["marker"]), s_peak, G.total), 1),
            **({"declared_direction": decl} if decl in ("left", "right") and decl != meas else {}),
        })
    used = {j for j in match if j is not None}
    unclaimed = [{"marker": round(G.out_fraction(cd.peak * STEP), 4), "direction": "left" if cd.sign > 0 else "right",
                  "radius_m": round(1 / cd.kappa, 1)}
                 for j, cd in enumerate(cands) if j not in used and 1 / cd.kappa <= NOTABLE_RADIUS_M]
    return out, unclaimed


# --- pit lane -----------------------------------------------------------------
def pit_lane_features(osm: dict, G: LapGeometry) -> list[dict]:
    import re
    rx = re.compile(PIT_NAME)
    feats = []
    for el in osm.get("elements", []):
        if el.get("type") != "way" or not el.get("geometry"):
            continue
        tags = el.get("tags", {})
        name = tags.get("name", "")
        if not (rx.search(name) or tags.get("service") in ("pit_lane", "pitlane")
                or tags.get("raceway") == "pitlane"):
            continue
        ll = np.array([[g["lon"], g["lat"]] for g in el["geometry"]])
        xy = G.F.to_xy(ll)
        d_end = min(geo.project(G.mid, G.cum, xy[0])[2], geo.project(G.mid, G.cum, xy[-1])[2])
        if d_end > 60:
            continue
        feats.append({"type": "Feature", "properties": {
            "role": "pit_lane", "name": name or None, "osm_way": el["id"],
            "quality": {"source": "osm", "accuracy_m": 5.0, "measured": False,
                        "note": "OSM-traced pit-lane centerline; not measured"}},
            "geometry": {"type": "LineString", "coordinates": geo.lonlat_list(ll)}})
    return feats


# --- apply ---------------------------------------------------------------------
def _layer(layout: dict, kind: str, attr: str) -> dict | None:
    return next((L for L in layout.get(attr, []) if L.get("id") == kind or L.get("kind") == kind), None)


def apply_layout(raw: Path, layout: dict, osm: dict | None = None) -> dict | None:
    meas_file = raw / f"surface-{layout['id']}.json"
    if not meas_file.exists():
        layout.pop("surface", None)
        layout.get("geometry", {}).pop("surface", None)
        return None
    meas = json.loads(meas_file.read_text())
    cl_gj = json.loads((raw / layout["geometry"]["centerline"]).read_text())
    cl = np.asarray(next(f for f in cl_gj["features"] if f["properties"].get("role") == "outline")["geometry"]["coordinates"])
    G = LapGeometry(meas, cl)
    sources = meas["sources"]
    q = meas["quality"]
    feats: list[dict] = []

    def ring_ll(xy):
        return geo.lonlat_list(G.F.to_lonlat(np.vstack([xy, xy[:1]])))

    for side in ("left", "right"):
        feats.append({"type": "Feature", "properties": {
            "role": f"edge_{side}", "orientation": "driving direction, from the lap origin",
            "unseen_spans": q["unseen_spans"][side],
            "quality": {**_quality(sources, q, True), "measured_fraction": q["seen_fraction"][side]}},
            "geometry": {"type": "LineString", "coordinates": meas["edges"][side]}})
    feats.append({"type": "Feature", "properties": {
        "role": "midline", "derived_from": ["edge_left", "edge_right"],
        "quality": {**_quality(sources, q, True), "source": "derived"}},
        "geometry": {"type": "LineString", "coordinates": meas["midline"]}})
    # surface polygon: outer ring = the edge away from the loop interior
    poly = _surface_polygon(meas, G)
    if poly:
        feats.append(poly)
    if osm:
        feats.extend(pit_lane_features(osm, G))

    rebased = layout.get("geometry", {}).get("basis") == "midline"
    # fraction 0 = start/finish: the seed's origin, projected onto the midline
    G.rebase(G.station(0.0))

    # layout points: lines across the track
    lp = _layer(layout, "layout_points", "point_layers")
    for it in (lp or {}).get("items", []):
        if it.get("marker") is None:
            continue
        st = G.station(it["marker"])
        it["marker"] = round(G.out_fraction(st), 5)
        it["location"] = G.point(st)
        it["line"] = G.crossing(st, sources)
        feats.append(_line_feature(it["id"], it["id"], it["line"]))

    # corners
    cl_layer = _layer(layout, "corners", "point_layers")
    corners = sorted((cl_layer or {}).get("items", []), key=lambda c: c.get("number", 0))
    old_offsets = {c["id"]: (c.get("placement") or {}).get("marker_offset_m") for c in corners}
    placed, unclaimed = place_corners(G, corners)
    for c, p in zip(corners, placed):
        for k in ("entry", "apex", "exit", "placement"):
            c.pop(k, None)
        if p is None:
            if c.get("marker") is not None:
                st = G.station(c["marker"])
                c["marker"] = round(G.out_fraction(st), 5)
                c["location"] = G.point(st)
                c["location_source"] = "midline"
            for k in ("start", "end"):
                if c.get(k) is not None:
                    c[k] = G.remap(c[k])
            c["placement"] = {"basis": "none",
                              "note": "no curvature peak near the marker; marker projected from the source data"}
            continue
        offset = old_offsets.get(c["id"]) if rebased and old_offsets.get(c["id"]) is not None else p["marker_offset_m"]
        c["placement"] = {"basis": p["basis"], "shape": "kink" if p["radius_m"] > KINK_RADIUS_M else "corner",
                          "direction": p["direction"], "radius_m": p["radius_m"],
                          "marker_offset_m": offset,
                          **({"declared_direction": p["declared_direction"]} if "declared_direction" in p else {})}
        c["entry"] = G.crossing(p["entry"], sources)
        c["exit"] = G.crossing(p["exit"], sources)
        i = G.idx(p["apex"])
        inside = p["direction"]
        pt = (G.left if inside == "left" else G.right)[i]
        c["apex"] = {
            "marker": round(G.out_fraction(p["apex"]), 5),
            "location": geo.lonlat_list(G.F.to_lonlat(pt[None, :]))[0],
            "edge": inside,
            "quality": _quality(sources, q, bool(G.seen[inside][i])),
        }
        # the corner itself is where the geometry says it is
        c["marker"] = c["apex"]["marker"]
        c["location"] = G.point(p["apex"])
        c["location_source"] = "midline"
        if c.get("start") is not None:
            c["start"] = c["entry"]["marker"]
        if c.get("end") is not None:
            c["end"] = c["exit"]["marker"]
        feats.append(_line_feature(f"{c['id']}-entry", "corner_entry", c["entry"], corner=c["id"]))
        feats.append(_line_feature(f"{c['id']}-exit", "corner_exit", c["exit"], corner=c["id"]))
        feats.append({"type": "Feature", "properties": {
            "role": "apex", "id": f"{c['id']}-apex", "corner": c["id"], "edge": inside,
            "marker": c["apex"]["marker"], "quality": c["apex"]["quality"]},
            "geometry": {"type": "Point", "coordinates": c["apex"]["location"]}})

    by_id = {c["id"]: c for c in corners}
    # every other point layer: markers (and locations) onto the midline
    for L in layout.get("point_layers", []):
        if L is cl_layer or L is lp:
            continue
        for it in L.get("items", []):
            if it.get("marker") is None:
                continue
            st = G.station(it["marker"])
            it["marker"] = round(G.out_fraction(st), 5)
            if "location" in it:
                it["location"] = G.point(st)

    # ranges: re-expressed; a corner's range is its geometric entry..exit, a
    # complex's the entry of its first placed member .. exit of its last
    for L in layout.get("range_layers", []):
        for it in L.get("items", []):
            it.pop("entry", None)
            it.pop("exit", None)
            start_line = end_line = None
            anchor = by_id.get(it.get("anchor"))
            if L.get("kind") == "corner_ranges" and anchor and "entry" in anchor:
                start_line, end_line = anchor["entry"], anchor["exit"]
            elif L.get("kind") == "corner_complexes" and it.get("members"):
                # bounded by the first member's entry and the last member's exit;
                # a bound member without a placement keeps the projected bound
                first, last = by_id.get(it["members"][0]), by_id.get(it["members"][-1])
                if first and "entry" in first:
                    it["entry"] = start_line = first["entry"]
                    if len(it["members"]) > 1:
                        feats.append(_line_feature(f"{it['id']}-entry", "complex_entry", it["entry"], complex=it["id"]))
                if last and "exit" in last:
                    it["exit"] = end_line = last["exit"]
                    if len(it["members"]) > 1:
                        feats.append(_line_feature(f"{it['id']}-exit", "complex_exit", it["exit"], complex=it["id"]))
            it["start_line"] = start_line or G.crossing(G.station(it["start"]), sources, frac=G.remap(it["start"]))
            it["end_line"] = end_line or G.crossing(G.station(it["end"]), sources, frac=G.remap(it["end"]))
            it["start"], it["end"] = it["start_line"]["marker"], it["end_line"]["marker"]
            for pt in it.get("points", []):
                ref = by_id.get(pt.get("point_ref"))
                if ref is not None and ref.get("marker") is not None:
                    pt["marker"] = ref["marker"]
                elif pt.get("marker") is not None:
                    pt["marker"] = G.remap(pt["marker"])
            if L.get("kind") in ("timing_sectors",):
                feats.append(_line_feature(f"{it['id']}-start", "sector_boundary", it["start_line"], range=it["id"]))

    _write_outline(raw / layout["geometry"]["centerline"], cl_gj, G, layout)
    layout["geometry"]["basis"] = "midline"

    rel = f"layers/{layout['id']}.surface.geojson"
    (raw / rel).write_text(json.dumps({"type": "FeatureCollection", "features": feats},
                                      ensure_ascii=False, separators=(",", ":")))
    layout.setdefault("geometry", {})["surface"] = rel
    layout["surface"] = {
        "file": rel,
        "method": meas["method"],
        "measured_at": meas["generated_at"],
        "lap_length_m": meas["lap_length_m"],
        "width_m": q["width_m"],
        "seen_fraction": q["seen_fraction"],
        "relative_precision_m": q["relative_precision_m"],
        "absolute_accuracy_ce95_m": q["absolute_accuracy_ce95_m"],
        "position": meas["position"],
        "selection": meas.get("selection"),
        "unnamed_corners": unclaimed,
        "sources": sources,
    }
    return layout


def _write_outline(path: Path, gj: dict, G: LapGeometry, layout: dict) -> None:
    """The layout GeoJSON on the new basis: outline = midline, points at their markers."""
    items = {it["id"]: it for L in layout.get("point_layers", []) for it in L.get("items", [])}
    for ft in gj["features"]:
        pr = ft["properties"]
        if pr.get("role") == "outline":
            ft["geometry"]["coordinates"] = G.outline_lonlat()
            pr["basis"] = "midline"
            continue
        it = items.get(pr.get("id")) or items.get(pr.get("role"))
        if it is not None and it.get("location") is not None:
            ft["geometry"]["coordinates"] = it["location"]
            pr["marker"] = it.get("marker")
    path.write_text(json.dumps(gj, ensure_ascii=False, indent=2))


def _line_feature(fid: str, role: str, crossing: dict, **props) -> dict:
    return {"type": "Feature", "properties": {"role": role, "id": fid, "marker": crossing["marker"],
                                              "width_m": crossing["width_m"], "quality": crossing["quality"], **props},
            "geometry": {"type": "LineString", "coordinates": crossing["line"]}}


def _surface_polygon(meas: dict, G: LapGeometry) -> dict | None:
    from shapely.geometry import LinearRing, Polygon
    L = np.asarray(meas["edges"]["left"])
    R = np.asarray(meas["edges"]["right"])
    lr, rr = LinearRing(L), LinearRing(R)
    if not (lr.is_simple and rr.is_simple):
        return None
    # clockwise lap -> interior on the right -> the left edge is the outer ring
    area = 0.5 * np.sum(G.mid[:, 0] * np.roll(G.mid[:, 1], -1) - np.roll(G.mid[:, 0], -1) * G.mid[:, 1])
    outer, hole = (L, R) if area < 0 else (R, L)
    poly = Polygon(outer, [hole])
    if not poly.is_valid:
        return None
    return {"type": "Feature", "properties": {"role": "surface", "rings": ["outer", "inner"],
                                              "area_m2": None},
            "geometry": {"type": "Polygon", "coordinates": [geo.lonlat_list(outer), geo.lonlat_list(hole)]}}


def apply_track(slug_raw: Path, track: dict) -> dict:
    osm_file = slug_raw / "osm.json"
    osm = json.loads(osm_file.read_text()) if osm_file.exists() else None
    for lo in track.get("layouts", []):
        apply_layout(slug_raw, lo, osm)
    return track

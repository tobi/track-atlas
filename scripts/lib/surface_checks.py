"""Consistency checks for a layout's surface geometry (used by verify.py).

Errors are geometric contradictions (edges that self-intersect or cross, left
and right swapped, a crossing line that does not reach both edges, an apex off
its inside edge or outside its corner). Warnings are curation hints (a curated
direction that disagrees with the geometry, a tight unnamed curvature peak, a
lot of unseen edge).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from shapely.geometry import LinearRing, LineString, Point, Polygon, shape

from . import geo

LINE_TO_EDGE_M = 0.3        # crossing endpoints / apex within this of their edge
MIN_WIDTH_M, MAX_WIDTH_M = 4.0, 45.0
MIN_SEEN_FRACTION = 0.8     # warn when less of an edge than this was seen
GPS_GATE_M = 2.0            # Omatrack draws racing lines / apexes at <= 2 m only


def _circ(a: float, b: float) -> float:
    """Signed b - a on the unit lap."""
    d = (b - a) % 1.0
    return d - 1.0 if d > 0.5 else d


def check_layout(raw: Path, lo: dict) -> tuple[list[str], list[str], list[str]]:
    errs: list[str] = []
    warns: list[str] = []
    infos: list[str] = []
    rel = (lo.get("geometry") or {}).get("surface")
    if not rel:
        return errs, warns, infos
    f = raw / rel
    if not f.exists():
        return [f"surface file missing: {rel}"], warns, infos
    feats = json.loads(f.read_text())["features"]
    by_role: dict[str, list[dict]] = {}
    for ft in feats:
        by_role.setdefault(ft["properties"].get("role"), []).append(ft)
    try:
        Lll = np.asarray(by_role["edge_left"][0]["geometry"]["coordinates"], dtype=float)
        Rll = np.asarray(by_role["edge_right"][0]["geometry"]["coordinates"], dtype=float)
        Mll = np.asarray(by_role["midline"][0]["geometry"]["coordinates"], dtype=float)
    except (KeyError, IndexError):
        return ["surface file lacks edge_left / edge_right / midline"], warns, infos
    F = geo.Frame.around(Mll)
    L, R, M = F.to_xy(Lll), F.to_xy(Rll), F.to_xy(Mll)
    Lr, Rr = LinearRing(L), LinearRing(R)
    for name, ring, raw_xy in (("left", Lr, L), ("right", Rr, R)):
        if not np.allclose(raw_xy[0], raw_xy[-1]):
            errs.append(f"edge_{name} is not closed")
        if not ring.is_simple:
            errs.append(f"edge_{name} self-intersects")
    if Lr.intersects(Rr):
        errs.append("edge_left and edge_right cross")
    # left in the driving direction: the midline's left normal points at it
    Mo, _ = geo.resample_closed(geo.open_ring(M), 5.0)
    nrm = geo.left_normals(Mo)
    Ls, Rs = LineString(L), LineString(R)
    wrong = 0
    for p, n in zip(Mo[::10], nrm[::10]):
        dl = Ls.distance(Point(p + n * 1.0)) - Ls.distance(Point(p - n * 1.0))
        dr = Rs.distance(Point(p - n * 1.0)) - Rs.distance(Point(p + n * 1.0))
        wrong += (dl > 0) + (dr > 0)
    if wrong > 0.05 * 2 * len(Mo[::10]):
        errs.append(f"edges not left/right of the driving direction at {wrong} of {2 * len(Mo[::10])} probes")
    area = 0.5 * float(np.sum(Mo[:, 0] * np.roll(Mo[:, 1], -1) - np.roll(Mo[:, 0], -1) * Mo[:, 1]))
    measured = "clockwise" if area < 0 else "anticlockwise"
    if lo.get("direction") and lo["direction"] != measured:
        errs.append(f"layout.direction {lo['direction']} but the measured lap runs {measured}")
    for ft in by_role.get("surface", []):
        if not shape(ft["geometry"]).is_valid:
            errs.append("surface polygon is invalid")

    def crossing(name: str, c: dict | None) -> None:
        if not c:
            return
        a, b = F.to_xy(np.asarray(c["line"], dtype=float))
        da, db = Ls.distance(Point(a)), Rs.distance(Point(b))
        if max(da, db) > LINE_TO_EDGE_M:
            errs.append(f"{name} line does not span the edges (left {da:.2f} m, right {db:.2f} m off)")
        if not (MIN_WIDTH_M <= c["width_m"] <= MAX_WIDTH_M):
            errs.append(f"{name} width {c['width_m']} m is implausible")

    for L_ in lo.get("point_layers", []):
        for it in L_.get("items", []):
            crossing(f"{it['id']}", it.get("line"))
            if L_.get("kind") != "corners":
                continue
            crossing(f"{it['id']} entry", it.get("entry"))
            crossing(f"{it['id']} exit", it.get("exit"))
            ap = it.get("apex")
            if ap:
                if not (it.get("entry") and it.get("exit")):
                    errs.append(f"{it['id']} has an apex without entry/exit lines")
                    continue
                e = _circ(ap["marker"], it["entry"]["marker"])
                x = _circ(ap["marker"], it["exit"]["marker"])
                if not (e < 0 < x):
                    errs.append(f"{it['id']} apex {ap['marker']} not between entry {it['entry']['marker']} and exit {it['exit']['marker']}")
                edge = Ls if ap["edge"] == "left" else Rs
                d = edge.distance(Point(F.to_xy(np.asarray(ap["location"], dtype=float))))
                if d > LINE_TO_EDGE_M:
                    errs.append(f"{it['id']} apex is {d:.2f} m off its {ap['edge']} edge")
                declared = (it.get("placement") or {}).get("declared_direction")
                if it.get("direction") and it["direction"] != ap["edge"] and not declared:
                    errs.append(f"{it['id']} is a {it['direction']}-hander but its apex is on the {ap['edge']} edge")
            pl = it.get("placement") or {}
            if pl.get("declared_direction"):
                warns.append(f"{it['id']} curated direction {pl['declared_direction']} but the geometry turns {pl['direction']}")
            if pl.get("basis") == "none":
                warns.append(f"{it['id']} has no curvature peak near its marker (no entry/apex/exit)")
    for L_ in lo.get("range_layers", []):
        for it in L_.get("items", []):
            crossing(f"{L_['kind']}.{it['id']} start", it.get("start_line"))
            crossing(f"{L_['kind']}.{it['id']} end", it.get("end_line"))
            crossing(f"{L_['kind']}.{it['id']} entry", it.get("entry"))
            crossing(f"{L_['kind']}.{it['id']} exit", it.get("exit"))
    s = lo.get("surface") or {}
    for u in s.get("unnamed_corners", []):
        warns.append(f"unnamed {u['direction']} curvature peak R {u['radius_m']} m at {u['marker']} (no atlas corner)")
    seen = (s.get("seen_fraction") or {})
    for side in ("left", "right"):
        if seen.get(side, 1.0) < MIN_SEEN_FRACTION:
            warns.append(f"edge_{side} seen on only {seen[side]:.0%} of the lap (rest bridged)")
    ab = s.get("absolute_accuracy_ce95_m")
    if ab is not None and ab > GPS_GATE_M:
        infos.append(f"surface absolute accuracy {ab} m (CE95) is above the {GPS_GATE_M:g} m racing-line gate; "
                     f"relative precision {s.get('relative_precision_m')} m")
    return errs, warns, infos

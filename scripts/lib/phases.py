"""Corner phase computation: braking-zone start / apex / corner exit.

A corner doesn't begin at the apex. For anything you brake for it starts a few
hundred metres earlier (turn-in / brake point) and ends a few seconds into the
throttle on exit; the distances scale with severity (hairpin = long braking
zone, kink = none). Neighbours are resolved so phases never overlap, and corners
inside one complex meet exactly (curve 1 ends where curve 2 starts). The apex is
the corner's existing marker.

generate.py calls this to populate corner.start / corner.end; suggest_phases.py
uses it to preview and tune the distance tables.
"""
from __future__ import annotations

# Braking distance (before apex) and exit distance (after apex), metres, by
# severity. 1 = hairpin (long brake) ... 6 = flat-out kink (none). Rough on
# purpose -- tune here.
BRAKE_M = {1: 250, 2: 180, 3: 120, 4: 70, 5: 35, 6: 0}
EXIT_M = {1: 170, 2: 130, 3: 100, 4: 70, 5: 45, 6: 0}
DEFAULT_SCALE = 3


def _frac(m: float) -> float:
    return m % 1.0


def _gap(a: float, b: float) -> float:
    return (b - a) % 1.0


def compute_phases(corners: list[dict], total_m: float) -> dict:
    """Map corner number -> {start, apex, end, brakes} as lap fractions, with
    overlaps resolved and same-complex corners meeting exactly."""
    cs = [c for c in corners if c.get("marker") is not None]
    cs.sort(key=lambda c: c["marker"])
    if not cs or not total_m:
        return {}

    ph = []
    for c in cs:
        scale = c.get("scale") or DEFAULT_SCALE
        bm, em = BRAKE_M.get(scale, 120), EXIT_M.get(scale, 100)
        apex = _frac(c["marker"])
        ph.append({"number": c["number"], "complex": c.get("complex"),
                   "apex": apex, "_b": bm / total_m, "_e": em / total_m,
                   "start": _frac(apex - bm / total_m),
                   "end": _frac(apex + em / total_m), "brakes": bm > 0})

    n = len(ph)
    for i in range(n):
        a, b = ph[i], ph[(i + 1) % n]
        gap = _gap(a["apex"], b["apex"])
        want = a["_e"] + b["_b"]
        same_complex = a["complex"] and a["complex"] == b["complex"]
        if want > gap or same_complex:
            split = (a["_e"] / want) if want > 0 else 0.5
            boundary = _frac(a["apex"] + gap * split)
            a["end"] = boundary
            b["start"] = boundary

    return {p["number"]: {"start": round(p["start"], 5), "apex": round(p["apex"], 5),
                          "end": round(p["end"], 5), "brakes": p["brakes"]}
            for p in ph}

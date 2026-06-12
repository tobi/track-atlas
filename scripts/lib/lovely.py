"""Normalize Lovely-Sim-Racing track JSON into track-atlas corner/straight records.

Lovely encodes everything as lap fractions [0,1]: turn.marker is the apex,
turn.scale is 1-6 severity, turn.direction is 0=left/1=right. We keep all of it.
"""
from __future__ import annotations


def corners_from_lovely(lovely: dict) -> list[dict]:
    """Normalize Lovely turns into the layered-naming model.

    'numbered' is always synthesized ('Turn N'); it numbers everything that
    bends, assigning sequential numbers when the source omits them (several
    sims, e.g. F1 2025 / iRacing, give names but no turn numbers). Lovely's
    free-text 'name' is treated as the colloquial layer -- it's what the data
    community/drivers call the corner. Official names are layered in later via
    overrides.json. A per-track default chooses which layer to surface.
    """
    out = []
    seq = 0
    for t in lovely.get("turn", []):
        seq += 1
        num = t["number"] if t.get("number") is not None else seq
        names = {"numbered": f"Turn {num}"}
        if t.get("name"):
            names["colloquial"] = t["name"]
        c = {"number": num, "names": names}
        if t.get("direction") is not None:
            c["direction"] = "right" if t["direction"] == 1 else "left"
        if t.get("scale") is not None:
            c["scale"] = t["scale"]
        for k in ("marker", "start", "end"):
            if t.get(k) is not None:
                c[k] = t[k]
        # Some sims (iRacing) give start/end lap fractions but no apex marker.
        # Synthesize it as the cyclic midpoint so corners can still be placed
        # on the centerline by lap fraction.
        if "marker" not in c and "start" in c and "end" in c:
            span = (c["end"] - c["start"]) % 1.0
            c["marker"] = round((c["start"] + span / 2.0) % 1.0, 6)
        out.append(c)
    return out


def straights_from_lovely(lovely: dict) -> list[dict]:
    out = []
    for s in lovely.get("straight", []):
        rec = {"name": s.get("name", "")}
        for k in ("start", "end"):
            if k in s:
                rec[k] = s[k]
        out.append(rec)
    return out


def sectors_from_lovely(lovely: dict) -> list[dict]:
    return [{"name": s.get("name", ""), "marker": s["marker"]}
            for s in lovely.get("sector", []) if "marker" in s]


def pit_from_lovely(lovely: dict) -> dict:
    pit = {}
    if "pitentry" in lovely:
        pit["entry"] = lovely["pitentry"]
    if "pitexit" in lovely:
        pit["exit"] = lovely["pitexit"]
    return pit

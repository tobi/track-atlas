"""Normalize Lovely-Sim-Racing track JSON into track-atlas corner/straight records.

Lovely encodes everything as lap fractions [0,1]: turn.marker is the apex,
turn.scale is 1-6 severity, turn.direction is 0=left/1=right. We keep all of it.
"""
from __future__ import annotations


def corners_from_lovely(lovely: dict) -> list[dict]:
    """Normalize Lovely turns into the layered-naming model.

    Every corner gets a ``code`` (the trackside identifier, str(number)) and an
    always-present ``numbered`` layer ('Turn <code>') -- the base layer that
    covers unnamed corners too. Sequential numbers are synthesized when the
    source omits them (several sims, e.g. F1 2025 / iRacing, give names but no
    turn numbers). Lovely's free-text 'name' is treated as the 'driver' layer --
    what the data community/drivers call the corner. Official names are layered
    in later via overrides.json. A per-track default chooses which layer to
    surface.
    """
    out = []
    seq = 0
    for t in lovely.get("turn", []):
        seq += 1
        num = t["number"] if t.get("number") is not None else seq
        code = str(num)
        names = {"numbered": f"Turn {code}"}
        if t.get("name"):
            names["driver"] = t["name"]
        c = {"number": num, "code": code, "names": names}
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


def sectors_s1s3(lovely: dict) -> list[dict]:
    """The three canonical timing sectors S1/S2/S3 as {name, start, end} lap
    fractions. Every circuit gets exactly three. We take Lovely's sector
    boundaries (which range from 3 to ~6 mini-sectors, and are occasionally
    buggy) and pick the two internal boundaries nearest 1/3 and 2/3; with no
    usable data we fall back to even thirds.
    """
    raw = [s["marker"] for s in lovely.get("sector", [])
           if isinstance(s.get("marker"), (int, float))]
    internal = sorted({round(m, 5) for m in raw if 0.02 < m < 0.98})
    if len(internal) >= 2:
        b1 = min(internal, key=lambda m: abs(m - 1 / 3))
        upper = [m for m in internal if m > b1 + 0.05]
        b2 = min(upper, key=lambda m: abs(m - 2 / 3)) if upper else (b1 + 1.0) / 2
    elif len(internal) == 1:
        b1 = internal[0]
        b2 = (b1 + 1.0) / 2
    else:
        b1, b2 = 1 / 3, 2 / 3
    b1, b2 = round(b1, 5), round(b2, 5)
    return [
        {"name": "S1", "start": 0.0, "end": b1},
        {"name": "S2", "start": b1, "end": b2},
        {"name": "S3", "start": b2, "end": 1.0},
    ]


def pit_from_lovely(lovely: dict) -> dict:
    pit = {}
    if "pitentry" in lovely:
        pit["entry"] = lovely["pitentry"]
    if "pitexit" in lovely:
        pit["exit"] = lovely["pitexit"]
    return pit

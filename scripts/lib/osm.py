"""OSM -> track-atlas geometry + corner helpers.

The key insight that makes this repo tractable: OpenStreetMap tags individual
circuit segments (ways with highway=raceway) with their real corner names
("Tertre Rouge", "Mulsanne", "Indianapolis", ...). So OSM gives us geometry AND
named corners with coordinates in one pull -- no fragile name->position guessing.
"""
from __future__ import annotations

import math
import re

# Way names that are infrastructure, not corners.
NON_CORNER = re.compile(
    r"(pit|circuit|ligne droite|straight|long lap|penalty|safety car|porsche center|"
    r"maison blanche|s du garage|moto)",
    re.I,
)


def ways_in_bbox(south, west, north, east):
    """Overpass QL to pull every named raceway way in a bounding box."""
    return (
        f'[out:json][timeout:180];'
        f'(way["highway"="raceway"]({south},{west},{north},{east}););'
        f'out geom;'
    )


def haversine(a, b):
    """Metres between two [lon,lat] points."""
    lon1, lat1, lon2, lat2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def way_coords(el):
    """[ [lon,lat], ... ] for an Overpass way element with out geom."""
    return [[g["lon"], g["lat"]] for g in el.get("geometry", [])]


def named_corner_ways(elements):
    """Return [(name, coords)] for ways whose name looks like a corner."""
    out = []
    for el in elements:
        if el.get("type") != "way":
            continue
        name = (el.get("tags") or {}).get("name")
        if not name or NON_CORNER.search(name):
            continue
        coords = way_coords(el)
        if len(coords) >= 2:
            out.append((name, coords))
    return out


def centroid(coords):
    n = len(coords)
    return [sum(c[0] for c in coords) / n, sum(c[1] for c in coords) / n]


# Ways to exclude when tracing the main racing surface (pit lanes, sub-circuits,
# access roads that share a name root with the circuit).
TRACE_DROP = re.compile(
    r"pit|bugatti|prost|c\.?i\.?k|amateur|\bkart\b|karting|\bmoto\b|penalty|"
    r"safety|maison blanche|garage bleu|chapelle|mus[eé]e|garage vert|"
    r"b[oœ]ufs|porsche cent",
    re.I,
)


def trace_loop(elements, corners):
    """Stitch a continuous track outline from OSM way geometry, ordered by lap
    fraction.

    Each named corner in `corners` carries a `marker` (lap fraction 0..1) and
    name layers. We match OSM ways (highway=raceway) to those markers by name,
    sort the matched way segments by lap position, orient each to chain onto the
    previous, and concatenate. Gaps (e.g. the Mulsanne public-road section not
    tagged as raceway) are bridged by the straight line between segment ends.

    Returns a list of [lon, lat] points, or None if too few segments matched.
    This preserves real chicane/corner geometry — unlike a spline through apex
    points, which erases it.
    """
    # name(normalized) -> lap marker, keeping the earliest mention
    marker_of = {}
    for c in corners:
        m = c.get("marker")
        if m is None:
            continue
        names = c.get("names", {})
        for layer in ("official", "colloquial"):
            nm = names.get(layer)
            if nm:
                marker_of.setdefault(normalize(nm), m)

    # Collect matched ways; dedupe by marker keeping the longest segment so two
    # OSM ways for the same corner don't create a self-intersecting curl.
    by_marker = {}
    for el in elements:
        if el.get("type") != "way":
            continue
        name = (el.get("tags") or {}).get("name") or ""
        if not name or TRACE_DROP.search(name):
            continue
        key = normalize(name)
        if key not in marker_of:
            continue
        coords = way_coords(el)
        if len(coords) < 2:
            continue
        m = marker_of[key]
        if m not in by_marker or len(coords) > len(by_marker[m][1]):
            by_marker[m] = (name, coords)

    segs = [by_marker[m] for m in sorted(by_marker)]
    if len(segs) < 4:
        return None

    loop = list(segs[0][1])
    for _name, c in segs[1:]:
        # orient segment so its near end joins the current loop tail
        if haversine(loop[-1], c[-1]) < haversine(loop[-1], c[0]):
            c = c[::-1]
        loop += c
    return loop


def loop_length_m(loop):
    return sum(haversine(loop[i], loop[i + 1]) for i in range(len(loop) - 1))



def normalize(s):
    """Loose key for matching corner names across sources (accent/diacritic-insensitive)."""
    import unicodedata

    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(virage|courbe|chicane|esses|ligne droite|le|la|les|l|du|de|des|d|the|s)\b",
               " ", s)
    return re.sub(r"[^a-z0-9]+", "", s)

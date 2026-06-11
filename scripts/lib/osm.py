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


def normalize(s):
    """Loose key for matching corner names across sources (accent/diacritic-insensitive)."""
    import unicodedata

    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(virage|courbe|chicane|esses|ligne droite|le|la|les|l|du|de|des|d|the|s)\b",
               " ", s)
    return re.sub(r"[^a-z0-9]+", "", s)

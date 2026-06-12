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


def relation_geom(relation_id):
    """Overpass QL to pull a route/circuit relation with full member geometry.

    A `type=route` (or `type=circuit`) relation is OSM's blessed *continuous
    lap*: it orders every way of the racing surface, including public-road
    sections (e.g. the Mulsanne straight, D338) that aren't tagged
    highway=raceway. This is the authoritative centerline source.
    """
    return (
        f'[out:json][timeout:120];'
        f'relation({int(relation_id)});'
        f'out geom;'
    )


def relation_centerline(relation_data, expected_m=None):
    """Chain a route-relation's member ways into one ordered centerline.

    `relation_data` is an Overpass `out geom` result whose first element is the
    relation. Member ways carry their own ordered `geometry`.

    Two strategies, best result wins (judged by closure + traced length vs
    `expected_m` when given):

      1. member-order chaining -- the relation lists ways in lap order; orient
         each onto the previous and concatenate (works for well-curated
         relations like Le Mans 2126739).
      2. graph cycle search -- snap way endpoints into nodes, DFS for closed
         cycles through the longest way, pick the cycle whose length is closest
         to `expected_m` (or the longest cycle without it). This handles
         relations whose members are unordered, duplicated (dual-carriageway
         street circuits), or include alternate-layout branches.

    Returns [[lon, lat], ...] forming a closed loop, or None if unavailable.
    This is the real surface — every chicane and kink preserved.
    """
    els = relation_data.get("elements", [])
    rel = next((e for e in els if e.get("type") == "relation"), None)
    if rel is None:
        return None
    segs = []
    seen_refs = set()
    for m in rel.get("members", []):
        if m.get("type") != "way":
            continue
        # skip non-lap members (pit lanes etc.) -- only '' / 'forward' /
        # 'backward' / 'main_track' roles are part of the racing lap
        if m.get("role") not in ("", None, "forward", "backward", "main_track"):
            continue
        # some circuit relations list each way twice (out-and-back duplication);
        # keep the first occurrence only
        ref = m.get("ref")
        if ref is not None and ref in seen_refs:
            continue
        seen_refs.add(ref)
        g = m.get("geometry")
        if not g or len(g) < 2:
            continue
        segs.append([[p["lon"], p["lat"]] for p in g])
    if not segs:
        return None
    if len(segs) == 1:
        # single-way relation (e.g. Montreal main_track): use it directly if
        # it's already (nearly) a closed loop
        loop = segs[0]
        return loop if haversine(loop[0], loop[-1]) < 50.0 else None

    candidates = []
    chained = _chain_in_member_order(segs)
    if chained:
        candidates.append(chained)
    cycle = _graph_cycle(segs, expected_m)
    if cycle:
        candidates.append(cycle)
    if not candidates:
        return None

    def score(loop):
        gap = haversine(loop[0], loop[-1])
        L = loop_length_m(loop)
        s = 0.0
        s += min(gap, 500.0)  # open loops are bad
        if expected_m:
            s += abs(L - expected_m) / expected_m * 1000.0  # length error dominates
        return s

    return min(candidates, key=score)


def _chain_in_member_order(segs):
    """Strategy 1: concatenate member ways in relation order."""
    # Orient the first segment against the second so direction is consistent.
    s0, s1 = segs[0], segs[1]
    if (min(haversine(s0[0], s1[0]), haversine(s0[0], s1[-1]))
            < min(haversine(s0[-1], s1[0]), haversine(s0[-1], s1[-1]))):
        segs = [s0[::-1]] + segs[1:]

    loop = list(segs[0])
    for s in segs[1:]:
        # flip s if its tail is nearer the current end than its head
        if haversine(loop[-1], s[-1]) < haversine(loop[-1], s[0]):
            s = s[::-1]
        # avoid duplicating the shared node between consecutive ways
        if haversine(loop[-1], s[0]) < 1.0:
            loop.extend(s[1:])
        else:
            loop.extend(s)
    return loop


def _graph_cycle(segs, expected_m=None):
    """Strategy 2: treat ways as graph edges and search for the lap cycle.

    Snap endpoints to ~5 m nodes, run an iterative DFS from the longest way,
    and collect simple cycles back to its start. Returns the cycle closest in
    length to expected_m (or the longest one). Handles unordered members,
    dual-carriageway duplicates and branch ways (old chicanes, alt layouts).
    """
    def key(p):
        return (round(p[0] * 20000), round(p[1] * 20000))  # ~5 m bins

    edges = []  # (node_a, node_b, coords)
    for c in segs:
        edges.append((key(c[0]), key(c[-1]), c))
    adj = {}
    for i, (a, b, _c) in enumerate(edges):
        adj.setdefault(a, []).append((i, b, False))
        adj.setdefault(b, []).append((i, a, True))

    lens = [loop_length_m(c) for _, _, c in (edges)]
    start_i = max(range(len(edges)), key=lambda i: lens[i])
    sa, sb, sc = edges[start_i]

    best = None
    best_err = float("inf")
    # DFS from sb back to sa, not reusing edges.
    stack = [(sb, [start_i], {start_i}, lens[start_i])]
    iters = 0
    while stack:
        iters += 1
        if iters > 200000:
            break
        node, path, used, dist = stack.pop()
        if expected_m and dist > (expected_m * 1.6 + 2000):
            continue
        if node == sa and len(path) > 1:
            err = abs(dist - expected_m) if expected_m else -dist
            if err < best_err:
                best_err, best = err, list(path)
            continue
        for ei, other, _rev in adj.get(node, []):
            if ei in used:
                continue
            stack.append((other, path + [ei], used | {ei}, dist + lens[ei]))

    if not best:
        return None
    # stitch the chosen edge sequence into one polyline
    coords = list(edges[best[0]][2])
    for ei in best[1:]:
        c = edges[ei][2]
        if haversine(coords[-1], c[-1]) < haversine(coords[-1], c[0]):
            c = c[::-1]
        if haversine(coords[-1], c[0]) < 10.0:
            coords.extend(c[1:])
        else:
            coords.extend(c)
    return coords


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


# Ways that are never part of the main lap (sub-circuits, pit, service).
# Includes Japanese names seen at Fuji (drift course, short circuit, kart).
STITCH_DROP = re.compile(
    r"pit|penalty|long lap|safety|kart|karting|moto\b|drift|short|"
    r"ドリフト|ショート|カート|スクール|paddock|service|access",
    re.I,
)


def stitch_circuit_ways(elements, drop=STITCH_DROP):
    """Spatially chain bbox raceway ways into one closed lap.

    For circuits whose OSM ways are named after the CIRCUIT (Fuji Speedway,
    Miami International Autodrome...) rather than corners, the name-based
    trace finds nothing. Here we ignore names entirely: drop obvious non-lap
    ways (pit, kart, drift...), start from the longest segment, and greedily
    append whichever remaining way has an endpoint nearest the current tail
    (within 60 m), flipping as needed. Spatially separate sub-circuits never
    attach. Returns a closed [[lon,lat],...] loop or None.
    """
    cands = []
    for el in elements:
        if el.get("type") != "way":
            continue
        name = (el.get("tags") or {}).get("name") or ""
        if name and drop.search(name):
            continue
        c = way_coords(el)
        if len(c) >= 2:
            cands.append(c)
    if not cands:
        return None
    cands.sort(key=lambda c: -loop_length_m(c))
    loop = list(cands.pop(0))
    GAP = 60.0
    while cands:
        bestd, bestidx, bestflip = GAP, None, False
        for idx, c in enumerate(cands):
            d0 = haversine(loop[-1], c[0])
            d1 = haversine(loop[-1], c[-1])
            if d0 < bestd:
                bestd, bestidx, bestflip = d0, idx, False
            if d1 < bestd:
                bestd, bestidx, bestflip = d1, idx, True
        if bestidx is None:
            break
        c = cands.pop(bestidx)
        if bestflip:
            c = c[::-1]
        loop.extend(c[1:] if haversine(loop[-1], c[0]) < 1.0 else c)
    if haversine(loop[0], loop[-1]) > 150:
        return None  # never closed -- not a usable lap
    return loop


def orient_loop(loop, direction):
    """Orient a closed loop to run in the given racing direction
    ('clockwise'/'anticlockwise', map view). Shoelace area in projected
    coords: negative = clockwise traversal."""
    if not direction:
        return loop
    k = math.cos(math.radians(loop[0][1]))
    area = 0.0
    for a, b in zip(loop, loop[1:]):
        area += (a[0] * k) * b[1] - (b[0] * k) * a[1]
    cw = area < 0
    want_cw = direction == "clockwise"
    return loop if cw == want_cw else loop[::-1]


def pit_lane_centroid(elements):
    """Centroid of ways named like a pit lane, or None."""
    pts = []
    for el in elements:
        if el.get("type") != "way":
            continue
        name = (el.get("tags") or {}).get("name") or ""
        if re.search(r"pit ?lane", name, re.I):
            pts.extend(way_coords(el))
    return centroid(pts) if pts else None


def rotate_loop_to(loop, pt):
    """Rotate a closed loop so its first vertex is the one nearest pt.
    The pit lane sits alongside the start/finish straight, so anchoring the
    lap origin there approximates marker 0.0 when no named corners matched."""
    best, bi = float("inf"), 0
    for i, p in enumerate(loop[:-1] if loop[0] == loop[-1] else loop):
        d = haversine(pt, p)
        if d < best:
            best, bi = d, i
    body = loop[:-1] if loop[0] == loop[-1] else loop
    return body[bi:] + body[:bi]


def densify(loop, max_seg_m=30.0):
    """Insert interpolated points so no segment exceeds max_seg_m metres.
    Sparse OSM straights (a 1.3 km straight can be a single 2-node segment)
    break nearest-vertex math in consumers; densifying fixes that."""
    out = [loop[0]]
    for a, b in zip(loop, loop[1:]):
        d = haversine(a, b)
        if d > max_seg_m:
            n = int(d // max_seg_m) + 1
            for i in range(1, n):
                t = i / n
                out.append([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t])
        out.append(b)
    return out


def arc_lengths(loop):
    """Cumulative arc length (metres) along a polyline. Returns (cum, total)."""
    cum = [0.0]
    for a, b in zip(loop, loop[1:]):
        cum.append(cum[-1] + haversine(a, b))
    return cum, cum[-1]


def nearest_fraction(loop, cum, total, pt):
    """Lap fraction (0..1) of the centerline vertex nearest to `pt`."""
    best, bi = float("inf"), 0
    for i, p in enumerate(loop):
        d = haversine(pt, p)
        if d < best:
            best, bi = d, i
    return (cum[bi] / total) if total else 0.0, best


def point_at_fraction(loop, cum, total, frac):
    """Interpolated [lon, lat] at lap fraction `frac` (0..1) along the loop."""
    if not total:
        return list(loop[0])
    target = (frac % 1.0) * total
    for i in range(1, len(cum)):
        if cum[i] >= target:
            seg = (cum[i] - cum[i - 1]) or 1e-9
            t = (target - cum[i - 1]) / seg
            a, b = loop[i - 1], loop[i]
            return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
    return list(loop[-1])


def align_markers_to_centerline(loop, matched):
    """Map lap-fraction markers onto a centerline using matched corners as
    control points.

    `matched` is a list of (marker, [lon,lat]) for corners whose real location
    is known. We learn how lap-marker (from Lovely) corresponds to centerline
    arc-fraction, automatically resolving the centerline's arbitrary start node
    and travel direction. Returns a callable `place(marker) -> [lon, lat]` plus
    the (possibly reversed) oriented loop so the outline is drawn the same way.

    This is what lets an *unlocated* corner (e.g. Le Mans Indianapolis, which has
    no highway=raceway way of its own) be placed exactly on the real track by its
    lap fraction.
    """
    cum, total = arc_lengths(loop)
    ctrl = []
    for marker, loc in matched:
        cf, _ = nearest_fraction(loop, cum, total, loc)
        ctrl.append((marker, cf))
    ctrl.sort(key=lambda x: x[0])
    if len(ctrl) < 2:
        # not enough anchors to align; place by raw fraction
        return (lambda m: point_at_fraction(loop, cum, total, m)), loop

    # Determine travel direction: sum wrapped deltas of centerline fraction as
    # marker increases. Negative -> centerline runs opposite the lap; reverse.
    def wrap_half(d):
        return (d + 0.5) % 1.0 - 0.5

    drift = sum(wrap_half(ctrl[i + 1][1] - ctrl[i][1]) for i in range(len(ctrl) - 1))
    if drift < 0:
        loop = loop[::-1]
        cum, total = arc_lengths(loop)
        ctrl = [(m, 1.0 - cf) for m, cf in ctrl]
        ctrl.sort(key=lambda x: x[0])

    # Unwrap centerline fractions to a monotonic increasing sequence.
    markers = [c[0] for c in ctrl]
    cfs = [c[1] for c in ctrl]
    un = [cfs[0]]
    for i in range(1, len(cfs)):
        d = cfs[i] - cfs[i - 1]
        if d < 0:
            d += 1.0
        un.append(un[-1] + d)

    # Markers are cyclic (lap fractions): extend the control set with wrapped
    # copies of the last/first anchors so markers outside [markers[0],
    # markers[-1]] (e.g. the 0.0 start/finish line) interpolate across the lap
    # boundary instead of extrapolating with an arbitrary edge slope.
    markers = [markers[-1] - 1.0] + markers + [markers[0] + 1.0]
    un = [un[-1] - 1.0] + un + [un[0] + 1.0]

    def place(marker):
        # piecewise-linear interpolate marker -> unwrapped centerline fraction
        # within the cyclically-extended control set.
        m = marker
        if m < markers[0]:
            m += 1.0
        elif m > markers[-1]:
            m -= 1.0
        i = max(j for j in range(len(markers) - 1) if markers[j] <= m)
        m0, m1 = markers[i], markers[i + 1]
        f0, f1 = un[i], un[i + 1]
        t = (m - m0) / ((m1 - m0) or 1e-9)
        return point_at_fraction(loop, cum, total, (f0 + t * (f1 - f0)) % 1.0)

    return place, loop



def normalize(s):
    """Loose key for matching corner names across sources (accent/diacritic-insensitive)."""
    import unicodedata

    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(virage|courbe|chicane|esses|ligne droite|le|la|les|l|du|de|des|d|the|s)\b",
               " ", s)
    return re.sub(r"[^a-z0-9]+", "", s)

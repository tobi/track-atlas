"""IGN LiDAR HD (France) point clouds as a registration reference.

LiDAR HD is IGN's national airborne lidar programme, published under the
Licence Ouverte Etalab 2.0 (compatible with ODbL, attribution "IGN"). The
classified point clouds are 1 km x 1 km COPC tiles in Lambert-93 (EPSG:2154,
RGF93), ~10 pulses/m2 and 20-40 points/m2. The tile index (with a download
URL per tile) is the Géoplateforme WFS layer IGNF_LIDAR-HD_METADONNEE:metadata.

Only the COPC octree nodes that touch a corridor around the seed lap are read,
with HTTP range requests (a tile is ~200 MB; the corridor needs a few
percent of it). The points of each tile's corridor are cached as .npz under
`tracks/<slug>/raw/lidar/IGN_LiDAR_HD/` (gitignored; recreatable from the
recorded tile URLs).

Coordinates are returned like the 3DEP EPT points (lib/lidar.Points): EPSG:3857
metres of the RGF93 longitude/latitude, i.e. RGF93 written as if it were
WGS 84. lib/datum.py moves RGF93 (ETRF2000) to the atlas frame.
"""
from __future__ import annotations

import io
import json
import math
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from .imagery import lonlat_to_merc, merc_to_lonlat
from .sources import UA

NAME = "IGN_LiDAR_HD"
WFS = "https://data.geopf.fr/wfs/ows"
TILE_INDEX = "IGNF_LIDAR-HD_METADONNEE:metadata"
COVERAGE = [-5.3, 41.3, 9.7, 51.2]  # metropolitan France (the programme's extent)
LICENSE = "Licence Ouverte Etalab 2.0 (IGN)"


def _get(url: str, headers: dict | None = None, timeout: int = 120, retries: int = 8) -> bytes:
    import time
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (400, 403, 404):
                raise
            last = e
            if e.code == 429:   # the download service rate-limits; honour it
                time.sleep(float(e.headers.get("Retry-After") or 10 * (attempt + 1)))
                continue
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"LiDAR HD request failed: {last!r} ({url[:160]})")


def _l93():
    import pyproj
    fwd = pyproj.Transformer.from_crs("EPSG:4171", "EPSG:2154", always_xy=True)   # RGF93 lon/lat -> Lambert-93
    inv = pyproj.Transformer.from_crs("EPSG:2154", "EPSG:4171", always_xy=True)
    return fwd, inv


def covers(lonlat) -> bool:
    ll = np.asarray(lonlat, dtype=float)
    lo, hi = ll.min(axis=0), ll.max(axis=0)
    return COVERAGE[0] <= lo[0] and COVERAGE[1] <= lo[1] and hi[0] <= COVERAGE[2] and hi[1] <= COVERAGE[3]


def tiles(lonlat, pad_m: float = 150.0) -> list[dict]:
    """Every LiDAR HD tile within pad_m of the lap: [{name, url, polygon (Lambert-93)}]."""
    from shapely.geometry import shape
    from shapely.ops import transform
    ll = np.asarray(lonlat, dtype=float)
    fwd, _ = _l93()
    x, y = fwd.transform(ll[:, 0], ll[:, 1])
    bbox = (min(x) - pad_m, min(y) - pad_m, max(x) + pad_m, max(y) + pad_m)
    out, start = {}, 0
    while True:
        q = {"SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature", "TYPENAMES": TILE_INDEX,
             "OUTPUTFORMAT": "application/json", "COUNT": 1000, "STARTINDEX": start,
             "BBOX": ",".join(f"{v:.0f}" for v in bbox) + ",urn:ogc:def:crs:EPSG::2154"}
        fc = json.loads(_get(f"{WFS}?{urllib.parse.urlencode(q)}"))
        feats = fc.get("features", [])
        for f in feats:
            url = f["properties"].get("url_npl")
            if not url:
                continue
            name = url.rsplit("/", 1)[-1].replace(".copc.laz", "")
            g = transform(lambda a, b, z=None: fwd.transform(a, b), shape(f["geometry"]))
            out[name] = {"name": name, "url": url, "polygon": g,
                         "dataset": url.rsplit("/", 2)[-2]}
        if len(feats) < 1000:
            break
        start += 1000
    return sorted(out.values(), key=lambda t: t["name"])


def coverage(lonlat) -> float:
    """Share of the lap inside published LiDAR HD tiles."""
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    ts = tiles(lonlat, pad_m=0.0)
    if not ts:
        return 0.0
    fwd, _ = _l93()
    ll = np.asarray(lonlat, dtype=float)
    x, y = fwd.transform(ll[:, 0], ll[:, 1])
    line = LineString(np.c_[x, y])
    u = unary_union([t["polygon"] for t in ts])
    return round(u.intersection(line).length / line.length, 3)


class _RangeStream(io.RawIOBase):
    """A read/seek/tell file over HTTP range requests, with a prefetch cache."""

    def __init__(self, url: str):
        self.url, self.pos, self.cache = url, 0, {}

    def readable(self):
        return True

    def seekable(self):
        return True

    def seek(self, pos, whence=io.SEEK_SET):
        self.pos = pos if whence == io.SEEK_SET else self.pos + pos
        return self.pos

    def tell(self):
        return self.pos

    def _fetch(self, off: int, n: int) -> bytes:
        return _get(self.url, {"Range": f"bytes={off}-{off + n - 1}"})

    def prefetch(self, ranges: list[tuple[int, int]], workers: int = 4, gap: int = 256 * 1024) -> int:
        """Fetch many (offset, size) chunks: neighbours closer than `gap` bytes
        share one request (few, large requests; the service rate-limits)."""
        todo = sorted(r for r in ranges if r[0] not in self.cache)
        spans: list[list] = []
        for off, n in todo:
            if spans and off - (spans[-1][0] + spans[-1][1]) <= gap:
                spans[-1][1] = off + n - spans[-1][0]
                spans[-1][2].append((off, n))
            else:
                spans.append([off, n, [(off, n)]])
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for (s0, _, parts), body in zip(spans, ex.map(lambda sp: self._fetch(sp[0], sp[1]), spans)):
                for off, n in parts:
                    self.cache[off] = body[off - s0: off - s0 + n]
        return sum(sp[1] for sp in spans)

    def readinto(self, buf):
        body = self.read(len(buf))
        buf[:len(body)] = body
        return len(body)

    def read(self, n=-1):
        out, pos = bytearray(), self.pos
        while len(out) < n and pos in self.cache:   # serve contiguous prefetched chunks
            b = self.cache[pos]
            out += b
            pos += len(b)
        if len(out) < n:
            out += self._fetch(pos, n - len(out))
        body = bytes(out[:n])
        self.pos += len(body)
        return body


def _tile_points(tile: dict, corridor_l93, cache: Path) -> dict:
    """Corridor points of one tile (cached): columns in Lambert-93."""
    path = cache / f"{tile['name']}.npz"
    if path.exists():
        return dict(np.load(path))
    from laspy.copc import Bounds, CopcReader, load_octree_for_query
    from shapely.geometry import box
    from shapely.prepared import prep
    part = corridor_l93.intersection(tile["polygon"].buffer(1.0))
    cols = {k: np.zeros(0) for k in ("x", "y", "z", "intensity", "cls", "ret", "nret", "source")}
    if part.is_empty:
        np.savez(path, **cols)
        return cols
    st = _RangeStream(tile["url"])
    rd = CopcReader(st)
    minx, miny, maxx, maxy = part.bounds
    q = Bounds(np.array([minx, miny]), np.array([maxx, maxy])).ensure_3d(rd.header.mins, rd.header.maxs)
    nodes = load_octree_for_query(st, rd.copc_info, rd.root_page, query_bounds=q)
    pp = prep(part)
    nodes = [nd for nd in nodes if nd.byte_size > 0 and
             pp.intersects(box(nd.bounds.mins[0], nd.bounds.mins[1], nd.bounds.maxs[0], nd.bounds.maxs[1]))]
    st.prefetch([(nd.offset, nd.byte_size) for nd in nodes])
    pts = rd._fetch_and_decompress_points_of_nodes(nodes)
    x, y = np.asarray(pts.x), np.asarray(pts.y)
    from shapely import contains_xy
    keep = contains_xy(part, x, y)
    cols = {"x": x[keep], "y": y[keep], "z": np.asarray(pts.z)[keep].astype(np.float32),
            "intensity": np.asarray(pts.intensity)[keep], "cls": np.asarray(pts.classification)[keep],
            "ret": np.asarray(pts.return_number)[keep], "nret": np.asarray(pts.number_of_returns)[keep],
            "source": np.asarray(pts.point_source_id)[keep]}
    np.savez(path, **cols)
    return cols


def fetch_corridor(cache_dir: Path, corridor_merc):
    """Every LiDAR HD point in the (EPSG:3857) corridor, as lib/lidar.Points."""
    from shapely.ops import transform
    from .lidar import Points
    cache = cache_dir / NAME
    cache.mkdir(parents=True, exist_ok=True)
    fwd, inv = _l93()

    def m2l(xs, ys, z=None):
        ll = merc_to_lonlat(np.c_[np.asarray(xs), np.asarray(ys)])
        return fwd.transform(ll[:, 0], ll[:, 1])
    corr = transform(m2l, corridor_merc)
    b = merc_to_lonlat(np.array([[corridor_merc.bounds[0], corridor_merc.bounds[1]],
                                 [corridor_merc.bounds[2], corridor_merc.bounds[3]]]))
    index_path = cache / "tiles.json"
    ts = tiles(b, pad_m=0.0)
    index_path.write_text(json.dumps([{k: t[k] for k in ("name", "url", "dataset")} for t in ts], indent=1))
    ts = [t for t in ts if t["polygon"].intersects(corr)]
    parts = [_tile_points(t, corr, cache) for t in ts]
    cols = {k: np.concatenate([p[k] for p in parts]) if parts else np.zeros(0) for k in parts[0]} if parts else {}
    lon, lat = inv.transform(cols["x"], cols["y"])
    m = lonlat_to_merc(np.c_[lon, lat])
    pts = Points(x=m[:, 0], y=m[:, 1], z=cols["z"], intensity=cols["intensity"], cls=cols["cls"],
                 ret=cols["ret"], nret=cols["nret"], source=cols["source"], gps_time=np.zeros(0))
    datasets = sorted({t["dataset"] for t in ts})
    meta = {"ept": f"{WFS}?TYPENAMES={TILE_INDEX} ({', '.join(datasets)})", "nodes": len(ts),
            "points": int(len(pts.x)), "tiles": [t["name"] for t in ts]}
    return pts, meta

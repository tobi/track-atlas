"""USGS 3DEP airborne lidar access (public domain) and intensity rasters.

3DEP point clouds are a US federal product in the public domain. Their
horizontal accuracy comes from each project's GNSS/IMU trajectory and boresight
calibration; where a project states it (PROJECTS below) it is 0.5-2.5 m CE95
as a design class, and many projects state nothing. The pulses are 1064 nm
(near infrared): asphalt returns weakly, grass and painted lines strongly, so
an intensity raster of the ground returns shows the track much like NAIP's NIR
band, also under tree canopy and without shadows. At 2-8 returns per square
metre it is too coarse to trace an edge to decimetres, but ideal as an
absolute reference to register sharper imagery onto (lib/register.py).

Points are read from the Entwine Point Tile (EPT) copies on the public AWS
bucket `usgs-lidar-public` (EPSG:3857), fetching only the octree nodes that
touch a corridor around the seed centerline. Nodes are cached under
`tracks/<slug>/raw/lidar/<ept>/` (gitignored; recreatable from the recorded
request).

Datum: USGS reprojected every source project (NAD83(2011) or NAD83(HARN)) to
EPSG:3857 with PROJ's default NAD83 -> WGS 84 step, which is the identity. EPT
coordinates are therefore NAD83 lon/lat written as if they were WGS 84, exactly
like NAIP (also NAD83). `nad83_to_wgs84` applies the real NAD83(2011) ->
WGS 84 (G2139) ~ ITRF2014 shift (~1 m in the conterminous US) so the published
geometry matches what a GNSS receiver reports.
"""
from __future__ import annotations

import io
import json
import math
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .imagery import Raster, lonlat_to_merc, merc_to_lonlat
from .sources import UA

EPT_BUCKET = "https://s3-us-west-2.amazonaws.com/usgs-lidar-public"
RESOURCES_INDEX = "https://raw.githubusercontent.com/hobuinc/usgs-lidar/master/boundaries/resources.geojson"
GROUND_CLASSES = (2, 11)      # ASPRS ground, road surface
FRAME = "NAD83(2011)"         # 3DEP delivery frame; EPT reprojects to 3857 with the identity step

# Horizontal accuracy stated by each 3DEP project we use (metadata / project
# report), as CE95 metres. None: the project states none; ASSUMED_CE95_M is
# then used and the claim is marked as assumed. CE95 from per-axis RMSE is
# 2.4477 x RMSE; from radial RMSE 1.7308 x RMSEr.
ASSUMED_CE95_M = 1.0
PROJECTS: dict[str, dict] = {
    "GA_Statewide_B3_2018": {"year": 2019, "ql": "QL2", "ce95_m": None, "basis": "not stated in the project metadata"},
    "ARRA-GA_LakeLanier_2010": {"year": 2010, "ql": None, "ce95_m": None, "basis": "not stated"},
    "FL_Peninsular_Volusia_2018": {"year": 2019, "ql": "QL1", "ce95_m": 0.87, "basis": "metadata ldrchacc 0.5 m, statistic unspecified; taken as radial RMSE (x1.7308)"},
    "FL_Peninsular_FDEM_Highlands_2018": {"year": 2019, "ql": "QL1", "ce95_m": 1.0, "basis": "ASPRS 2014 41 cm RMSEx/y class = 1.0 m at 95% (design class)"},
    "CA_LosAngeles_1_B23": {"year": 2023, "ql": "QL1", "ce95_m": None, "basis": "not stated in the metadata XML"},
    "USGS_LPC_CA_LosAngeles_2016_LAS_2018": {"year": 2016, "ql": None, "ce95_m": None, "basis": "not stated"},
    "CA_FEMA_Z4_B1_2018": {"year": 2018, "ql": "QL2", "ce95_m": None, "basis": "not stated"},
    "ARRA-CA_CentralCoast-Z4_2010": {"year": 2010, "ql": None, "ce95_m": None, "basis": "not stated"},
    "NY_FingerLakes_1_2020": {"year": 2020, "ql": "QL2", "ce95_m": None, "basis": "not stated"},
    "USGS_LPC_NY_FEMA_R2_Seneca_2012_LAS_2015": {"year": 2012, "ql": None, "ce95_m": None, "basis": "not stated"},
    "CT_Statewide_B7_2016": {"year": 2016, "ql": "QL2", "ce95_m": 2.45, "basis": "designed to 1.0 m RMSEx/y (ASPRS 2014); design class, not tested"},
    "VA_South_Central_B2_2017": {"year": 2017, "ql": "QL2", "ce95_m": None, "basis": "not found"},
    "USGS_LPC_IN_Central_MarionCo_2016_LAS_2018": {"year": 2016, "ql": "QL2", "ce95_m": 1.47, "basis": "project specification 0.6 m RMSE per axis"},
    "USGS_LPC_IN_MarionCo_2011_LAS_2016": {"year": 2011, "ql": None, "ce95_m": None, "basis": "not stated"},
    "USGS_LPC_TX_Central_B1_2017_LAS_2019": {"year": 2017, "ql": "QL2", "ce95_m": 0.46, "basis": "metadata ldrchacc: RMSEx 0.189 m, RMSEy 0.186 m"},
    "WI_Oshkosh_3Rivers_B2_2018": {"year": 2019, "ql": "QL2", "ce95_m": None, "basis": "not extracted"},
}


def project_accuracy(name: str) -> tuple[float, str, bool]:
    """(CE95 m, basis, stated?) for an EPT project."""
    p = PROJECTS.get(name, {})
    if p.get("ce95_m"):
        return float(p["ce95_m"]), p["basis"], True
    return ASSUMED_CE95_M, f"assumed {ASSUMED_CE95_M:g} m CE95 ({p.get('basis', 'project not catalogued')})", False


def find_projects(lonlat_lap) -> list[tuple[str, float]]:
    """EPT projects whose boundary covers the lap: [(name, covered fraction)]."""
    from shapely.geometry import LineString, shape
    idx = json.loads(_get(RESOURCES_INDEX))["features"]
    line = LineString(np.asarray(lonlat_lap, dtype=float))
    out = []
    for f in idx:
        g = shape(f["geometry"])
        if g.intersects(line):
            out.append((f["properties"]["name"], round(g.intersection(line).length / line.length, 3)))
    return sorted(out, key=lambda t: -t[1])
CORRIDOR_M = 40.0             # lateral half-width of the fetched corridor


def _get(url: str, timeout: int = 120, retries: int = 4) -> bytes:
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                raise
            last = e
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"lidar request failed: {last!r} ({url[:160]})")


# ---------------------------------------------------------------- discovery

def ept_info(name: str) -> dict | None:
    try:
        return json.loads(_get(f"{EPT_BUCKET}/{name}/ept.json"))
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------- EPT reading

@dataclass
class Points:
    x: np.ndarray   # EPSG:3857 metres
    y: np.ndarray
    z: np.ndarray
    intensity: np.ndarray
    cls: np.ndarray
    ret: np.ndarray
    nret: np.ndarray
    source: np.ndarray
    gps_time: np.ndarray


def _hierarchy(name: str, cache: Path, bounds, touches, key: str = "0-0-0-0") -> dict[str, int]:
    """Point counts of the octree nodes whose cube `touches` accepts."""
    path = cache / "hierarchy" / f"{key}.json"
    if path.exists():
        h = json.loads(path.read_text())
    else:
        h = json.loads(_get(f"{EPT_BUCKET}/{name}/ept-hierarchy/{key}.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(h))
    out = {}
    for k, v in h.items():
        if not touches(_node_box(bounds, k)):
            continue
        if v == -1 and k != key:
            out.update(_hierarchy(name, cache, bounds, touches, k))
        else:
            out[k] = v
    return out


def _node_box(bounds, key: str):
    d, x, y, _ = (int(v) for v in key.split("-"))
    size = (bounds[3] - bounds[0]) / (2 ** d)
    x0 = bounds[0] + x * size
    y0 = bounds[1] + y * size
    return x0, y0, x0 + size, y0 + size


def fetch_corridor(name: str, cache_dir: Path, corridor_merc) -> tuple[Points, dict]:
    """Every point of EPT `name` inside the (shapely, EPSG:3857) corridor polygon."""
    import laspy
    from shapely.geometry import box
    from shapely.prepared import prep

    cache = cache_dir / name
    cache.mkdir(parents=True, exist_ok=True)
    info_path = cache / "ept.json"
    if info_path.exists():
        info = json.loads(info_path.read_text())
    else:
        info = json.loads(_get(f"{EPT_BUCKET}/{name}/ept.json"))
        info_path.write_text(json.dumps(info))
    pc = prep(corridor_merc)
    hier = _hierarchy(name, cache, info["bounds"], lambda b: pc.intersects(box(*b)))
    keys = [k for k, n in hier.items() if n > 0]

    def load(key: str) -> bytes:
        p = cache / "data" / f"{key}.laz"
        if p.exists():
            return p.read_bytes()
        body = _get(f"{EPT_BUCKET}/{name}/ept-data/{key}.laz")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)
        return body

    with ThreadPoolExecutor(max_workers=16) as ex:
        blobs = list(ex.map(load, keys))
    cols: dict[str, list] = {k: [] for k in Points.__dataclass_fields__}
    minx, miny, maxx, maxy = corridor_merc.bounds
    for body in blobs:
        las = laspy.read(io.BytesIO(body))
        x = np.asarray(las.x)
        y = np.asarray(las.y)
        keep = (x >= minx) & (x <= maxx) & (y >= miny) & (y <= maxy)
        if not keep.any():
            continue
        cols["x"].append(x[keep])
        cols["y"].append(y[keep])
        cols["z"].append(np.asarray(las.z)[keep])
        cols["intensity"].append(np.asarray(las.intensity)[keep])
        cols["cls"].append(np.asarray(las.classification)[keep])
        cols["ret"].append(np.asarray(las.return_number)[keep])
        cols["nret"].append(np.asarray(las.number_of_returns)[keep])
        cols["source"].append(np.asarray(las.point_source_id)[keep])
        cols["gps_time"].append(np.asarray(las.gps_time)[keep])
    pts = Points(**{k: np.concatenate(v) if v else np.zeros(0) for k, v in cols.items()})
    meta = {"ept": f"{EPT_BUCKET}/{name}", "nodes": len(keys), "points": int(len(pts.x))}
    return pts, meta


# ---------------------------------------------------------------- rasters

def corridor(seed_lonlat, half_width_m: float = CORRIDOR_M):
    """EPSG:3857 polygon: the seed centerline buffered by half_width (ground m)."""
    from shapely.geometry import LineString
    ll = np.asarray(seed_lonlat, dtype=float)
    k = 1.0 / math.cos(math.radians(float(ll[:, 1].mean())))
    m = lonlat_to_merc(ll)
    return LineString(np.vstack([m, m[:1]])).buffer(half_width_m * k)


def _gauss_kernel(sigma_px: float) -> np.ndarray:
    r = max(1, int(math.ceil(3 * sigma_px)))
    x = np.arange(-r, r + 1)
    k = np.exp(-0.5 * (x / sigma_px) ** 2)
    return k / k.sum()


def _blur(a: np.ndarray, sigma_px: float) -> np.ndarray:
    k = _gauss_kernel(sigma_px)
    a = np.apply_along_axis(lambda v: np.convolve(v, k, mode="same"), 0, a)
    return np.apply_along_axis(lambda v: np.convolve(v, k, mode="same"), 1, a)


def intensity_raster(pts: Points, grid: dict, sigma_m: float = 0.3) -> tuple[Raster, dict]:
    """Ground-return intensity and canopy fraction on a north-up EPSG:3857 grid.

    grid: {x0, y0, px, width, height} (the same convention as the NAIP cache).
    Intensity (last returns classified ground/road) is normalised per flight
    line (point source) to that line's median over the corridor, so strips
    flown with different gain match, then mapped to 0-255 with the corridor's
    1st-99th percentile. Cells are a Gaussian-weighted mean of the returns
    around them (normalised convolution); cells with less than half a return's
    weight nearby are NaN (no data, never guessed).
    Canopy fraction (0-255): share of all returns around the cell that are
    vegetation or not the last return. Ground under trees returns weakly, like
    asphalt; this band tells the two apart.
    The Raster bands are (intensity, canopy, 0, intensity), `kind = "lidar"`.
    """
    px, W, H = grid["px"], grid["width"], grid["height"]
    ground_m = px * math.cos(math.radians(float(merc_to_lonlat(np.array([grid["x0"], grid["y0"]]))[1])))

    def cells(x, y):
        c = np.floor((x - grid["x0"]) / px).astype(int)
        r = np.floor((grid["y0"] - y) / px).astype(int)
        ok = (c >= 0) & (c < W) & (r >= 0) & (r < H)
        return r[ok] * W + c[ok], ok

    def acc(idx, w=None):
        return np.bincount(idx, weights=w, minlength=W * H).reshape(H, W).astype(np.float32)

    g = np.isin(pts.cls, GROUND_CLASSES) & (pts.ret == pts.nret)
    inten, src = pts.intensity[g].astype(float), pts.source[g]
    norm = np.empty_like(inten)
    for s in np.unique(src):
        m = src == s
        norm[m] = inten[m] / (float(np.median(inten[m])) or 1.0)
    lo, hi = np.percentile(norm, [1, 99])
    v = np.clip((norm - lo) / (hi - lo), 0, 1) * 255.0
    idx, ok = cells(pts.x[g], pts.y[g])
    cnt = acc(idx)
    sig = sigma_m / ground_m
    wc = _blur(cnt, sig)
    img = _blur(acc(idx, v[ok]), sig) / np.maximum(wc, 1e-6)
    dem = _blur(acc(idx, pts.z[g][ok]), sig) / np.maximum(wc, 1e-6)
    nodata = wc < 0.5 * float(_gauss_kernel(sig).max() ** 2)
    img[nodata] = np.nan
    dem[nodata] = np.nan

    veg = np.isin(pts.cls, (3, 4, 5)) | (pts.ret < pts.nret)
    ia, _ = cells(pts.x, pts.y)
    iv, _ = cells(pts.x[veg], pts.y[veg])
    sc = 1.0 / ground_m
    canopy = _blur(acc(iv), sc) / np.maximum(_blur(acc(ia), sc), 1e-6) * 255.0

    density = float(cnt.sum() / (np.count_nonzero(~nodata) * ground_m ** 2)) if (~nodata).any() else 0.0
    rgb = np.stack([img, canopy.astype(np.float32), np.zeros_like(img)], axis=-1)
    R = Raster(grid["x0"], grid["y0"], px, rgb, img, "lidar", {"dem": dem})
    stats = {"ground_points": int(ok.sum()), "ground_density_per_m2": round(density, 2),
             "sources": int(len(np.unique(src)))}
    return R, stats


def grid_for(lonlat_extent, gsd_m: float = 0.5, margin_m: float = 60.0) -> dict:
    """The NAIP cache grid convention (EPSG:3857, pixel-aligned) for an extent."""
    ll = np.asarray(lonlat_extent, dtype=float)
    k = 1.0 / math.cos(math.radians(float(ll[:, 1].mean())))
    px = gsd_m * k
    m = lonlat_to_merc(ll)
    pad = margin_m * k
    x0 = math.floor((m[:, 0].min() - pad) / px) * px
    x1 = math.ceil((m[:, 0].max() + pad) / px) * px
    y0 = math.ceil((m[:, 1].max() + pad) / px) * px
    y1 = math.floor((m[:, 1].min() - pad) / px) * px
    return {"x0": x0, "y0": y0, "px": px, "width": int(round((x1 - x0) / px)),
            "height": int(round((y0 - y1) / px))}

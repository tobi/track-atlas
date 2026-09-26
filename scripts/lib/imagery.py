"""Open orthoimagery access (ArcGIS ImageServer exports) and rasters.

Only openly licensed imagery whose derived geometry can be published under
the atlas's ODbL is listed in SOURCES (public domain, CC0, or "no
restrictions"). Commercial basemaps (Esri/Google/Bing) may NOT be traced.

Imagery is fetched once per track as Web-Mercator (EPSG:3857) tiles at a fixed
ground sample distance and cached under `tracks/<slug>/raw/imagery/<source>/`
(gitignored: many MB per track; the request is fully recorded, so the cache is
recreatable). Only tiles within a corridor around the seed lap are fetched.
Two rasters per tile: natural colour (RGB) and the NIR band (when the source
has one).

Every source records its horizontal datum. The US sources are NAD83(2011)
served through PROJ's identity step as "WGS 84"; lib/datum.py moves them to
the atlas frame.
"""
from __future__ import annotations

import io
import json
import math
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

from .sources import UA

R_MERC = 6378137.0
TILE_PX = 2000

NAIP_SERVICE = "https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer"

# id -> source description. ce95_m: stated absolute horizontal accuracy (95 %),
# None when the producer states none (then the imagery is only used after
# registration to a reference). accuracy_basis says where the number comes from.
SOURCES: dict[str, dict] = {
    "naip": {
        "coverage": [-125.0, 24.4, -66.9, 49.4],  # conterminous US
        "name": "USDA NAIP via USGS The National Map", "service": NAIP_SERVICE,
        "rgb": "0,1,2", "nir": "3", "gsd_m": 0.5, "frame": "WGS84-service",
        "license": "public domain (US federal)",
        "ce95_m": 4.0, "accuracy_basis": "NAIP contract: 95% of well-defined points within 4 m (2016+); not tested per acquisition",
        "catalog": True,
    },
    "ct-2023": {
        "coverage": [-73.73, 40.95, -71.78, 42.06],  # Connecticut
        "name": "Connecticut 2023 statewide orthoimagery (CT ECO, UConn CLEAR / CT DEEP)",
        "service": "https://cteco.uconn.edu/ctraster/rest/services/images/Ortho_2023/ImageServer",
        "rgb": "0,1,2", "nir": "3", "gsd_m": 0.25, "native_gsd_m": 0.0762, "frame": "WGS84-service",
        "license": "no restrictions; acknowledgement appreciated (CT ECO metadata)",
        "ce95_m": 0.16, "accuracy_basis": "tested: RMSEx 0.072 m, RMSEy 0.060 m on 179 independent checkpoints (CT_ortho_2023_metadata.xml); CE95 = 2.4477 x RMS per axis",
        "acquisition_dates": ["2023-03-27", "2023-04-13"],
    },
    "indiana-2025": {
        "coverage": [-88.10, 37.77, -84.78, 41.77],  # Indiana
        "name": "Indiana 2025 statewide orthoimagery (IGIO / IndianaMap)",
        "service": "https://di-ingov.img.arcgis.com/arcgis/rest/services/DynamicWebMercator/Indiana_2025_Imagery/ImageServer",
        "rgb": "0,1,2", "nir": "3", "gsd_m": 0.25, "native_gsd_m": 0.0762, "frame": "WGS84-service",
        "license": "CC0 1.0 (stated in the service)",
        "ce95_m": 0.37, "accuracy_basis": "specification: ASPRS 15 cm horizontal class for the 3-inch product (1.2 ft at 95%); no tested report found",
        "acquisition_dates": ["2025"],
    },
    "txgio-2021-caparea": {
        "coverage": [-100.0, 29.4, -95.8, 31.6],  # Austin / Brazos / Kerr (approx.)
        "name": "TxGIO StratMap 2021 CapArea/Brazos/Kerr 6-inch natural colour + CIR",
        "service": "https://imagery.geographic.texas.gov/server/rest/services/StratMap/StratMap21_NCCIR_CapArea_Brazos_Kerr/ImageServer",
        "rgb": "0,1,2", "nir": "3", "gsd_m": 0.25, "native_gsd_m": 0.1524, "frame": "WGS84-service",
        "license": "CC0 1.0 (TxGIO DataHub)",
        "ce95_m": None, "accuracy_basis": "not stated by the producer",
        "acquisition_dates": ["2021-01-03"],
    },
    "fdep-2020": {
        "coverage": [-87.64, 24.4, -79.97, 31.0],  # Florida (per county; gaps)
        "name": "Florida DOR county orthoimagery 2020 (FDOT yearly aerials, served by FDEP)",
        "service": "https://ca.dep.state.fl.us/image/rest/services/FDOT_Yearly_Aerials/Aerial_Imagery_2020/ImageServer",
        "rgb": "0,1,2", "nir": "3", "gsd_m": 0.25, "native_gsd_m": 0.1524, "frame": "WGS84-service",
        "license": "Florida public record; no licence restrictions stated",
        "ce95_m": 0.75, "accuracy_basis": "specification: Florida county orthoimagery standard, RMSEx/RMSEy <= 1.0 ft for 0.5 ft imagery; no tested report found",
        "acquisition_dates": ["2019/2020 season"],
    },
    "fdep-2021": {
        "coverage": [-87.64, 24.4, -79.97, 31.0],  # Florida (per county; gaps)
        "name": "Florida DOR county orthoimagery 2021 (FDOT yearly aerials, served by FDEP)",
        "service": "https://ca.dep.state.fl.us/image/rest/services/FDOT_Yearly_Aerials/Aerial_Imagery_2021/ImageServer",
        "rgb": "0,1,2", "nir": None, "gsd_m": 0.25, "native_gsd_m": 0.1524, "frame": "WGS84-service",
        "license": "Florida public record; no licence restrictions stated",
        "ce95_m": 0.75, "accuracy_basis": "specification: Florida county orthoimagery standard (Oct 2021), RMSEx/RMSEy <= 1.0 ft for 0.5 ft imagery; no tested report found",
        "acquisition_dates": ["2021"],
    },
}


def lonlat_to_merc(lonlat) -> np.ndarray:
    a = np.asarray(lonlat, dtype=float)
    x = np.radians(a[..., 0]) * R_MERC
    y = np.log(np.tan(math.pi / 4 + np.radians(a[..., 1]) / 2)) * R_MERC
    return np.stack([x, y], axis=-1)


def merc_to_lonlat(xy) -> np.ndarray:
    a = np.asarray(xy, dtype=float)
    lon = np.degrees(a[..., 0] / R_MERC)
    lat = np.degrees(2 * np.arctan(np.exp(a[..., 1] / R_MERC)) - math.pi / 2)
    return np.stack([lon, lat], axis=-1)


def _get(url: str, timeout: int = 180, retries: int = 5) -> bytes:
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"imagery request failed: {last!r} ({url[:160]})")


def covering(lonlat) -> list[str]:
    """Imagery sources whose coverage box contains the whole lap (NAIP last)."""
    ll = np.asarray(lonlat, dtype=float)
    lo, hi = ll.min(axis=0), ll.max(axis=0)
    ids = [k for k, v in SOURCES.items()
           if v["coverage"][0] <= lo[0] and v["coverage"][1] <= lo[1] and hi[0] <= v["coverage"][2] and hi[1] <= v["coverage"][3]]
    return sorted(ids, key=lambda k: k == "naip")


def _export(service: str, bbox_merc, w: int, h: int, bands: str) -> np.ndarray:
    params = {
        "bbox": ",".join(f"{v:.3f}" for v in bbox_merc),
        "bboxSR": 3857, "imageSR": 3857, "size": f"{w},{h}",
        "format": "png", "pixelType": "U8", "bandIds": bands,
        "renderingRule": json.dumps({"rasterFunction": "None"}),
        "interpolation": "RSP_BilinearInterpolation", "f": "image",
    }
    body = _get(f"{service}/exportImage?{urllib.parse.urlencode(params)}")
    if body[:4] != b"\x89PNG":
        raise RuntimeError(f"imagery export did not return a PNG: {body[:200]!r}")
    return np.asarray(Image.open(io.BytesIO(body)))


def catalog_items(lon: float, lat: float, service: str = NAIP_SERVICE) -> list[dict]:
    """NAIP source rasters (acquisition date, GSD, state) covering a point."""
    geom = json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}})
    params = {"geometry": geom, "geometryType": "esriGeometryPoint",
              "returnCatalogItems": "true", "returnGeometry": "false", "f": "json"}
    data = json.loads(_get(f"{service}/identify?{urllib.parse.urlencode(params)}"))
    out = []
    for f in (data.get("catalogItems") or {}).get("features", []):
        a = f.get("attributes", {})
        if a.get("Category") != 1 or not a.get("raster_name"):
            continue
        out.append({
            "raster": a["raster_name"], "state": a.get("State"), "year": a.get("Year"),
            "acquisition_date": time.strftime("%Y-%m-%d", time.gmtime(a["acquisition_date"] / 1000))
            if a.get("acquisition_date") else None,
            "gsd_m": round(float(a["resolution_value"]), 2) if a.get("resolution_value") else None,
            "download_url": a.get("download_url"),
        })
    return out


@dataclass
class Raster:
    """A north-up Web-Mercator raster: rgb (H,W,3), nir (H,W).

    uint8 for imagery; float32 with NaN for no-data for derived rasters (lidar).
    kind selects the feature model in lib/edges.py: "rgbn", "rgb" or "lidar".
    """
    x0: float  # merc x of the left edge of pixel column 0
    y0: float  # merc y of the top edge of pixel row 0
    px: float  # merc metres per pixel
    rgb: np.ndarray
    nir: np.ndarray
    kind: str = "rgbn"
    extra: dict = field(default_factory=dict)

    def sample(self, lonlat) -> np.ndarray:
        """Bilinear (R,G,B,NIR) float32 samples at lon/lat points; NaN outside."""
        m = lonlat_to_merc(lonlat)
        c = (m[..., 0] - self.x0) / self.px - 0.5
        r = (self.y0 - m[..., 1]) / self.px - 0.5
        h, w = self.nir.shape
        inside = (c >= 0) & (r >= 0) & (c <= w - 2) & (r <= h - 2)
        c = np.clip(c, 0, w - 2)
        r = np.clip(r, 0, h - 2)
        c0 = np.floor(c).astype(np.intp)
        r0 = np.floor(r).astype(np.intp)
        fc = (c - c0).astype(np.float32)
        fr = (r - r0).astype(np.float32)
        out = np.empty(c.shape + (4,), dtype=np.float32)
        bands = [self.rgb[..., 0], self.rgb[..., 1], self.rgb[..., 2], self.nir]
        for k, B in enumerate(bands):
            out[..., k] = (B[r0, c0] * (1 - fc) * (1 - fr) + B[r0, c0 + 1] * fc * (1 - fr)
                           + B[r0 + 1, c0] * (1 - fc) * fr + B[r0 + 1, c0 + 1] * fc * fr)
        out[~inside] = np.nan
        return out


def _grid(ll: np.ndarray, gsd_m: float, margin_m: float) -> dict:
    lat_c = float(ll[:, 1].mean())
    k = 1.0 / math.cos(math.radians(lat_c))  # mercator metres per ground metre
    px = gsd_m * k
    m = lonlat_to_merc(ll)
    pad = margin_m * k
    x0 = math.floor((m[:, 0].min() - pad) / px) * px
    x1 = math.ceil((m[:, 0].max() + pad) / px) * px
    y0 = math.ceil((m[:, 1].max() + pad) / px) * px
    y1 = math.floor((m[:, 1].min() - pad) / px) * px
    return {"x0": x0, "y0": y0, "px": px, "gsd_m": gsd_m,
            "width": int(round((x1 - x0) / px)), "height": int(round((y0 - y1) / px))}


def fetch_imagery(cache_dir: Path, lonlat_extent, source: str = "naip", margin_m: float = 60.0,
                  corridor_m: float = 120.0) -> dict:
    """Fetch (or reuse cached) imagery over the lap. Returns the manifest.

    Only tiles within corridor_m of the lap are requested; the rest of the
    grid stays empty (zero), which the edge search treats as no data.
    """
    src = SOURCES[source]
    cache_dir.mkdir(parents=True, exist_ok=True)
    ll = np.asarray(lonlat_extent, dtype=float)
    g = _grid(ll, src["gsd_m"], margin_m)
    x0, y0, px, W, H = g["x0"], g["y0"], g["px"], g["width"], g["height"]
    manifest = {"source": source, "service": src["service"], "crs": "EPSG:3857", **g,
                "tile_px": TILE_PX, "tiles": []}
    mpath = cache_dir / "manifest.json"
    if mpath.exists():
        old = json.loads(mpath.read_text())
        same = all(abs(old.get(k2, 0) - manifest[k2]) < 1e-6 for k2 in ("x0", "y0", "px")) \
            and (old.get("width"), old.get("height")) == (W, H)
        if same and all((cache_dir / t["rgb"]).exists() for t in old["tiles"]):
            return old
    from shapely.geometry import LineString, box
    k = 1.0 / math.cos(math.radians(float(ll[:, 1].mean())))
    m = lonlat_to_merc(ll)
    near = LineString(np.vstack([m, m[:1]])).buffer(corridor_m * k)
    for ty in range(0, H, TILE_PX):
        for tx in range(0, W, TILE_PX):
            w = min(TILE_PX, W - tx)
            h = min(TILE_PX, H - ty)
            bb = (x0 + tx * px, y0 - (ty + h) * px, x0 + (tx + w) * px, y0 - ty * px)
            if not near.intersects(box(*bb)):
                continue
            rgb = _export(src["service"], bb, w, h, src["rgb"])
            if rgb.ndim == 3 and rgb.shape[2] == 4:
                rgb = rgb[..., :3]
            name = f"tile_{ty:05d}_{tx:05d}"
            Image.fromarray(rgb).save(cache_dir / f"{name}.rgb.png")
            tile = {"row": ty, "col": tx, "w": w, "h": h, "rgb": f"{name}.rgb.png"}
            if src.get("nir"):
                nir = _export(src["service"], bb, w, h, src["nir"])
                if nir.ndim == 3:
                    nir = nir[..., 0]
                Image.fromarray(nir).save(cache_dir / f"{name}.nir.png")
                tile["nir"] = f"{name}.nir.png"
            manifest["tiles"].append(tile)
    if src.get("catalog"):
        # record every NAIP source raster the lap crosses (acquisition dates)
        seen: dict[str, dict] = {}
        for i in np.linspace(0, len(ll) - 1, 12).astype(int):
            for item in catalog_items(float(ll[i, 0]), float(ll[i, 1]), src["service"]):
                seen.setdefault(item["raster"], item)
        manifest["catalog"] = sorted(seen.values(), key=lambda d: d["raster"])
    manifest["fetched_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    mpath.write_text(json.dumps(manifest, indent=2))
    return manifest


def fetch_naip(cache_dir: Path, lonlat_extent, gsd_m: float = 0.5, margin_m: float = 60.0) -> dict:
    return fetch_imagery(cache_dir, lonlat_extent, "naip", margin_m)


def load_raster(cache_dir: Path) -> tuple[Raster, dict]:
    man = json.loads((cache_dir / "manifest.json").read_text())
    rgb = np.zeros((man["height"], man["width"], 3), dtype=np.uint8)
    nir = np.zeros((man["height"], man["width"]), dtype=np.uint8)
    has_nir = True
    for t in man["tiles"]:
        r, c, w, h = t["row"], t["col"], t["w"], t["h"]
        a = np.asarray(Image.open(cache_dir / t["rgb"]))
        rgb[r:r + h, c:c + w] = a[..., :3] if a.ndim == 3 else a[..., None]
        if t.get("nir"):
            b = np.asarray(Image.open(cache_dir / t["nir"]))
            nir[r:r + h, c:c + w] = b if b.ndim == 2 else b[..., 0]
        else:
            has_nir = False
    if not has_nir:
        # no NIR band: the brightness stands in (the "rgb" feature model ignores it)
        nir = rgb.mean(axis=-1).astype(np.uint8)
    return Raster(man["x0"], man["y0"], man["px"], rgb, nir, "rgbn" if has_nir else "rgb"), man

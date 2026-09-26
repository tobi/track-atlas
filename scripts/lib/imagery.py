"""Public-domain orthoimagery access (USDA NAIP via the USGS National Map).

NAIP is a US federal product in the public domain, so geometry measured from it
can be published under the atlas's ODbL without licence conflict. (Commercial
basemaps such as Esri/Google/Bing may NOT be traced for this dataset.)

Imagery is fetched once per track as Web-Mercator (EPSG:3857) tiles at a fixed
ground sample distance and cached under `tracks/<slug>/raw/imagery/`
(gitignored: several MB per track; the request is fully recorded, so the cache
is recreatable). Two rasters per tile: natural colour (RGB) and the NIR band.
"""
from __future__ import annotations

import io
import json
import math
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from .sources import UA

NAIP_SERVICE = "https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer"
R_MERC = 6378137.0
TILE_PX = 2000


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


def _get(url: str, timeout: int = 120, retries: int = 5) -> bytes:
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


def _export(bbox_merc, w: int, h: int, bands: str) -> np.ndarray:
    params = {
        "bbox": ",".join(f"{v:.3f}" for v in bbox_merc),
        "bboxSR": 3857, "imageSR": 3857, "size": f"{w},{h}",
        "format": "png", "pixelType": "U8", "bandIds": bands,
        "renderingRule": json.dumps({"rasterFunction": "None"}),
        "interpolation": "RSP_BilinearInterpolation", "f": "image",
    }
    body = _get(f"{NAIP_SERVICE}/exportImage?{urllib.parse.urlencode(params)}")
    if body[:4] != b"\x89PNG":
        raise RuntimeError(f"NAIP export did not return a PNG: {body[:200]!r}")
    return np.asarray(Image.open(io.BytesIO(body)))


def catalog_items(lon: float, lat: float) -> list[dict]:
    """NAIP source rasters (acquisition date, GSD, state) covering a point."""
    geom = json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}})
    params = {"geometry": geom, "geometryType": "esriGeometryPoint",
              "returnCatalogItems": "true", "returnGeometry": "false", "f": "json"}
    data = json.loads(_get(f"{NAIP_SERVICE}/identify?{urllib.parse.urlencode(params)}"))
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
    """A north-up Web-Mercator raster: rgb (H,W,3), nir (H,W) uint8."""
    x0: float  # merc x of the left edge of pixel column 0
    y0: float  # merc y of the top edge of pixel row 0
    px: float  # merc metres per pixel
    rgb: np.ndarray
    nir: np.ndarray

    def sample(self, lonlat) -> np.ndarray:
        """Bilinear (R,G,B,NIR) float samples at lon/lat points; NaN outside."""
        m = lonlat_to_merc(lonlat)
        c = (m[..., 0] - self.x0) / self.px - 0.5
        r = (self.y0 - m[..., 1]) / self.px - 0.5
        h, w = self.nir.shape
        inside = (c >= 0) & (r >= 0) & (c <= w - 2) & (r <= h - 2)
        c = np.clip(c, 0, w - 2)
        r = np.clip(r, 0, h - 2)
        c0 = np.floor(c).astype(int)
        r0 = np.floor(r).astype(int)
        fc = (c - c0)[..., None]
        fr = (r - r0)[..., None]
        stack = np.concatenate([self.rgb, self.nir[..., None]], axis=-1).astype(np.float32) \
            if not hasattr(self, "_stack") else self._stack
        self._stack = stack
        v = (stack[r0, c0] * (1 - fc) * (1 - fr) + stack[r0, c0 + 1] * fc * (1 - fr)
             + stack[r0 + 1, c0] * (1 - fc) * fr + stack[r0 + 1, c0 + 1] * fc * fr)
        v[~inside] = np.nan
        return v


def fetch_naip(cache_dir: Path, lonlat_extent, gsd_m: float = 0.5, margin_m: float = 60.0) -> dict:
    """Fetch (or reuse cached) NAIP over the lon/lat extent. Returns the manifest."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    ll = np.asarray(lonlat_extent, dtype=float)
    lat_c = float(ll[:, 1].mean())
    k = 1.0 / math.cos(math.radians(lat_c))  # mercator metres per ground metre
    px = gsd_m * k
    m = lonlat_to_merc(ll)
    pad = margin_m * k
    x0 = math.floor((m[:, 0].min() - pad) / px) * px
    x1 = math.ceil((m[:, 0].max() + pad) / px) * px
    y0 = math.ceil((m[:, 1].max() + pad) / px) * px
    y1 = math.floor((m[:, 1].min() - pad) / px) * px
    W = int(round((x1 - x0) / px))
    H = int(round((y0 - y1) / px))
    manifest = {"service": NAIP_SERVICE, "crs": "EPSG:3857", "x0": x0, "y0": y0, "px": px,
                "gsd_m": gsd_m, "width": W, "height": H, "tile_px": TILE_PX, "tiles": []}
    mpath = cache_dir / "manifest.json"
    if mpath.exists():
        old = json.loads(mpath.read_text())
        same = all(abs(old.get(k2, 0) - manifest[k2]) < 1e-6 for k2 in ("x0", "y0", "px")) \
            and (old.get("width"), old.get("height")) == (W, H)
        if same and all((cache_dir / t["rgb"]).exists() for t in old["tiles"]):
            return old
    for ty in range(0, H, TILE_PX):
        for tx in range(0, W, TILE_PX):
            w = min(TILE_PX, W - tx)
            h = min(TILE_PX, H - ty)
            bb = (x0 + tx * px, y0 - (ty + h) * px, x0 + (tx + w) * px, y0 - ty * px)
            rgb = _export(bb, w, h, "0,1,2")
            nir = _export(bb, w, h, "3")
            if rgb.ndim == 3 and rgb.shape[2] == 4:
                rgb = rgb[..., :3]
            if nir.ndim == 3:
                nir = nir[..., 0]
            name = f"tile_{ty:05d}_{tx:05d}"
            Image.fromarray(rgb).save(cache_dir / f"{name}.rgb.png")
            Image.fromarray(nir).save(cache_dir / f"{name}.nir.png")
            manifest["tiles"].append({"row": ty, "col": tx, "w": w, "h": h,
                                      "rgb": f"{name}.rgb.png", "nir": f"{name}.nir.png"})
    # record every NAIP source raster the lap crosses (acquisition dates)
    seen: dict[str, dict] = {}
    for i in np.linspace(0, len(ll) - 1, 12).astype(int):
        for item in catalog_items(float(ll[i, 0]), float(ll[i, 1])):
            seen.setdefault(item["raster"], item)
    manifest["catalog"] = sorted(seen.values(), key=lambda d: d["raster"])
    manifest["fetched_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    mpath.write_text(json.dumps(manifest, indent=2))
    return manifest


def load_raster(cache_dir: Path) -> tuple[Raster, dict]:
    man = json.loads((cache_dir / "manifest.json").read_text())
    rgb = np.zeros((man["height"], man["width"], 3), dtype=np.uint8)
    nir = np.zeros((man["height"], man["width"]), dtype=np.uint8)
    for t in man["tiles"]:
        r, c, w, h = t["row"], t["col"], t["w"], t["h"]
        a = np.asarray(Image.open(cache_dir / t["rgb"]))
        rgb[r:r + h, c:c + w] = a[..., :3] if a.ndim == 3 else a[..., None]
        b = np.asarray(Image.open(cache_dir / t["nir"]))
        nir[r:r + h, c:c + w] = b if b.ndim == 2 else b[..., 0]
    return Raster(man["x0"], man["y0"], man["px"], rgb, nir), man

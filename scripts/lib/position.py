"""Absolute position of a surface measurement: reference, registration, datum.

The edges are traced in the imagery's own frame (lib/edges.py). This module
decides where that frame really is and what the result's absolute accuracy is:

1. Reference. The imagery's stated accuracy (lib/imagery.SOURCES) is compared
   with each lidar reference's (lib/lidar.PROJECTS, or the assumed default).
   The sharper stated one is the reference.
2. Registration. The imagery is correlated against every lidar reference
   (lib/register.py). If a lidar project is the reference, its shift is
   applied; otherwise the shifts are only checks. With two lidar references
   their difference is an independent check of the references themselves.
3. Datum. The reference's frame is moved to the atlas frame (lib/datum.py):
   NAD83(2011) for 3DEP lidar, "WGS84-service" for imagery served in Web
   Mercator.

Error budget (95 %, horizontal): hypot(reference CE95, registration CE95,
datum step CE95). The window shifts scatter around the applied (mean) shift
for two reasons: estimator noise, and real non-rigid distortion of the imagery
(which a single shift leaves in place). Registration CE95 covers the
non-rigid part plus the standard error of the mean. With one lidar reference
the two cannot be told apart and the whole scatter counts (conservative). With
two, the per-window difference of the two registrations cancels the imagery's
distortion (common to both) and measures the noise alone:
noise^2 = var(diff) / 2, non-rigid^2 = scatter^2 - noise^2.
The relative precision of the edges (lib/edges.py) is combined per feature
downstream.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from . import datum, lidar, register
from .imagery import SOURCES, Raster

REG_GSD_M = 0.5            # registration grid
REF_CORRIDOR_M = 110.0     # lidar fetched around the lap for registration


def _ce95(sd_e: float, sd_n: float) -> float:
    return 2.4477 * math.sqrt((sd_e ** 2 + sd_n ** 2) / 2.0)


def _pseudo_nir(rgb: np.ndarray) -> np.ndarray:
    """RGB-only imagery: brightness plus excess green, so grass reads bright
    and asphalt dark, as in the NIR band and in lidar intensity."""
    r, g, b = (rgb[..., k].astype(np.float32) for k in range(3))
    return np.clip((r + g + b) / 3.0 + 1.5 * (2 * g - r - b), 0, 255)


def _resample(image: Raster, grid: dict) -> Raster:
    """The image's NIR (or pseudo-NIR) on the registration grid."""
    from .imagery import merc_to_lonlat
    H, W = grid["height"], grid["width"]
    xs = grid["x0"] + (np.arange(W) + 0.5) * grid["px"]
    ys = grid["y0"] - (np.arange(H) + 0.5) * grid["px"]
    out = np.zeros((H, W), dtype=np.float32)
    for r0 in range(0, H, 512):
        yy = ys[r0:r0 + 512]
        m = np.stack(np.meshgrid(xs, yy), axis=-1)
        S = image.sample(merc_to_lonlat(m))
        v = S[..., 3] if image.kind == "rgbn" else _pseudo_nir(S[..., :3])
        out[r0:r0 + len(yy)] = np.nan_to_num(v)
    rgb = np.repeat(out[..., None], 3, axis=-1)
    return Raster(grid["x0"], grid["y0"], grid["px"], rgb, out)


def _window_noise(usable: list[dict]) -> tuple[float, float] | None:
    """Per-axis estimator noise (1 sigma) from two registrations' window pairs."""
    if len(usable) < 2:
        return None
    a, b = usable[0]["registration"].windows, usable[1]["registration"].windows
    d = [np.subtract(wa["shift_m"], wb["shift_m"]) for wa, wb in zip(a, b)
         if wa["kept"] and wb["kept"] and wa["centre"] == wb["centre"]]
    if len(d) < 5:
        return None
    d = np.asarray(d)
    return tuple(float(v) for v in 1.4826 * np.median(np.abs(d - np.median(d, axis=0)), axis=0) / math.sqrt(2))


def _infer_frame(default: str, usable: list[dict], lon: float, lat: float,
                 hypotheses=("WGS84-service", "NAD83(2011)")) -> tuple[str, str]:
    """Which frame an imagery service really delivers, from the lidar registrations.

    Services convert the producer's NAD83(2011) to Web Mercator either with a
    real NAD83 -> WGS 84 transformation (NAIP, CT) or with the identity step
    (Indiana). The two hypotheses are ~1 m apart; the lidar (NAD83(2011)) says
    which one the imagery matches: under the identity hypothesis the imagery
    registers onto the lidar with ~zero shift, under the transformed one with
    about minus the NAD83 -> ITRF2014 step.
    """
    if not usable:
        return default, "catalog default (no lidar to test it)"
    res = {}
    for f in hypotheses:
        d = datum.shift_m(lon, lat, f)
        res[f] = float(np.mean([math.hypot(r["registration"].de + r["shift"][0] - d[0],
                                           r["registration"].dn + r["shift"][1] - d[1]) for r in usable]))
    best = min(res, key=res.get)
    txt = ", ".join(f"{k} {v:.2f} m" for k, v in res.items())
    return best, f"inferred from registration to {len(usable)} lidar survey(s): mean residual {txt}"


def locate(image: Raster, source_id: str, lap_lonlat, lidar_projects: list[str], cache_dir: Path) -> dict:
    """Registration, datum and error budget for a measurement.

    Returns {"shift_m": (east, north) to add to image-frame coordinates, ...}.
    """
    src = SOURCES[source_id]
    ll = np.asarray(lap_lonlat, dtype=float)
    lon_c, lat_c = float(ll[:, 0].mean()), float(ll[:, 1].mean())
    grid = lidar.grid_for(ll, REG_GSD_M)
    img = _resample(image, grid) if lidar_projects else None
    refs = []
    for name in lidar_projects:
        pts, meta = lidar.fetch_corridor(name, cache_dir, lidar.corridor(ll, REF_CORRIDOR_M))
        L, stats = lidar.intensity_raster(pts, grid, sigma_m=0.6)
        reg = register.register(img, L, ll, REG_GSD_M)
        ce95, basis, stated = lidar.project_accuracy(name)
        refs.append({"name": name, "ce95_m": ce95, "basis": basis, "stated": stated,
                     "ept": meta["ept"], "points": meta["points"], **stats,
                     "year": lidar.PROJECTS.get(name, {}).get("year"),
                     "frame": lidar.project_frame(name),
                     "shift": datum.shift_m(lon_c, lat_c, lidar.project_frame(name)),
                     "registration": reg})

    usable = [r for r in refs if r["registration"] is not None]
    img_ce95 = src.get("ce95_m")
    best_lidar = min(usable, key=lambda r: (not r["stated"], r["ce95_m"])) if usable else None
    noise = _window_noise(usable)
    frame_basis = None
    if best_lidar and (img_ce95 is None or best_lidar["ce95_m"] < img_ce95):
        reg = best_lidar["registration"]
        shift = (reg.de, reg.dn)
        reference = {"kind": "lidar", "name": best_lidar["name"], "ce95_m": best_lidar["ce95_m"],
                     "basis": best_lidar["basis"], "stated": best_lidar["stated"]}
        if noise is None:
            nr_e, nr_n = reg.sd_e, reg.sd_n
        else:
            nr_e = math.sqrt(max(reg.sd_e ** 2 - noise[0] ** 2, 0.0))
            nr_n = math.sqrt(max(reg.sd_n ** 2 - noise[1] ** 2, 0.0))
        reg_ce95 = math.hypot(_ce95(nr_e, nr_n), 2.4477 * reg.se / math.sqrt(2))
        frame = best_lidar["frame"]
    elif img_ce95 is not None:
        shift = (0.0, 0.0)
        reference = {"kind": "imagery", "name": source_id, "ce95_m": img_ce95,
                     "basis": src["accuracy_basis"], "stated": True}
        reg_ce95 = 0.0
        frame, frame_basis = _infer_frame(src["frame"], usable, lon_c, lat_c,
                                          src.get("frame_hypotheses", ("WGS84-service", "NAD83(2011)")))
    else:
        raise RuntimeError(f"{source_id}: no stated accuracy and no lidar reference registered")

    d_e, d_n = datum.shift_m(lon_c, lat_c, frame)
    d_ce95 = datum.step_ce95_m(lon_c, frame, lat_c)
    total = math.sqrt(reference["ce95_m"] ** 2 + reg_ce95 ** 2 + d_ce95 ** 2)

    checks = []
    for r in refs:
        g = r["registration"]
        c = {"reference": r["name"], "year": r["year"], "reference_ce95_m": r["ce95_m"],
             "reference_basis": r["basis"], "ground_density_per_m2": r["ground_density_per_m2"]}
        if g is None:
            c["result"] = "no reliable registration"
        else:
            c.update(g.summary())
            # where this reference would put the geometry (its registration plus
            # its own datum step), relative to where it was put
            c["residual_vs_applied_m"] = round(math.hypot(g.de + r["shift"][0] - shift[0] - d_e,
                                                          g.dn + r["shift"][1] - shift[1] - d_n), 3)
        checks.append(c)
    if len(usable) >= 2:
        a, b = usable[0]["registration"], usable[1]["registration"]
        checks.append({"reference_agreement": [usable[0]["name"], usable[1]["name"]],
                       "difference_m": round(math.hypot(a.de - b.de, a.dn - b.dn), 3),
                       "note": "independent lidar surveys; their difference bounds both references' errors"})

    return {
        "shift_m": (shift[0] + d_e, shift[1] + d_n),
        "summary": {
            "frame": datum.ATLAS_FRAME, "epoch": datum.ATLAS_EPOCH,
            "source_frame": frame,
            "imagery_frame": frame if reference["kind"] == "imagery" else src["frame"],
            "imagery_frame_basis": frame_basis,
            "datum_shift_m": {"east": round(d_e, 3), "north": round(d_n, 3)},
            "registration_shift_m": {"east": round(shift[0], 3), "north": round(shift[1], 3)},
            "applied_shift_m": {"east": round(shift[0] + d_e, 3), "north": round(shift[1] + d_n, 3)},
            "reference": reference,
            "budget_ce95_m": {"reference": round(reference["ce95_m"], 3),
                              "registration": round(reg_ce95, 3), "datum": round(d_ce95, 3),
                              "total": round(total, 3)},
            "imagery_stated_ce95_m": img_ce95,
            "registration_model": ("window scatter split into estimator noise "
                                   f"({noise[0]:.2f}/{noise[1]:.2f} m E/N, from two lidar surveys) and non-rigid distortion"
                                   if noise else "whole window scatter counted (single lidar reference)")
            if reference["kind"] == "lidar" else "not applied (imagery is the reference)",
            "checks": checks,
        },
        "ce95_m": total,
    }

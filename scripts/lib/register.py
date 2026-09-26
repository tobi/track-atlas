"""Co-registration of orthoimagery to a lidar intensity reference.

Orthoimagery (NAIP, 4 m CE95 contract) has excellent relative geometry but a
loose absolute position; airborne lidar has a sub-metre absolute position but
too few returns per square metre to trace a sharp edge. Both see the track in
the near infrared (NAIP band 4, lidar pulses at 1064 nm): asphalt dark, grass
and paint bright. So the imagery is shifted onto the lidar.

Method: windows (WIN_M square) centred on the lap every STEP_M metres. In each,
normalised cross-correlation between the image's NIR and the lidar intensity
over integer pixel shifts within +/- MAX_SHIFT_M, excluding lidar no-data and
canopy (the image sees the treetop, the lidar the ground below it), then a
parabolic sub-pixel refinement of the peak. A window is kept when its peak is
distinct (peak NCC >= MIN_NCC and clearly above the best shift outside
PEAK_EXCL_M). The shift field is the robust (Tukey) weighted mean of the kept
windows' shifts, smoothed along the lap; with fewer than MIN_WINDOWS kept
windows no registration is claimed.
"""
from __future__ import annotations

import collections
import math
from dataclasses import dataclass

import numpy as np

from .imagery import Raster, lonlat_to_merc

WIN_M = 120.0
STEP_M = 100.0
MAX_SHIFT_M = 8.0
MIN_NCC = 0.12
PEAK_EXCL_M = 2.0
MIN_WINDOWS = 6
CANOPY_MAX = 0.25       # canopy fraction above which a pixel is excluded
DEBUG = False
HIGHPASS_M = 3.0


@dataclass
class Registration:
    """Shift (ground metres, east/north) to ADD to image coordinates."""
    de: float
    dn: float
    sd_e: float           # robust spread of the window shifts
    sd_n: float
    se: float             # standard error of the mean shift (horizontal, 1 sigma)
    windows: list[dict]   # every window: centre, shift, ncc, kept
    n_kept: int

    def summary(self) -> dict:
        return {"shift_m": {"east": round(self.de, 3), "north": round(self.dn, 3)},
                "window_spread_m": {"east": round(self.sd_e, 3), "north": round(self.sd_n, 3)},
                "standard_error_m": round(self.se, 3),
                "windows": {"kept": self.n_kept, "total": len(self.windows)}}


def _ncc_surface(a: np.ndarray, b: np.ndarray, mask_b: np.ndarray, r: int) -> np.ndarray:
    """NCC of a (larger, padded by r) against b for every shift in [-r, r]^2.

    a: (h+2r, w+2r) image, b: (h, w) reference, mask_b: valid reference pixels.
    Entry [r+dy, r+dx] compares b with a shifted by (dy, dx) pixels.
    """
    h, w = b.shape
    m = mask_b.astype(np.float64)
    n = m.sum()
    bz = np.where(mask_b, b - (b * m).sum() / n, 0.0)
    bn = math.sqrt((bz ** 2).sum()) or 1.0
    out = np.full((2 * r + 1, 2 * r + 1), -1.0)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            aa = a[r + dy:r + dy + h, r + dx:r + dx + w]
            am = (aa * m).sum() / n
            az = np.where(mask_b, aa - am, 0.0)
            an = math.sqrt((az ** 2).sum()) or 1.0
            out[r + dy, r + dx] = (az * bz).sum() / (an * bn)
    return out


def _highpass(a: np.ndarray, valid: np.ndarray, sigma_px: float) -> np.ndarray:
    """a minus its (normalised, valid-only) Gaussian blur; 0 where invalid."""
    from .lidar import _blur
    v = valid.astype(np.float32)
    low = _blur(np.where(valid, a, 0).astype(np.float32), sigma_px) / np.maximum(_blur(v, sigma_px), 1e-6)
    return np.where(valid, a - low, 0.0)


def _subpixel(s: np.ndarray, i: int, j: int) -> tuple[float, float]:
    def par(m1, c, p1):
        d = m1 - 2 * c + p1
        return 0.0 if d >= 0 else 0.5 * (m1 - p1) / d
    di = par(s[i - 1, j], s[i, j], s[i + 1, j]) if 0 < i < s.shape[0] - 1 else 0.0
    dj = par(s[i, j - 1], s[i, j], s[i, j + 1]) if 0 < j < s.shape[1] - 1 else 0.0
    return i + di, j + dj


def register(image: Raster, ref: Raster, lap_lonlat, ground_m_per_px: float) -> Registration | None:
    """Estimate the shift that moves `image` onto the lidar `ref` (same grid)."""
    assert image.nir.shape == ref.nir.shape and abs(image.px - ref.px) < 1e-9
    canopy = ref.rgb[..., 1].astype(np.float64) / 255.0
    valid = np.isfinite(ref.nir) & (canopy < CANOPY_MAX)
    # correlate structure, not brightness: both high-passed at HIGHPASS_M
    img = _highpass(image.nir.astype(np.float64), np.ones(image.nir.shape, bool), HIGHPASS_M / ground_m_per_px)
    lid = _highpass(np.nan_to_num(ref.nir.astype(np.float64)), np.isfinite(ref.nir), HIGHPASS_M / ground_m_per_px)
    H, W = img.shape
    half = int(WIN_M / 2 / ground_m_per_px)
    r = int(math.ceil(MAX_SHIFT_M / ground_m_per_px))
    excl = PEAK_EXCL_M / ground_m_per_px

    ll = np.asarray(lap_lonlat, dtype=float)
    m = lonlat_to_merc(ll)
    seg = np.hypot(*np.diff(m, axis=0).T) * ground_m_per_px / image.px
    cum = np.concatenate([[0], np.cumsum(seg)])
    centres = [m[int(np.searchsorted(cum, s))] for s in np.arange(STEP_M / 2, cum[-1], STEP_M)]

    windows = []
    for cm in centres:
        c = int((cm[0] - image.x0) / image.px)
        rr = int((image.y0 - cm[1]) / image.px)
        if rr - half - r < 0 or c - half - r < 0 or rr + half + r >= H or c + half + r >= W:
            continue
        b = lid[rr - half:rr + half, c - half:c + half]
        mb = valid[rr - half:rr + half, c - half:c + half]
        a = img[rr - half - r:rr + half + r, c - half - r:c + half + r]
        win = {"centre": [round(float(v), 7) for v in _merc_to_ll(cm)], "kept": False}
        windows.append(win)
        if mb.mean() < 0.3:
            win["reason"] = "reference coverage"
            continue
        s = _ncc_surface(a, b, mb, r)
        i, j = np.unravel_index(int(np.argmax(s)), s.shape)
        peak = float(s[i, j])
        yy, xx = np.mgrid[:s.shape[0], :s.shape[1]]
        far = np.hypot(yy - i, xx - j) > excl
        second = float(s[far].max()) if far.any() else -1.0
        fi, fj = _subpixel(s, i, j)
        # the image content at reference pixel p is found at p + (dy, dx) in
        # the image, so the image must move by -(dx, +dy) in east/north
        de = -(fj - r) * ground_m_per_px
        dn = (fi - r) * ground_m_per_px
        win.update({"shift_m": [round(de, 3), round(dn, 3)], "ncc": round(peak, 3),
                    "second": round(second, 3)})
        if peak < MIN_NCC:
            win["reason"] = "weak correlation"
        elif peak - second < 0.01:
            win["reason"] = "ambiguous peak"
        elif not (i in (0, s.shape[0] - 1) or j in (0, s.shape[1] - 1)):
            win["kept"] = True
        else:
            win["reason"] = "shift at search limit"
    kept = [w for w in windows if w["kept"]]
    if DEBUG:
        print(collections.Counter(w.get("reason", "kept") for w in windows))
        for w in windows:
            print(w)
    if len(kept) < MIN_WINDOWS:
        return None
    S = np.array([w["shift_m"] for w in kept])
    wt = np.ones(len(S))
    mu = np.median(S, axis=0)
    for _ in range(10):
        d = np.hypot(*(S - mu).T)
        sc = max(1.4826 * np.median(d), 0.05)
        u = d / (4.685 * sc)
        wt = np.where(u < 1, (1 - u ** 2) ** 2, 0.0)
        mu = (S * wt[:, None]).sum(0) / wt.sum()
    good = wt > 0
    for w, g in zip(kept, good):
        if not g:
            w["kept"] = False
            w["reason"] = "outlier shift"
    sd = 1.4826 * np.median(np.abs(S[good] - mu), axis=0)
    n_eff = float(good.sum())
    se = float(math.hypot(*sd) / math.sqrt(max(n_eff, 1)))
    return Registration(float(mu[0]), float(mu[1]), float(sd[0]), float(sd[1]), se, windows, int(good.sum()))


def _merc_to_ll(m):
    from .imagery import merc_to_lonlat
    return merc_to_lonlat(np.asarray(m))

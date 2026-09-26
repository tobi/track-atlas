"""Measure a circuit's left/right track edges from orthoimagery.

The algorithm (documented in docs/GEOMETRY.md):

1. Resample the seed centerline (OSM) at 1 m, smooth it (sigma 4 m) and take
   left normals. Sample the imagery on a straightened grid: station s x
   lateral offset t (0.25 m steps, +/- 26 m), bilinear in RGB + NIR.
2. Self-calibrating asphalt model: samples within 1.5 m of the seed line are
   (mostly) the racing surface; samples 16-26 m out are (mostly) not. Each
   sample gets a log-likelihood ratio over robust (median/MAD) diagonal models
   of chroma (max-min RGB), NDVI and brightness, squashed to p(asphalt).
3. Edge evidence per side: mean p(asphalt) over the 1.5 m inside the candidate
   offset minus the 1.5 m outside it, plus a painted-line bonus (a narrow,
   neutral bright ridge, i.e. the white track-limit line).
4. A dynamic-programming optimal path per side through (s, t): max total
   evidence, lateral change <= 0.5 m per metre of lap with a linear penalty,
   and a soft width prior. The closed lap is solved by unrolling it three times
   and keeping the middle copy. On the inside of tight corners the search stops
   at 85 % of the local radius (normals cross beyond it).
5. Recentre: the midline of the two edges replaces the seed and steps 1-4 run
   again, so a seed that is metres off the asphalt (TIGER-traced OSM ways are)
   is corrected.
6. Robust smoothing: each half-width is smoothed by iteratively reweighted
   Gaussian smoothing (Tukey weights) over the seen stations. Stations whose
   contrast is weak or whose outside window is in shadow are "not seen" and
   bridged linearly from their neighbours; their spans are reported, never
   hidden. Precision is the robust spread of the raw path against the fit.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import geo
from .imagery import Raster

STEP_S = 1.0          # m between stations
STEP_T = 0.25         # m between lateral samples
T_MAX = 26.0          # m lateral search half-width
SEED_SIGMA = 4.0      # m, smoothing of the seed line before taking normals
EDGE_WIN = 1.5        # m, inside/outside averaging window for the edge step
MIN_HALF = 2.5        # m, soft minimum distance centre -> edge
MAX_HALF = 16.0       # m, soft maximum distance centre -> edge
MAX_SHIFT = 2         # lateral samples per station (0.5 m per m of lap)
SHIFT_PENALTY = 0.08  # evidence units per lateral sample moved
WEAK_CONTRAST = 0.25  # evidence below this is "not seen"
OCCLUSION_WIN = 3.0   # m outside the edge checked for shadow
ROBUST_SIGMA = 10.0   # m, width smoothing scale
ROBUST_SCALE = 0.5    # m, residual scale for Tukey weights
WIDTH_FREE = 2.5      # m a half-width may deviate from the lap's typical one for free
WIDTH_PRIOR = 0.15    # evidence units per metre beyond that


@dataclass
class EdgeResult:
    stations: np.ndarray      # (N,) m along the midline
    mid_xy: np.ndarray        # (N,2) local metres
    left_xy: np.ndarray       # (N,2)
    right_xy: np.ndarray      # (N,2)
    half_left: np.ndarray     # (N,) m
    half_right: np.ndarray    # (N,) m
    evidence_left: np.ndarray
    evidence_right: np.ndarray
    seen_left: np.ndarray     # bool
    seen_right: np.ndarray
    resid_left: np.ndarray    # m, raw path minus smoothed path
    resid_right: np.ndarray
    total_m: float
    seed_shift_m: np.ndarray  # (N,) lateral move of the midline vs the seed


def _robust(x: np.ndarray) -> tuple[float, float]:
    x = x[np.isfinite(x)]
    med = float(np.median(x))
    mad = float(np.median(np.abs(x - med))) * 1.4826
    return med, max(mad, 1e-3)


def _features(S: np.ndarray, kind: str = "rgbn") -> np.ndarray:
    """Per-sample features (chroma-like, vegetation-like, brightness).

    rgbn (orthoimagery): chroma (max-min RGB), NDVI, brightness.
    lidar (ground-return raster, see lib/lidar.py): bands are (intensity,
    canopy fraction, 0, intensity); features are (0, canopy, intensity): no
    chroma, canopy stands in for vegetation, intensity is the brightness.
    """
    if kind == "lidar":
        return np.stack([np.zeros_like(S[..., 0]), S[..., 1], S[..., 0]], axis=-1)
    r, g, b, n = S[..., 0], S[..., 1], S[..., 2], S[..., 3]
    if kind == "rgb":  # no NIR band: no NDVI
        chroma = S[..., :3].max(-1) - S[..., :3].min(-1)
        return np.stack([chroma, np.zeros_like(r), (r + g + b) / 3.0], axis=-1)
    chroma = S[..., :3].max(-1) - S[..., :3].min(-1)
    ndvi = (n - r) / (n + r + 1.0)
    bright = (r + g + b) / 3.0
    return np.stack([chroma, ndvi * 100.0, bright], axis=-1)


FEATURE_WEIGHTS = {
    "rgbn": (1.0, 1.0, 0.35),   # brightness is shadow-sensitive: weigh it less
    "rgb": (1.0, 0.0, 0.5),     # no NIR: chroma carries vegetation, brightness a bit more
    "lidar": (0.0, 1.0, 1.0),   # lidar intensity has no shadows
}


def asphalt_probability(S: np.ndarray, t: np.ndarray, kind: str = "rgbn") -> np.ndarray:
    f = _features(S, kind)
    inner = np.abs(t) <= 1.5
    outer = (np.abs(t) >= 16) & (np.abs(t) <= 26)
    llr = np.zeros(f.shape[:2])
    weights = FEATURE_WEIGHTS[kind]
    for k in range(f.shape[-1]):
        mi, si = _robust(f[:, inner, k].ravel())
        mo, so = _robust(f[:, outer, k].ravel())
        # a feature that does not separate the classes carries no weight
        sep = abs(mi - mo) / math.hypot(si, so)
        w = weights[k] * min(1.0, sep)
        if w == 0.0:
            continue
        zi = (f[..., k] - mi) / si
        zo = (f[..., k] - mo) / so
        # Cauchy-ish tails: one odd channel must not dominate
        llr += w * (np.log1p(zo ** 2) - np.log1p(zi ** 2) + math.log(so / si))
    p = 1.0 / (1.0 + np.exp(-np.clip(llr, -30, 30)))
    p[~np.isfinite(S[..., 0])] = 0.5
    return p


def _box(a: np.ndarray, n: int, axis: int = 1) -> np.ndarray:
    """Mean over a window of n samples starting at each index (along axis)."""
    c = np.cumsum(np.insert(a, 0, 0, axis=axis), axis=axis)
    L = a.shape[axis]
    idx = np.arange(L)
    hi = np.clip(idx + n, 0, L)
    lo = idx
    return (np.take(c, hi, axis=axis) - np.take(c, lo, axis=axis)) / np.maximum(hi - lo, 1)


def _side_evidence(p: np.ndarray, bright: np.ndarray, chroma: np.ndarray, t_side: np.ndarray,
                   typical_half: float | None, dark_level: float) -> np.ndarray:
    """Evidence that the edge lies at each outward offset (t_side >= 0 increasing)."""
    w = int(round(EDGE_WIN / STEP_T))
    outside = _box(p, w)                              # [j, j+w)
    inside = np.full_like(p, np.nan)
    inside[:, w:] = outside[:, :-w]                   # [j-w, j)
    ev = inside - outside
    # painted line: a ridge of brightness 0.25-0.75 m wide, neutral, brighter
    # than both sides by a margin, with asphalt on the inside
    k = 3
    ridge = bright - 0.5 * (np.roll(bright, k, axis=1) + np.roll(bright, -k, axis=1))
    neutral = chroma < 20
    line = np.clip(ridge / 25.0, 0, 1) * neutral * np.nan_to_num(inside > 0.6)
    # the edge sits just outside a painted line: shift by one sample outward
    line = np.roll(line, 1, axis=1)
    ev = np.nan_to_num(ev, nan=-1.0) + 0.5 * line
    # shadow / occlusion: where the window around a candidate is mostly dark
    # the imagery says nothing about the edge -> neutral evidence, the path is
    # carried by its smoothness and the width prior instead
    dark = (bright < dark_level).astype(float)
    dwin = _box(dark, 2 * w)
    dwin = np.roll(dwin, w, axis=1)
    ev = np.where(dwin > 0.35, 0.0, ev)
    if typical_half is not None:
        ev -= WIDTH_PRIOR * np.clip(np.abs(t_side - typical_half) - WIDTH_FREE, 0, None)
    # soft width prior
    ev -= 0.6 * np.clip((MIN_HALF - t_side) / MIN_HALF, 0, None)
    ev -= 0.6 * np.clip((t_side - MAX_HALF) / 6.0, 0, None)
    return ev


def _dp_closed(ev: np.ndarray, limit: np.ndarray) -> np.ndarray:
    """Max-evidence path j(s) over a closed lap; limit[s] = max usable index."""
    N, T = ev.shape
    ev = ev.copy()
    mask = np.arange(T)[None, :] > limit[:, None]
    ev[mask] = -5.0
    E = np.vstack([ev, ev, ev])
    M = len(E)
    score = E[0].copy()
    back = np.zeros((M, T), dtype=np.int16)
    shifts = range(-MAX_SHIFT, MAX_SHIFT + 1)
    for i in range(1, M):
        best = np.full(T, -np.inf)
        arg = np.zeros(T, dtype=np.int16)
        for d in shifts:
            cand = np.full(T, -np.inf)
            if d >= 0:
                cand[d:] = score[:T - d] if d else score
            else:
                cand[:d] = score[-d:]
            cand -= SHIFT_PENALTY * abs(d)
            better = cand > best
            best[better] = cand[better]
            arg[better] = d
        score = best + E[i]
        back[i] = arg
    j = int(np.argmax(score))
    path = np.zeros(M, dtype=int)
    for i in range(M - 1, -1, -1):
        path[i] = j
        j = j - back[i, j]
    return path[N:2 * N]


def _profile(R: Raster, frame: geo.Frame, mid: np.ndarray, t: np.ndarray):
    nrm = geo.left_normals(mid)
    P = mid[:, None, :] + nrm[:, None, :] * t[None, :, None]
    S = R.sample(frame.to_lonlat(P))
    return S, nrm


def _extract_once(R: Raster, frame: geo.Frame, seed_xy: np.ndarray, typical=None):
    mid, total = geo.resample_closed(seed_xy, STEP_S)
    mid = geo.circular_gaussian(mid, SEED_SIGMA / STEP_S)
    t = np.arange(-T_MAX, T_MAX + 1e-9, STEP_T)
    S, nrm = _profile(R, frame, mid, t)
    kind = R.kind
    p = asphalt_probability(S, t, kind)
    f = _features(S, kind)
    bright = np.nan_to_num(f[..., 2])
    chroma = np.nan_to_num(f[..., 0], nan=255)
    kappa = geo.circular_gaussian(geo.curvature(mid, STEP_S), 8)
    radius = 1.0 / np.maximum(np.abs(kappa), 1e-6)
    c = len(t) // 2
    inner = np.abs(t) <= 1.5
    bmed, bmad = _robust(bright[:, inner].ravel())
    dark_level = bmed - 6 * bmad
    out = {"dark": (bright < dark_level)}
    for side, sl, sign in (("left", slice(c, None), 1), ("right", slice(c, None, -1), -1)):
        ts = np.abs(t[sl])
        ev = _side_evidence(p[:, sl], bright[:, sl], chroma[:, sl], ts[None, :],
                            None if typical is None else typical[side], dark_level)
        inside_turn = np.sign(kappa) == sign
        lim_m = np.where(inside_turn, np.minimum(0.85 * radius, T_MAX), T_MAX)
        limit = np.floor(lim_m / STEP_T).astype(int) - int(round(EDGE_WIN / STEP_T))
        path = _dp_closed(ev, limit)
        evid = ev[np.arange(len(path)), path]
        # occluded: shadow within 3 m outside the chosen edge -> the edge may
        # continue under it; never trust such a station
        dk = (bright[:, sl] < dark_level).astype(float)
        n_out = int(round(OCCLUSION_WIN / STEP_T))
        rows = np.arange(len(path))[:, None]
        cols = np.clip(path[:, None] + np.arange(-2, n_out)[None, :], 0, dk.shape[1] - 1)
        occluded = dk[rows, cols].mean(axis=1) > 0.2
        evid = np.where(occluded, 0.0, evid)
        out[side] = (ts[path], evid)
    return mid, nrm, total, out


def extract_edges(R: Raster, frame: geo.Frame, seed_xy: np.ndarray, iterations: int = 3) -> EdgeResult:
    seed0, _ = geo.resample_closed(seed_xy, STEP_S)
    cur = seed_xy
    typical = None
    for it in range(iterations):
        mid, nrm, total, out = _extract_once(R, frame, cur, typical)
        hl, el = out["left"]
        hr, er = out["right"]
        seen_l = el > WEAK_CONTRAST
        seen_r = er > WEAK_CONTRAST
        hl = _fill_and_smooth(hl, seen_l)
        hr = _fill_and_smooth(hr, seen_r)
        centre = mid + nrm * ((hl - hr) / 2.0)[:, None]
        cur = centre
        typical = {"left": float(np.median(hl)), "right": float(np.median(hr))}
    left = mid + nrm * hl[:, None]
    right = mid - nrm * hr[:, None]
    # final midline and its stations
    midline = (left + right) / 2.0
    raw_l, raw_r = out["left"][0], out["right"][0]
    cum = geo.cumulative(midline)
    shift = np.array([geo.project(seed0, geo.cumulative(seed0), p)[1] for p in midline[::5]])
    return EdgeResult(
        stations=cum[:-1], mid_xy=midline, left_xy=left, right_xy=right,
        half_left=hl, half_right=hr, evidence_left=el, evidence_right=er,
        seen_left=seen_l, seen_right=seen_r,
        resid_left=np.where(seen_l, raw_l - hl, np.nan),
        resid_right=np.where(seen_r, raw_r - hr, np.nan),
        total_m=float(cum[-1]), seed_shift_m=shift,
    )


def _fill_and_smooth(h: np.ndarray, seen: np.ndarray) -> np.ndarray:
    """Robust smooth of a half-width signal.

    Unseen stations get zero weight; the rest are fitted by iteratively
    reweighted Gaussian smoothing (sigma ROBUST_SIGMA m) with Tukey weights on
    the residual (scale ROBUST_SCALE m), so short bumps into kerbs, painted
    run-off or shadow are rejected while real, gradual width changes stay.
    """
    h = np.asarray(h, dtype=float)
    w = seen.astype(float)
    if w.sum() < 10:
        return np.full_like(h, float(np.nanmedian(h)))
    fit = None
    for _ in range(6):
        num = geo.circular_gaussian(np.nan_to_num(h) * w, ROBUST_SIGMA / STEP_S)
        den = geo.circular_gaussian(w, ROBUST_SIGMA / STEP_S)
        fit = num / np.maximum(den, 1e-6)
        r = (h - fit) / (4.685 * ROBUST_SCALE)
        w = seen * np.where(np.abs(r) < 1, (1 - r ** 2) ** 2, 0.0)
    # a light final pass keeps corner-scale detail from well-supported samples
    num = geo.circular_gaussian(np.nan_to_num(h) * w, 2.0 / STEP_S)
    den = geo.circular_gaussian(w, 2.0 / STEP_S)
    fine = num / np.maximum(den, 1e-6)
    support = den > 0.5
    out = np.where(support & (np.abs(fine - fit) < 0.75), fine, fit)
    # long unseen gaps: the Gaussian has no support there -> bridge linearly
    # between the nearest supported stations (reported as interpolated)
    den0 = geo.circular_gaussian(w, ROBUST_SIGMA / STEP_S)
    ok = den0 > 0.05
    if not ok.all():
        n = len(out)
        idx = np.arange(n)
        gi = idx[ok]
        out[~ok] = np.interp(idx[~ok], np.concatenate([gi - n, gi, gi + n]),
                             np.tile(out[ok], 3))
        out = geo.circular_gaussian(out, 2.0 / STEP_S)
    return out

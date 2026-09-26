"""Planar geometry helpers for closed racing laps (numpy).

Everything here works in a local tangent-plane frame in metres. A `Frame` maps
WGS84 [lon, lat] to (x east, y north) metres about a reference point with the
ellipsoid's local radii; over a circuit (< 10 km) the scale error is well under
1 cm per km, far below any source accuracy we handle.

A lap is a closed polyline sampled at a uniform arc-length step. Arrays are
(N, 2) with the closing point *not* repeated; index arithmetic is modulo N.
"""
from __future__ import annotations

import math

import numpy as np

# WGS84
_A = 6378137.0
_E2 = 6.69437999014e-3


class Frame:
    """Local east/north metres about (lon0, lat0)."""

    def __init__(self, lon0: float, lat0: float):
        self.lon0 = float(lon0)
        self.lat0 = float(lat0)
        phi = math.radians(lat0)
        s = math.sin(phi)
        w = math.sqrt(1 - _E2 * s * s)
        self.m_per_deg_lat = math.radians(1) * _A * (1 - _E2) / (w ** 3)
        self.m_per_deg_lon = math.radians(1) * _A * math.cos(phi) / w

    @classmethod
    def around(cls, lonlat) -> "Frame":
        a = np.asarray(lonlat, dtype=float)
        return cls(float(a[:, 0].mean()), float(a[:, 1].mean()))

    def to_xy(self, lonlat) -> np.ndarray:
        a = np.asarray(lonlat, dtype=float)
        return np.stack([(a[..., 0] - self.lon0) * self.m_per_deg_lon,
                         (a[..., 1] - self.lat0) * self.m_per_deg_lat], axis=-1)

    def to_lonlat(self, xy) -> np.ndarray:
        a = np.asarray(xy, dtype=float)
        return np.stack([a[..., 0] / self.m_per_deg_lon + self.lon0,
                         a[..., 1] / self.m_per_deg_lat + self.lat0], axis=-1)


def open_ring(xy: np.ndarray) -> np.ndarray:
    xy = np.asarray(xy, dtype=float)
    if len(xy) > 1 and np.allclose(xy[0], xy[-1]):
        return xy[:-1]
    return xy


def cumulative(xy: np.ndarray, closed: bool = True) -> np.ndarray:
    """Arc length at each vertex; for a closed ring, one extra entry = total."""
    pts = np.vstack([xy, xy[:1]]) if closed else xy
    seg = np.hypot(*np.diff(pts, axis=0).T)
    return np.concatenate([[0.0], np.cumsum(seg)])


def resample_closed(xy: np.ndarray, step: float) -> tuple[np.ndarray, float]:
    """Uniformly resample a closed ring. Returns (points (N,2), total length)."""
    xy = open_ring(xy)
    cum = cumulative(xy)
    total = float(cum[-1])
    n = max(8, int(round(total / step)))
    s = np.linspace(0.0, total, n, endpoint=False)
    pts = np.vstack([xy, xy[:1]])
    x = np.interp(s, cum, pts[:, 0])
    y = np.interp(s, cum, pts[:, 1])
    return np.stack([x, y], axis=1), total


def resample_open(xy: np.ndarray, step: float) -> np.ndarray:
    cum = cumulative(xy, closed=False)
    n = max(2, int(round(cum[-1] / step)) + 1)
    s = np.linspace(0.0, cum[-1], n)
    return np.stack([np.interp(s, cum, xy[:, 0]), np.interp(s, cum, xy[:, 1])], axis=1)


def circular_gaussian(values: np.ndarray, sigma_samples: float) -> np.ndarray:
    """Gaussian smoothing of a periodic signal (1-D or (N, k)) via FFT."""
    v = np.asarray(values, dtype=float)
    if sigma_samples <= 0:
        return v.copy()
    n = v.shape[0]
    freq = np.fft.fftfreq(n)
    kernel = np.exp(-2.0 * (math.pi * freq * sigma_samples) ** 2)
    if v.ndim == 1:
        return np.real(np.fft.ifft(np.fft.fft(v) * kernel))
    return np.real(np.fft.ifft(np.fft.fft(v, axis=0) * kernel[:, None], axis=0))


def circular_median(values: np.ndarray, half_window: int) -> np.ndarray:
    """Running median of a periodic signal; NaNs are ignored."""
    v = np.asarray(values, dtype=float)
    n = len(v)
    idx = (np.arange(n)[:, None] + np.arange(-half_window, half_window + 1)[None, :]) % n
    with np.errstate(all="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            return np.nanmedian(v[idx], axis=1)


def tangents(xy: np.ndarray) -> np.ndarray:
    """Unit tangents of a closed uniformly-sampled ring (central differences)."""
    d = np.roll(xy, -1, axis=0) - np.roll(xy, 1, axis=0)
    return d / np.linalg.norm(d, axis=1, keepdims=True)


def left_normals(xy: np.ndarray) -> np.ndarray:
    t = tangents(xy)
    return np.stack([-t[:, 1], t[:, 0]], axis=1)


def curvature(xy: np.ndarray, ds: float) -> np.ndarray:
    """Signed curvature (1/m, + = turning left) of a closed uniform ring."""
    t = tangents(xy)
    ang = np.unwrap(np.arctan2(t[:, 1], t[:, 0]))
    # periodic derivative of heading: correct the wrap at the seam
    d = np.roll(ang, -1) - np.roll(ang, 1)
    d = (d + math.pi) % (2 * math.pi) - math.pi
    return d / (2 * ds)


def unwrap_wrapped(a: float, b: float, total: float) -> float:
    """Signed shortest distance b - a on a loop of length total."""
    d = (b - a) % total
    return d - total if d > total / 2 else d


def project(xy_ring: np.ndarray, cum: np.ndarray, p) -> tuple[float, float, float]:
    """Project p onto a closed ring. Returns (station m, signed offset m (+left), distance)."""
    p = np.asarray(p, dtype=float)
    a = xy_ring
    b = np.roll(xy_ring, -1, axis=0)
    ab = b - a
    l2 = np.einsum("ij,ij->i", ab, ab)
    l2[l2 == 0] = 1e-12
    t = np.clip(np.einsum("ij,ij->i", p - a, ab) / l2, 0.0, 1.0)
    q = a + ab * t[:, None]
    d = np.hypot(*(p - q).T)
    i = int(np.argmin(d))
    cross = ab[i, 0] * (p[1] - a[i, 1]) - ab[i, 1] * (p[0] - a[i, 0])
    s = float(cum[i] + t[i] * math.sqrt(l2[i]))
    return s, float(math.copysign(d[i], cross)), float(d[i])


def douglas_peucker(xy: np.ndarray, tol: float) -> np.ndarray:
    """Simplify an open polyline, keeping endpoints."""
    xy = np.asarray(xy, dtype=float)
    if len(xy) < 3:
        return xy
    keep = np.zeros(len(xy), dtype=bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(xy) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        a, b = xy[i], xy[j]
        ab = b - a
        L = math.hypot(*ab)
        seg = xy[i + 1:j]
        if L == 0:
            d = np.hypot(*(seg - a).T)
        else:
            d = np.abs(ab[0] * (seg[:, 1] - a[1]) - ab[1] * (seg[:, 0] - a[0])) / L
        k = int(np.argmax(d))
        if d[k] > tol:
            m = i + 1 + k
            keep[m] = True
            stack.append((i, m))
            stack.append((m, j))
    return xy[keep]


def simplify_closed(xy: np.ndarray, tol: float) -> np.ndarray:
    """Simplify a closed ring; returns an explicitly closed ring (first == last)."""
    ring = np.vstack([xy, xy[:1]])
    return douglas_peucker(ring, tol)


def lonlat_list(ll: np.ndarray, nd: int = 7) -> list[list[float]]:
    return [[round(float(a), nd), round(float(b), nd)] for a, b in ll]

"""Racing line and a quasi-steady-state lap on the measured surface.

Offline, deterministic, no dependencies beyond numpy. Given the measured
midline with its left/right edges (lib/surface.LapGeometry) this computes:

  * the minimum-curvature racing line inside the edges, the car's half width
    kept off each edge: min sum |p[i-1] - 2 p[i] + p[i+1]|^2 over lateral
    offsets alpha[i] along the midline normals, a box-constrained QP solved by
    an active-set method;
  * a quasi-steady-state speed profile for a reference car on that line:
    cornering speed capped by grip (with downforce), a forward pass limited by
    power, traction and the friction ellipse, a backward pass by braking;
  * per-corner phases from the profile: braking point, minimum speed, racing
    apex (where the line clips the inside edge), full throttle, and a
    character (kink / high_speed / medium / slow).

This is a model, not a measurement. It has no elevation, no kerbs and a
generic car; figures are stated with the model that produced them. The
algorithm is documented in docs/GEOMETRY.md ("Racing line and phases").
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import geo

G0 = 9.81
RHO = 1.2
QP_STEP_STATIONS = 3       # optimise on every 3rd midline station (~3 m)
ADMM_RHO = 1e-4            # ADMM penalty relative to mean diag(H); within ~2 cm of an exact active set
QP_ROUNDS = 3              # re-linearisations of the curvature around the current line
LINE_STEP_M = 2.0          # m, racing-line resampling for the speed profile
LINE_KAPPA_SIGMA_M = 4.0   # m, smoothing of racing-line curvature
APEX_TIE_M = 0.15          # m, stations this close to the minimum edge gap share the apex
BRAKE_EPS = 0.05           # m/s, braking where the backward pass is this far below the forward
FLAT_LIMIT = 0.98          # a corner is taken flat if speed stays below this share of its grip limit
PHASE_LEAD_S = 0.5         # s, a corner's range starts this long before braking, ends this long after full throttle
HIGH_SPEED_KMH = 160.0     # minimum speed at or above this = high-speed corner
SLOW_KMH = 100.0           # below this = slow corner
MIN_BRAKE_M = 10.0         # m, shorter braking than this counts as none (a lift)


@dataclass(frozen=True)
class Car:
    id: str
    name: str
    mass_kg: float
    power_w: float          # at the wheels
    mu: float               # tyre friction, lateral and braking
    drive_share: float      # share of load on the driven axle (traction limit)
    cla_m2: float           # downforce coefficient x area
    cda_m2: float           # drag coefficient x area
    width_m: float

    def down(self, v):
        return 0.5 * RHO * self.cla_m2 * v * v / self.mass_kg

    def drag(self, v):
        return 0.5 * RHO * self.cda_m2 * v * v / self.mass_kg


GT3 = Car(id="gt3", name="GT3 (IMSA GTD class), generic", mass_kg=1350.0, power_w=330e3, mu=1.5,
          drive_share=0.6, cla_m2=2.8, cda_m2=1.0, width_m=2.05)


# --- racing line --------------------------------------------------------------
def _box_qp(H: np.ndarray, g: np.ndarray, lo: np.ndarray, hi: np.ndarray, x0: np.ndarray | None = None,
            iters: int = 5000, tol: float = 1e-4) -> np.ndarray:
    """min 1/2 x'Hx + g'x  s.t. lo <= x <= hi, by ADMM (one factorisation, then mat-vecs)."""
    rho = ADMM_RHO * float(np.mean(np.diag(H)))   # small: the curvature QP is badly conditioned
    M = np.linalg.inv(H + rho * np.eye(len(g)))
    z = np.clip(np.zeros_like(g) if x0 is None else x0, lo, hi)
    u = np.zeros_like(g)
    for _ in range(iters):
        x = M @ (rho * (z - u) - g)
        z_old = z
        z = np.clip(x + u, lo, hi)
        u += x - z
        if max(np.abs(x - z).max(), np.abs(z - z_old).max()) < tol:
            break
    return z


def min_curvature_offsets(mid: np.ndarray, nrm: np.ndarray, lo: np.ndarray, hi: np.ndarray,
                          rounds: int = QP_ROUNDS) -> np.ndarray:
    """Lateral offsets alpha (along nrm) minimising sum kappa^2 of mid + alpha nrm.

    kappa[i] ~ nhat[i] . (p[i-1] - 2 p[i] + p[i+1]) / (ds[i-1] ds[i]), linear in
    alpha with the current line's normals nhat and spacing ds held fixed; the
    line is re-linearised `rounds` times. (The bare second difference would
    also reward shrinking the spacing, which is not curvature.)
    """
    n = len(mid)
    i = np.arange(n)
    alpha = np.zeros(n)
    for _ in range(rounds):
        p = mid + nrm * alpha[:, None]
        seg = np.hypot(*(np.roll(p, -1, axis=0) - p).T)
        w = 1.0 / (np.roll(seg, 1) * seg)
        nh = geo.left_normals(p)
        A = np.zeros((n, n))
        cx, cy = nh[:, 0] * w, nh[:, 1] * w
        for off, coef in ((-1, 1.0), (0, -2.0), (1, 1.0)):
            j = (i + off) % n
            A[i, j] += coef * (cx * nrm[j, 0] + cy * nrm[j, 1])
        b = cx * (np.roll(mid[:, 0], 1) - 2 * mid[:, 0] + np.roll(mid[:, 0], -1)) + \
            cy * (np.roll(mid[:, 1], 1) - 2 * mid[:, 1] + np.roll(mid[:, 1], -1))
        H = A.T @ A + 1e-10 * np.eye(n)
        alpha = _box_qp(H, A.T @ b, lo, hi, x0=alpha)
    return alpha


# --- speed profile -----------------------------------------------------------
def speed_profile(kappa: np.ndarray, ds: np.ndarray, car: Car) -> dict:
    """Quasi-steady-state lap. kappa[i] at point i, ds[i] from point i to i+1 (closed)."""
    n = len(kappa)
    k = np.abs(kappa)
    den = k - car.mu * 0.5 * RHO * car.cla_m2 / car.mass_kg
    v_top = (2 * car.power_w / (RHO * car.cda_m2)) ** (1 / 3)
    with np.errstate(divide="ignore", invalid="ignore"):
        vlim = np.where(den > 0, np.sqrt(car.mu * G0 / den), v_top)
    vlim = np.minimum(vlim, v_top)

    def ellipse(v, i):
        a_max = car.mu * (G0 + car.down(v))
        return math.sqrt(max(0.0, 1.0 - (v * v * k[i] / a_max) ** 2)) if a_max > 0 else 0.0

    start = int(np.argmin(vlim))
    order = [(start + j) % n for j in range(n + 1)]
    fwd = np.empty(n)
    power = np.zeros(n, dtype=bool)
    v = vlim[start]
    fwd[start] = v
    for a, b in zip(order[:-1], order[1:]):
        grip = car.mu * car.drive_share * (G0 + car.down(v)) * ellipse(v, a)
        pw = car.power_w / (car.mass_kg * max(v, 1.0))
        power[a] = pw <= grip
        acc = min(pw, grip) - car.drag(v)
        v = min(math.sqrt(max(v * v + 2 * acc * ds[a], 0.0)), vlim[b])
        if b != start:
            fwd[b] = v
    bwd = np.empty(n)
    v = vlim[start]
    bwd[start] = v
    for b, a in zip(order[:0:-1], order[-2::-1]):   # walk the lap backwards: from b to its predecessor a
        dec = car.mu * (G0 + car.down(v)) * ellipse(v, b) + car.drag(v)
        v = min(math.sqrt(v * v + 2 * dec * ds[a]), vlim[a])
        if a != start:
            bwd[a] = v
    speed = np.minimum(fwd, bwd)
    lap_s = float(np.sum(ds / np.maximum((speed + np.roll(speed, -1)) / 2, 0.1)))
    return {"v": speed, "fwd": fwd, "bwd": bwd, "vlim": vlim, "power": power, "lap_s": lap_s, "v_top": v_top}


# --- the lap -----------------------------------------------------------------
class Lap:
    """Racing line + speed profile on a LapGeometry. Stations are midline stations."""

    def __init__(self, G, car: Car = GT3):
        self.G, self.car = G, car
        idx = np.arange(0, G.N, QP_STEP_STATIONS)
        mid, nrm = G.mid[idx], G.nrm[idx]
        wl = np.einsum("ij,ij->i", G.left[idx] - mid, nrm)
        wr = np.einsum("ij,ij->i", mid - G.right[idx], nrm)
        half = car.width_m / 2
        lo, hi = -wr + half, wl - half
        narrow = lo > hi                       # narrower than the car: stay mid-way
        lo[narrow] = hi[narrow] = (lo[narrow] + hi[narrow]) / 2
        alpha = min_curvature_offsets(mid, nrm, lo, hi)
        pts = mid + nrm * alpha[:, None]
        # resample uniformly along the line; keep the station of every point
        st = idx * (G.total / G.N)
        cum = geo.cumulative(pts)
        self.length = float(cum[-1])
        n = max(8, int(round(self.length / LINE_STEP_M)))
        ell = np.linspace(0.0, self.length, n, endpoint=False)
        ring = np.vstack([pts, pts[:1]])
        st_unw = np.append(np.unwrap(st / G.total * 2 * math.pi) / (2 * math.pi) * G.total, st[0] + G.total)
        self.xy = np.stack([np.interp(ell, cum, ring[:, 0]), np.interp(ell, cum, ring[:, 1])], axis=1)
        self.station = np.interp(ell, cum, st_unw) % G.total
        self.ds = np.full(n, self.length / n)
        self.kappa = geo.circular_gaussian(geo.curvature(self.xy, self.length / n), LINE_KAPPA_SIGMA_M / (self.length / n))
        # edge gaps (car centre to each edge) at every line point
        mi = np.array([G.idx(s) for s in self.station])
        off = np.einsum("ij,ij->i", self.xy - G.mid[mi], G.nrm[mi])
        self.gap = {"left": np.einsum("ij,ij->i", G.left[mi] - G.mid[mi], G.nrm[mi]) - off,
                    "right": off - np.einsum("ij,ij->i", G.right[mi] - G.mid[mi], G.nrm[mi])}
        self.mi = mi
        self.prof = speed_profile(self.kappa, self.ds, car)
        self.v = self.prof["v"]
        self.n = n

    # line index <-> midline station
    def at_station(self, s: float) -> int:
        d = np.abs(((self.station - s) + self.G.total / 2) % self.G.total - self.G.total / 2)
        return int(np.argmin(d))

    def _window(self, s0: float, s1: float) -> np.ndarray:
        i0, i1 = self.at_station(s0), self.at_station(s1)
        return np.arange(i0, i0 + ((i1 - i0) % self.n) + 1) % self.n

    def _walk_time(self, i: int, seconds: float, step: int) -> int:
        t = 0.0
        while t < seconds:
            j = (i + step) % self.n
            t += self.ds[min(i, j) if step < 0 else i] / max(self.v[i], 1.0)
            i = j
        return i

    def corner(self, entry_s: float, exit_s: float, inside: str) -> dict:
        """Phases of one corner bounded (geometrically) by entry..exit midline stations."""
        v, fwd, bwd, vlim, power = (self.prof[k] for k in ("v", "fwd", "bwd", "vlim", "power"))
        w = self._window(entry_s - 15.0, exit_s + 15.0)
        i_min = int(w[np.argmin(v[w])])
        braking = bwd < fwd - BRAKE_EPS
        # braking point: back from the minimum while the speed keeps rising
        # (braking and trail braking into the corner)
        i = i_min
        for _ in range(self.n):
            j = (i - 1) % self.n
            if v[j] <= v[i] + 1e-3:
                break
            i = j
        i_b = i if i != i_min else None
        brake_m = float(((i_min - i_b) % self.n) * self.ds[0]) if i_b is not None else 0.0
        if brake_m < MIN_BRAKE_M:
            i_b, brake_m = None, 0.0
        # full throttle: forward from the minimum to the first power-limited point
        i_f = i_min
        for _ in range(self.n):
            if power[i_f] and not braking[i_f]:
                break
            i_f = (i_f + 1) % self.n
        # racing apex: the line's closest approach to the inside edge
        pad = min(LINE_STEP_M, ((exit_s - entry_s) % self.G.total) / 4)   # stay strictly inside turn-in..exit
        aw = self._window(entry_s + pad, exit_s - pad)
        gap = self.gap[inside][aw]
        tie = np.flatnonzero(gap <= gap.min() + APEX_TIE_M)
        k0 = int(np.argmin(gap))
        run = [k0]
        for step in (-1, 1):
            k = k0 + step
            while 0 <= k < len(aw) and k in set(tie.tolist()):
                run.append(k)
                k += step
        i_apex = int(aw[sorted(run)[len(run) // 2]])
        flat = i_b is None and float(np.max(v[w] / vlim[w])) < FLAT_LIMIT
        v_min = float(v[i_min]) * 3.6
        character = ("kink" if flat else "high_speed" if v_min >= HIGH_SPEED_KMH
                     else "medium" if v_min >= SLOW_KMH else "slow")
        # the range always covers turn-in..track-out, and braking..full throttle
        i_in, i_out = self.at_station(entry_s), self.at_station(exit_s)
        back = lambda i: (i_apex - i) % self.n     # line points before the apex
        ahead = lambda i: (i - i_apex) % self.n    # line points after the apex
        first = i_b if i_b is not None and back(i_b) > back(i_in) else i_in
        last = i_f if ahead(i_out) < ahead(i_f) < self.n / 2 else i_out
        i_start = self._walk_time(first, PHASE_LEAD_S, -1)
        i_end = self._walk_time(last, PHASE_LEAD_S, +1)
        return {
            "character": character,
            "i_min": i_min, "i_apex": i_apex, "i_brake": i_b, "i_full": i_f, "i_start": i_start, "i_end": i_end,
            "min_speed_kmh": round(v_min, 1),
            "entry_speed_kmh": round(float(v[i_b]) * 3.6, 1) if i_b is not None else None,
            "brake_m": round(brake_m, 1),
            "apex_gap_m": round(float(self.gap[inside][i_apex]) - self.car.width_m / 2, 2),
        }

#!/usr/bin/env python3
"""Generate apex-candidate points and corner-range candidates from centerline curvature.

This is intentionally a lightweight, deterministic preprocessing tool rather
than a full CasADi minimum-lap-time optimizer. It implements the first useful
piece of that stack for Track Atlas: reduce a layout centerline to a smooth
1D curvature profile kappa(s), then emit likely apexes and corner influence
ranges. The generated data is meant for verification/curation, not as an
authoritative race-control source.
"""
from __future__ import annotations

import json
import math
import sys
from bisect import bisect_right
from pathlib import Path
from typing import Any

EARTH_R = 6371008.8


def haversine(a: list[float], b: list[float]) -> float:
    lon1, lat1 = math.radians(a[0]), math.radians(a[1])
    lon2, lat2 = math.radians(b[0]), math.radians(b[1])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_R * math.asin(min(1.0, math.sqrt(h)))


def load_outline(path: str) -> list[list[float]]:
    gj = json.loads(Path(path).read_text())
    if gj.get("type") == "LineString":
        coords = gj["coordinates"]
    else:
        coords = None
        for f in gj.get("features", []):
            if f.get("geometry", {}).get("type") == "LineString" and f.get("properties", {}).get("role") == "outline":
                coords = f["geometry"]["coordinates"]
                break
        if coords is None:
            for f in gj.get("features", []):
                if f.get("geometry", {}).get("type") == "LineString":
                    coords = f["geometry"]["coordinates"]
                    break
    if not coords or len(coords) < 4:
        raise ValueError(f"no usable LineString outline in {path}")
    out = [[float(c[0]), float(c[1])] for c in coords]
    if out[0] == out[-1]:
        out = out[:-1]
    return out


def arc_lengths_lonlat(coords: list[list[float]]) -> tuple[list[float], float]:
    closed = coords + [coords[0]]
    cum = [0.0]
    for a, b in zip(closed, closed[1:]):
        cum.append(cum[-1] + haversine(a, b))
    return cum, cum[-1]


def local_xy(coords: list[list[float]]) -> list[tuple[float, float]]:
    lat0 = math.radians(sum(c[1] for c in coords) / len(coords))
    lon_ref = coords[0][0]
    lat_ref = coords[0][1]
    return [
        (
            math.radians(c[0] - lon_ref) * EARTH_R * math.cos(lat0),
            math.radians(c[1] - lat_ref) * EARTH_R,
        )
        for c in coords
    ]


def interpolate_closed(values: list[Any], cum: list[float], total: float, s: float) -> Any:
    s = s % total
    i = bisect_right(cum, s) - 1
    if i >= len(values):
        i = len(values) - 1
    j = (i + 1) % len(values)
    seg = (cum[i + 1] - cum[i]) if i + 1 < len(cum) else (total - cum[i])
    t = 0.0 if seg <= 1e-9 else (s - cum[i]) / seg
    a, b = values[i], values[j]
    if isinstance(a, (list, tuple)):
        return [a[k] + (b[k] - a[k]) * t for k in range(len(a))]
    return a + (b - a) * t


def resample(coords: list[list[float]], step_m: float) -> tuple[list[float], list[list[float]], list[tuple[float, float]], float]:
    cum, total = arc_lengths_lonlat(coords)
    xy = local_xy(coords)
    n = max(80, int(round(total / step_m)))
    step = total / n
    ss = [i * step for i in range(n)]
    ll = [interpolate_closed(coords, cum, total, s) for s in ss]
    xys = [tuple(interpolate_closed(xy, cum, total, s)) for s in ss]
    return ss, ll, xys, total


def curvature_profile(xy: list[tuple[float, float]], ds: float) -> list[float]:
    n = len(xy)
    out = []
    for i in range(n):
        x0, y0 = xy[(i - 1) % n]
        x1, y1 = xy[i]
        x2, y2 = xy[(i + 1) % n]
        dx = (x2 - x0) / (2 * ds)
        dy = (y2 - y0) / (2 * ds)
        ddx = (x2 - 2 * x1 + x0) / (ds * ds)
        ddy = (y2 - 2 * y1 + y0) / (ds * ds)
        denom = (dx * dx + dy * dy) ** 1.5
        out.append(0.0 if denom < 1e-12 else (dx * ddy - dy * ddx) / denom)
    return out


def circular_smooth(vals: list[float], window: int) -> list[float]:
    if window <= 1:
        return vals[:]
    if window % 2 == 0:
        window += 1
    half = window // 2
    n = len(vals)
    out = []
    for i in range(n):
        out.append(sum(vals[(i + j) % n] for j in range(-half, half + 1)) / window)
    return out


def percentile(vals: list[float], q: float) -> float:
    if not vals:
        return 0.0
    xs = sorted(vals)
    idx = min(len(xs) - 1, max(0, int(round((len(xs) - 1) * q))))
    return xs[idx]


def point_at_s(samples_ll: list[list[float]], total: float, s: float) -> list[float]:
    n = len(samples_ll)
    step = total / n
    i = int(math.floor((s % total) / step)) % n
    j = (i + 1) % n
    t = ((s % total) - i * step) / step
    a, b = samples_ll[i], samples_ll[j]
    return [round(a[0] + (b[0] - a[0]) * t, 6), round(a[1] + (b[1] - a[1]) * t, 6)]


def wrapped_distance(a: float, b: float, total: float) -> float:
    d = abs(a - b) % total
    return min(d, total - d)


def find_peaks(abs_k: list[float], ss: list[float], total: float, min_k: float, min_sep_m: float, max_count: int | None) -> list[int]:
    candidates = []
    n = len(abs_k)
    for i in range(n):
        if abs_k[i] < min_k:
            continue
        if abs_k[i] >= abs_k[(i - 1) % n] and abs_k[i] > abs_k[(i + 1) % n]:
            candidates.append(i)
    candidates.sort(key=lambda i: abs_k[i], reverse=True)
    chosen: list[int] = []
    for i in candidates:
        if all(wrapped_distance(ss[i], ss[j], total) >= min_sep_m for j in chosen):
            chosen.append(i)
        if max_count and len(chosen) >= max_count:
            break
    return sorted(chosen, key=lambda i: ss[i])


def range_for_peak(i: int, k: list[float], ss: list[float], total: float, params: dict[str, Any]) -> tuple[float, float]:
    n = len(k)
    peak = abs(k[i])
    floor = float(params.get("range_min_abs_curvature", 0.00012))
    threshold = max(floor, peak * float(params.get("range_threshold_ratio", 0.32)))
    max_walk = float(params.get("max_corner_range_m", 650.0))
    pre = float(params.get("pre_brake_m", 75.0))
    post = float(params.get("post_accel_m", 55.0))

    left = i
    walked = 0.0
    step = total / n
    while walked < max_walk and abs(k[(left - 1) % n]) >= threshold:
        left = (left - 1) % n
        walked += step
    right = i
    walked = 0.0
    while walked < max_walk and abs(k[(right + 1) % n]) >= threshold:
        right = (right + 1) % n
        walked += step

    start = ss[left] - pre
    end = ss[right] + post
    # Current RangeItem schema cannot represent wrap-around ranges. Clamp ranges
    # that straddle start/finish; apexes still carry the exact marker.
    return max(0.0, start / total), min(1.0, end / total)


def scale_for_curvature(abs_k: float) -> int:
    # Radius buckets: lower radius == more severe. Track Atlas scale convention:
    # 1=hairpin/slow, 6=kink.
    if abs_k <= 1e-9:
        return 6
    r = 1.0 / abs_k
    if r < 55:
        return 1
    if r < 95:
        return 2
    if r < 160:
        return 3
    if r < 280:
        return 4
    if r < 550:
        return 5
    return 6


def compute_layers(centerline_path: str, params: dict[str, Any] | None = None, resource_meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return Track Atlas point/range layers derived from centerline curvature."""
    params = params or {}
    resource_meta = resource_meta or {}
    coords = load_outline(centerline_path)

    step_m = float(params.get("step_m", 4.0))
    smooth_window_m = float(params.get("smooth_window_m", 90.0))
    ss, ll, xy, total = resample(coords, step_m)
    ds = total / len(ss)
    raw_k = curvature_profile(xy, ds)
    smooth_window = max(1, int(round(smooth_window_m / ds)))
    k = circular_smooth(circular_smooth(raw_k, smooth_window), max(1, smooth_window // 2))
    abs_k = [abs(x) for x in k]

    min_k = float(params.get("min_abs_curvature", 0.0))
    if min_k <= 0:
        min_k = max(0.00018, percentile(abs_k, float(params.get("curvature_percentile", 0.82))))
    peaks = find_peaks(
        abs_k,
        ss,
        total,
        min_k,
        float(params.get("min_separation_m", 90.0)),
        params.get("max_apexes"),
    )

    point_items = []
    range_items = []
    for idx, i in enumerate(peaks, 1):
        marker = ss[i] / total
        direction = "left" if k[i] > 0 else "right"
        label = f"Apex {idx} ({'L' if direction == 'left' else 'R'})"
        item_id = f"apex{idx}"
        point_items.append({
            "id": item_id,
            "label": label,
            "marker": round(marker, 8),
            "location": point_at_s(ll, total, ss[i]),
            "location_source": "centerline",
            "direction": direction,
            "scale": scale_for_curvature(abs_k[i]),
        })
        start, end = range_for_peak(i, k, ss, total, params)
        if end - start >= float(params.get("min_range_fraction", 0.002)):
            range_items.append({
                "id": f"corner{idx}",
                "label": f"Corner candidate {idx}",
                "start": round(start, 8),
                "end": round(end, 8),
                "anchor": item_id,
            })

    source = params.get("source", "centerline curvature profile")
    provenance = {
        "source": source,
        "local_path": resource_meta.get("relative_path") or resource_meta.get("local_path") or centerline_path,
        "method": "uniform resample → finite-difference curvature → circular moving-average smoothing → local curvature maxima",
        "step_m": step_m,
        "smooth_window_m": smooth_window_m,
        "min_abs_curvature": min_k,
        "lap_length_m": total,
    }
    return {
        "point_layers": [{
            "id": params.get("point_layer_id", "curvature_apexes"),
            "kind": "apex_candidates",
            "label": params.get("point_label", "Curvature Apex Candidates"),
            "description": params.get("point_description", "Computed apex candidates from the smoothed centerline curvature profile; intended for verification/curation."),
            "series": params.get("series", []),
            "items": point_items,
        }],
        "range_layers": [{
            "id": params.get("range_layer_id", "curvature_corner_ranges"),
            "kind": "corner_candidates",
            "label": params.get("range_label", "Curvature Corner Ranges"),
            "description": params.get("range_description", "Computed corner influence ranges: thresholded curvature region with brake/accel padding."),
            "series": params.get("series", []),
            "coverage": "partial",
            "generated": True,
            "provenance": provenance,
            "items": range_items,
        }],
    }


def main() -> None:
    payload = json.load(sys.stdin)
    params = payload.get("params") or {}
    resource_name = params.get("resource", "centerline")
    resource = payload["resources"][resource_name]
    print(json.dumps(compute_layers(resource["local_path"], params, resource), ensure_ascii=False))


if __name__ == "__main__":
    main()

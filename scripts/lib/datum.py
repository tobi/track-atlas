"""Horizontal datum: what the atlas's coordinates mean, and getting sources there.

The atlas publishes WGS 84 in the sense a GNSS receiver reports it today:
WGS 84 (G2139), which agrees with ITRF2014/ITRF2020 to about a centimetre, at
the coordinate epoch ATLAS_EPOCH. That is what Omatrack compares against
(car GNSS). Ground on a tectonic plate moves in that frame by a few cm per year;
the epoch is recorded so the drift can be accounted for when it matters.

Most US sources (NAIP, USGS 3DEP lidar, state orthoimagery, much of the
TIGER-derived OSM data) are NAD83(2011), a plate-fixed frame. Services label
them "WGS 84" through PROJ's identity NAD83 -> WGS 84 step, which is off by
0.9-1.6 m across the conterminous US (the frames diverged by design). Treating
them as the same is a metre-level error, larger than what the atlas aims for.
`shift_m` gives the NAD83(2011) -> ITRF2014 displacement at ATLAS_EPOCH (NGS
14-parameter time-dependent transformation, EPSG:7912 target, via PROJ). Over a
circuit it is constant to well under a millimetre, so it is applied as a
translation.

Accuracy of the step itself: about 2 cm on the stable North American plate.
West of the San Andreas system (Laguna Seca, Long Beach) the ground moves with
the Pacific plate, which NAD83(2011) models only through its survey epoch
(2010.0); the plate-fixed step can then be off by several cm per year since
the source's survey epoch, so DEFORMATION_ZONE_M is added to the error budget
there.
"""
from __future__ import annotations

import math

ATLAS_FRAME = "WGS 84 (G2139) ~ ITRF2014"
ATLAS_EPOCH = 2026.0
STABLE_STEP_M = 0.02          # 1 sigma of the NAD83(2011) -> ITRF2014 step
DEFORMATION_ZONE_M = 0.35     # 95 %, Pacific-plate side of California
DEFORMATION_WEST_OF_LON = -116.0  # crude: coastal California


def shift_m(lon: float, lat: float, frame: str = "NAD83(2011)", epoch: float = ATLAS_EPOCH) -> tuple[float, float]:
    """(east, north) metres to ADD to `frame` coordinates to get atlas coordinates."""
    if frame in ("WGS84", "ITRF2014", "ITRF2020"):
        return 0.0, 0.0
    if frame != "NAD83(2011)":
        raise ValueError(f"unsupported source frame {frame!r}")
    import pyproj
    t = pyproj.Transformer.from_crs("EPSG:6318", "EPSG:7912", always_xy=True)
    x, y, _, _ = t.transform(lon, lat, 0.0, epoch)
    geod = pyproj.Geod(ellps="GRS80")
    az, _, dist = geod.inv(lon, lat, x, y)
    a = math.radians(az)
    return dist * math.sin(a), dist * math.cos(a)


def step_ce95_m(lon: float, frame: str = "NAD83(2011)") -> float:
    """95 % horizontal error of the frame step at this longitude."""
    if frame != "NAD83(2011)":
        return 0.0
    if lon < DEFORMATION_WEST_OF_LON:
        return DEFORMATION_ZONE_M
    return 2.4477 * STABLE_STEP_M

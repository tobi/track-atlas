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

Imagery served by ArcGIS ImageServers (NAIP, the state orthos) is stored in
Web Mercator: the producer's NAD83(2011) was converted to "WGS 84" when the
service was built, with a transformation and epoch the service does not state.
Registration of NAIP to NAD83(2011) lidar at ten venues gives shifts close to
the negative of the NAD83(2011) -> ITRF2014 step, so a real transformation was
applied, not the identity. That frame is "WGS84-service": assumed to be ITRF
at the NAD83(2011) reference epoch 2010.0 (Esri's ITRF08-based transformation),
so only the plate motion since then is applied, and the ambiguity of the epoch
(2002-2010, the ITRF00- and ITRF08-based transformations) plus 0.1 m for the
choice of transformation enters the error budget. When lidar is the reference
this frame does not matter: the imagery is registered onto the lidar, whose
frame (NAD83(2011), identity-labelled in EPT) is stepped instead.

Accuracy of the step itself: about 2 cm on the stable North American plate.
West of the San Andreas system (Laguna Seca, Long Beach) the ground moves with
the Pacific plate, which NAD83(2011) models only through its survey epoch
(2010.0); the plate-fixed step can then be off by several cm per year since
the source's survey epoch, so DEFORMATION_ZONE_M is added to the error budget
there.

France (IGN BD ORTHO, LiDAR HD) is delivered in RGF93 (Lambert-93), the
national realisation of ETRS89 (v1 = ETRF93 at 1993.0; v2/v2b = ETRF2000
at 2009.0/2019.0; EPSG:2154 does not say which): ETRF2000 coordinates, fixed to the stable
Eurasian plate, so the ground does not move in it. `shift_m` for "RGF93" is
the ETRF2000 -> ITRF2014 step at ATLAS_EPOCH (EUREF/IGN Helmert via PROJ,
~0.9 m NE in 2026, growing ~2.5 cm/yr). RGF93_REALISATION_M covers the
difference between the RGF93 realisations a product may really be in (v1,
v2, v2b: a few cm) plus the Helmert parameters' own uncertainty.
"""
from __future__ import annotations

import math

ATLAS_FRAME = "WGS 84 (G2139) ~ ITRF2014"
ATLAS_EPOCH = 2026.0
STABLE_STEP_M = 0.02          # 1 sigma of the NAD83(2011) -> ITRF2014 step
DEFORMATION_ZONE_M = 0.35     # 95 %, Pacific-plate side of California
DEFORMATION_WEST_OF_LON = -116.0  # crude: coastal California
SERVICE_EPOCH = 2010.0        # assumed epoch of a service's NAD83 -> WGS 84 conversion
SERVICE_EPOCH_EARLIEST = 2002.0
SERVICE_TRANSFORM_M = 0.10    # 1 sigma, choice of transformation
RGF93_REALISATION_M = 0.04    # 1 sigma: RGF93 v1 (ETRF93) vs v2/v2b (ETRF2000) 'a few cm' (IGN), + Helmert


def shift_m(lon: float, lat: float, frame: str = "NAD83(2011)", epoch: float = ATLAS_EPOCH) -> tuple[float, float]:
    """(east, north) metres to ADD to `frame` coordinates to get atlas coordinates."""
    if frame in ("WGS84", "ITRF2014", "ITRF2020"):
        return 0.0, 0.0
    if frame == "WGS84-service":
        a = shift_m(lon, lat, "NAD83(2011)", epoch)
        b = shift_m(lon, lat, "NAD83(2011)", SERVICE_EPOCH)
        return a[0] - b[0], a[1] - b[1]
    if frame not in ("NAD83(2011)", "RGF93"):
        raise ValueError(f"unsupported source frame {frame!r}")
    import pyproj
    src = "EPSG:7931" if frame == "RGF93" else "EPSG:6318"   # ETRF2000 geog3D / NAD83(2011)
    t = pyproj.Transformer.from_crs(src, "EPSG:7912", always_xy=True)
    x, y, _, _ = t.transform(lon, lat, 0.0, epoch)
    geod = pyproj.Geod(ellps="GRS80")
    az, _, dist = geod.inv(lon, lat, x, y)
    a = math.radians(az)
    return dist * math.sin(a), dist * math.cos(a)


def step_ce95_m(lon: float, frame: str = "NAD83(2011)", lat: float | None = None) -> float:
    """95 % horizontal error of the frame step at this longitude."""
    if frame == "WGS84-service":
        a = shift_m(lon, lat, "NAD83(2011)", SERVICE_EPOCH)
        b = shift_m(lon, lat, "NAD83(2011)", SERVICE_EPOCH_EARLIEST)
        epoch_range = math.hypot(a[0] - b[0], a[1] - b[1])
        base = math.hypot(epoch_range, 2.4477 * SERVICE_TRANSFORM_M)
        return math.hypot(base, DEFORMATION_ZONE_M) if lon < DEFORMATION_WEST_OF_LON else base
    if frame == "RGF93":
        return 2.4477 * RGF93_REALISATION_M
    if frame != "NAD83(2011)":
        return 0.0
    if lon < DEFORMATION_WEST_OF_LON:
        return DEFORMATION_ZONE_M
    return 2.4477 * STABLE_STEP_M

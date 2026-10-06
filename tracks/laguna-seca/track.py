from lib.dsl import Track, osm

t = Track(
    "laguna-seca",
    "WeatherTech Raceway Laguna Seca",
    aka=["Laguna Seca"],
    country="US",
    series=["imsa"],
    location=dict(
        lat=36.5842,
        lon=-121.7517,
        locality="Monterey, California",
        region="California",
        timezone="America/Los_Angeles",
    ),
    external_ids=dict(imsa_data="laguna-seca"),
    osm=osm([36.5542, -121.7817, 36.6142, -121.7217]),
    lovely=dict(gp="iracing/lagunaseca.json"),
)
t.surface()

# -- gp --------------------------------------------------------------------
lap = t.layout(
    "gp",
    "Full Course",
    length_m=3602,
    direction="anticlockwise",
    lovely="gp",
    start_finish=dict(
        location=[-121.756637, 36.586458],
        note="Pinned at the stitched-centerline origin so the curated replace_corners markers (geometry fractions on this frame) cannot move; the Lovely ranges center on the measured peaks with no systematic shift. Not a surveyed timing line.",
    ),
)
lap.corners([
    dict(number=1, code="1", marker=0.0669, direction="left", scale=6),
    dict(
        number=2,
        code="2",
        official="Andretti Hairpin",
        driver="Andretti Hairpin",
        marker=0.1452,
        direction="left",
        scale=1,
    ),
    dict(number=3, code="3", marker=0.2195, direction="right", scale=3),
    dict(number=4, code="4", marker=0.2959, direction="right", scale=3),
    dict(number=5, code="5", marker=0.4298, direction="left", scale=3),
    dict(number=6, code="6", marker=0.5419, direction="left", scale=3),
    dict(number=7, code="7", marker=0.6541, direction="right", scale=5),
    dict(
        number=8,
        code="8",
        official="The Corkscrew",
        driver="The Corkscrew",
        marker=0.6856,
        direction="left",
        scale=2,
        complex="The Corkscrew",
    ),
    dict(
        number=9,
        code="8A",
        official="The Corkscrew",
        driver="The Corkscrew",
        marker=0.6963,
        direction="right",
        scale=2,
        complex="The Corkscrew",
    ),
    dict(
        number=10,
        code="9",
        official="Rainey Curve",
        driver="Rainey Curve",
        marker=0.7706,
        direction="left",
        scale=3,
    ),
    dict(number=11, code="10", marker=0.836, direction="right", scale=3),
    dict(number=12, code="11", marker=0.913, direction="left", scale=2),
])
lap.unnamed(
    0.6472,
    "left",
    "artefact",
    "R48, +19 deg with the left edge seen on 10% of it; the OSM centerline turns right here (R153), into T7",
)
lap.unnamed(
    0.7978,
    "right",
    "artefact",
    "R76, -13 deg over 26 m where the OSM centerline is straight (R1560, and bending the other way)",
)

from lib.dsl import Track, osm

t = Track(
    "road-america",
    "Road America",
    aka=["Elkhart Lake"],
    country="US",
    series=["imsa"],
    location=dict(
        lat=43.7918,
        lon=-87.9897,
        locality="Elkhart Lake, Wisconsin",
        region="Wisconsin",
        timezone="America/Chicago",
    ),
    external_ids=dict(imsa_data="road-america"),
    osm=osm([43.7618, -88.0197, 43.8218, -87.9597]),
    lovely=dict(gp="iracing/roadamerica-full.json"),
)

# -- gp --------------------------------------------------------------------
lap = t.layout(
    "gp",
    "Full Course",
    length_m=6514,
    direction="clockwise",
    lovely="gp",
    start_finish=dict(
        location=[-87.989626, 43.797797],
        note="Pinned 96 m north of the OSM-alignment origin, where the Lovely corner markers line up with the OSM ref=1..14 turn ways and the centerline curvature peaks (10 corners, mean shift 0.0148 lap, sd ~13 m). Not a surveyed timing line.",
    ),
)
lap.corners([
    dict(number=1, marker=0.1008, direction="right", scale=2),
    dict(number=2, marker=0.1445, direction="right", scale=6),
    dict(number=3, marker=0.1702, direction="right", scale=3),
    dict(number=4, marker=0.2459, direction="right", scale=6),
    dict(number=5, marker=0.3553, direction="left", scale=2),
    dict(number=6, marker=0.4007, direction="left", scale=3),
    dict(number=7, marker=0.4392, direction="right", scale=4),
    dict(number=8, marker=0.5027, direction="left", scale=2),
    dict(
        number=9,
        official="The Carousel",
        driver="Carousel",
        marker=0.5333,
        direction="right",
        scale=3,
        complex="Carousel",
    ),
    dict(
        number=10,
        official="The Carousel",
        driver="Carousel",
        marker=0.5847,
        direction="right",
        scale=3,
        complex="Carousel",
    ),
    dict(
        number=11,
        official="The Kink",
        driver="The Kink",
        marker=0.6601,
        direction="right",
        scale=5,
    ),
    dict(
        number=12,
        official="Canada Corner",
        driver="Canada Corner",
        marker=0.7901,
        direction="right",
        scale=2,
    ),
    dict(number=13, driver="Bill Mitchell Bend", marker=0.8367, direction="left", scale=4),
    dict(number=14, marker=0.8903, direction="right", scale=3),
])

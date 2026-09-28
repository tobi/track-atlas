from lib.dsl import Track, osm

t = Track(
    "lime-rock",
    "Lime Rock Park",
    aka=["Lime Rock"],
    country="US",
    series=["imsa"],
    location=dict(
        lat=41.9277,
        lon=-73.3836,
        locality="Lakeville, Connecticut",
        region="Connecticut",
        timezone="America/New_York",
    ),
    external_ids=dict(imsa_data="lime-rock"),
    osm=osm([41.8977, -73.4136, 41.9577, -73.3536], relation=6429257),
    lovely=dict(gp="iracing/limerock-2019-classic.json"),
)
t.surface()

# -- gp --------------------------------------------------------------------
lap = t.layout(
    "gp",
    "Classic",
    length_m=2462,
    direction="clockwise",
    lovely="gp",
    centerline="relation",
    start_finish=dict(
        location=[-73.380692, 41.928495],
        note="Pinned at the relation's lap origin (Sam Posey Straight) so the curated replace_corners markers (geometry fractions on this frame) cannot move. Not a surveyed timing line.",
    ),
)
lap.corners([
    dict(
        number=1,
        official="Big Bend",
        driver="Big Bend",
        marker=0.0928,
        direction="right",
        scale=3,
        complex="Big Bend",
    ),
    dict(
        number=2,
        official="Big Bend",
        driver="Big Bend",
        marker=0.1808,
        direction="right",
        scale=3,
        complex="Big Bend",
    ),
    dict(
        number=3,
        official="The Lefthander",
        driver="The Left-Hander",
        marker=0.2776,
        direction="left",
        scale=3,
    ),
    dict(
        number=4,
        official="The Righthander",
        driver="The Right-Hander",
        marker=0.3242,
        direction="right",
        scale=3,
    ),
    dict(
        number=5,
        official="Climbing Turn",
        driver="The Uphill",
        marker=0.4993,
        direction="right",
        scale=2,
    ),
    dict(
        number=6,
        official="West Bend",
        driver="West Bend",
        marker=0.655,
        direction="right",
        scale=3,
    ),
    dict(
        number=7,
        official="Diving Turn",
        driver="The Downhill",
        marker=0.7916,
        direction="right",
        scale=4,
    ),
])
lap.unnamed(
    0.5121,
    "left",
    "part_of_corner",
    "South Chicane (L21, +52 deg): the OSM relation 'Lime Rock Park (with Chicane)' takes the South Chicane way here instead of the second Climbing Turn way; same endpoints, up to 24 m apart",
)
lap.unnamed(
    0.5281,
    "right",
    "part_of_corner",
    "South Chicane exit (R30.5, -42 deg), same branch as 0.5125",
)
lap.unnamed(
    0.5868,
    "right",
    "unnumbered_bend",
    "R76, -18 deg where the South Chicane branch rejoins the Climbing Turn line (both OSM ways end at 0.5889); centerline R76 too",
)

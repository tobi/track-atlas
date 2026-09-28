from lib.dsl import Track, osm

t = Track(
    "daytona",
    "Daytona International Speedway",
    aka=["Daytona"],
    country="US",
    series=["imsa"],
    location=dict(
        lat=29.1851,
        lon=-81.0707,
        locality="Daytona Beach, Florida",
        region="Florida",
        timezone="America/New_York",
    ),
    external_ids=dict(imsa_data="daytona"),
    osm=osm([29.1551, -81.1007, 29.2151, -81.0407], relation=5254136),
    lovely=dict(gp="iracing/daytona-2011-road.json"),
)
t.surface()

# -- gp --------------------------------------------------------------------
lap = t.layout(
    "gp",
    "Road Course",
    length_m=5729,
    direction="anticlockwise",
    lovely="gp",
    centerline="relation",
    start_finish=dict(
        location=[-81.072622, 29.1879],
        note="Pinned where the Lovely corner markers line up with the measured curvature peaks (T1, T2, International Horseshoe, the Kink, West Horseshoe, Bus Stop, NASCAR 3-4 within ~40 m); the OSM-derived origin was on the back straight. Not a surveyed timing line.",
    ),
)
lap.summary(
    "Metadata says 'clockwise' but the Daytona road course runs counter-clockwise (NASCAR oval direction); the GeoJSON outline also appears mirrored north-south versus the real circuit (infield turns plotted north of the oval), which would make a CCW track render as clockwise — directions given here are real-world. T7 coordinate looks misplaced in the infield instead of on the NASCAR 2 banking.",
)
lap.corner(1, driver="Turn 1", official="Turn 1", direction="left", scale=2)
lap.corner(2, driver="Turn 2", official="Turn 2", direction="left", scale=3)
lap.corner(
    3,
    driver="International Horseshoe",
    official="International Horseshoe",
    direction="right",
    scale=1,
)
lap.corner(4, driver="The Kink", official="Turn 4 (Kink)", direction="left", scale=5)
lap.corner(5, driver="West Horseshoe", official="West Horseshoe", direction="right", scale=2)
lap.corner(6, driver="NASCAR 1", official="Turn 6 (NASCAR Turn 1)", direction="left", scale=5)
lap.corner(
    7,
    driver="NASCAR 2",
    official="Turn 7 (NASCAR Turn 2)",
    direction="left",
    scale=5,
    error="marker 0.451 then long gap to T8 at 0.67 is expected (backstretch), but T7's coordinate sits in the infield region near the West Horseshoe exit rather than on the oval banking — looks misplaced",
)
lap.corner(
    8,
    driver="Bus Stop entry",
    official="Turn 8",
    complex="Bus Stop (Le Mans Chicane)",
    direction="left",
    scale=4,
)
lap.corner(
    9,
    driver="Bus Stop",
    official="Turn 9",
    complex="Bus Stop (Le Mans Chicane)",
    direction="right",
    scale=3,
)
lap.corner(
    10,
    driver="Bus Stop",
    official="Turn 10",
    complex="Bus Stop (Le Mans Chicane)",
    direction="right",
    scale=3,
)
lap.corner(
    11,
    driver="Bus Stop exit",
    official="Turn 11",
    complex="Bus Stop (Le Mans Chicane)",
    direction="left",
    scale=4,
)
lap.corner(
    12,
    driver="NASCAR 3",
    official="Turn 12 (NASCAR Turns 3-4)",
    direction="left",
    scale=5,
    error="Turn 12 covers both NASCAR 3 and NASCAR 4 banking — a single marker at 0.81 under-represents roughly a quarter mile of continuous banked cornering; consider a second point for NASCAR 4 around 0.87",
)
lap.unnamed(
    0.0517,
    "left",
    "artefact",
    "L/R +-20 deg pair where the pit lane splits off the front stretch (OSM pit way 0.0536-0.0587): the right edge follows the pit apron",
)
lap.unnamed(0.0553, "right", "artefact", "other half of the pit-split pair")
lap.unnamed(
    0.0693,
    "left",
    "part_of_corner",
    "turn-in lobe of T1 (+19 deg, R72) before its R36 apex at 0.085",
)
lap.unnamed(
    0.0997,
    "left",
    "unnumbered_bend",
    "flat +25 deg bend (R65) between T1 and T2; not numbered",
)
lap.unnamed(
    0.1129,
    "right",
    "unnumbered_bend",
    "flat -25 deg bend (R69) before T2; not numbered",
)
lap.unnamed(
    0.4084,
    "left",
    "part_of_corner",
    "second apex of T6: the left that merges the infield onto the NASCAR 1 banking",
)
lap.unnamed(
    0.5686,
    "left",
    "artefact",
    "L/R +-18 deg pair at the banking exit where the edges jump between apron and wall lines; OSM centerline R368/R775 there",
)
lap.unnamed(0.5726, "right", "artefact", "other half of the banking-exit pair")
lap.unnamed(
    0.7601,
    "left",
    "artefact",
    "254 m lobe (+61 deg, R57) where the left edge jumps to the apron line; OSM centerline R196 (the tri-oval banking)",
)
lap.unnamed(
    0.8463,
    "left",
    "artefact",
    "edge jump on the NASCAR 3-4 banking; OSM centerline R252",
)

from lib.dsl import Track, osm

t = Track(
    "circuit-of-the-americas",
    "Circuit of the Americas",
    aka=["COTA"],
    country="US",
    series=["wec", "f1"],
    location=dict(
        lat=30.1366,
        lon=-97.6307,
        locality="Austin, Texas",
        region="Texas",
        timezone="America/Chicago",
    ),
    external_ids=dict(imsa_data="circuit-of-the-americas"),
    osm=osm([30.1066, -97.6607, 30.1666, -97.6007], relation=6537729),
    lovely=dict(gp="lmu/circuit-of-the-americas.json"),
)
t.surface()

# -- gp --------------------------------------------------------------------
lap = t.layout(
    "gp",
    "Grand Prix Circuit",
    length_m=5515,
    direction="anticlockwise",
    lovely="gp",
    centerline="relation",
    start_finish=dict(
        location=[-97.64225, 30.1335372],
        note="OSM relation 6537729 member node 13826373967 (role=finish). The relation's lap started at its role=start node, 0.024 lap later, which put every Lovely lmu marker 90-190 m before its OSM 'Turn N' way.",
    ),
)
lap.corner(1, driver="Big Red", official="Turn 1", direction="left", scale=1, marker=0.1194)
lap.corner(2, official="Turn 2", direction="right", scale=4, marker=0.1536)
lap.corner(3, official="Turn 3", complex="Esses", direction="left", scale=5, marker=0.2119)
lap.corner(4, official="Turn 4", complex="Esses", direction="right", scale=5, marker=0.2299)
lap.corner(5, official="Turn 5", complex="Esses", direction="left", scale=5, marker=0.2454)
lap.corner(6, official="Turn 6", complex="Esses", direction="right", scale=4, marker=0.2647)
lap.corner(7, official="Turn 7", complex="Esses", direction="left", scale=4, marker=0.3123)
lap.corner(8, official="Turn 8", complex="Esses", direction="right", scale=2, marker=0.3463)
lap.corner(9, official="Turn 9", complex="Esses", direction="left", scale=3, marker=0.3591)
lap.corner(10, official="Turn 10", complex="Esses", direction="left", scale=5, marker=0.3962)
lap.corner(11, driver="Hairpin", official="Turn 11", direction="left", scale=1, marker=0.4699)
lap.corner(12, official="Turn 12", direction="left", scale=1, marker=0.6871)
lap.corner(13, official="Turn 13", direction="right", scale=2, marker=0.7281)
lap.corner(14, official="Turn 14", direction="right", scale=4, marker=0.7455)
lap.corner(15, official="Turn 15", direction="left", scale=5, marker=0.7703)
lap.corner(16, official="Turn 16", direction="left", scale=2, marker=0.7803)
lap.corner(17, official="Turn 17", direction="right", scale=5, marker=0.8366)
lap.corner(18, official="Turn 18", direction="right", scale=5, marker=0.8543)
lap.corner(19, official="Turn 19", direction="left", scale=4, marker=0.917)
lap.corner(20, official="Turn 20", direction="left", scale=2, marker=0.9722)
lap.unnamed(
    0.2876,
    "right",
    "part_of_corner",
    "second apex of T6 (R65, -59 deg); both T6 apexes lie inside the OSM 'Turn 6' way 0.2555-0.3023",
)
lap.unnamed(
    0.8171,
    "right",
    "part_of_corner",
    "first apex of T17 (R70, -50 deg) before its R53 apex; OSM 'Turn 17' way 0.8099-0.8468",
)

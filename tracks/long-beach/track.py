from lib.dsl import Track, osm

t = Track(
    "long-beach",
    "Long Beach Street Circuit",
    aka=["Long Beach"],
    country="US",
    series=["imsa"],
    location=dict(
        lat=33.7598,
        lon=-118.189,
        locality="Long Beach, California",
        region="California",
        timezone="America/Los_Angeles",
    ),
    external_ids=dict(imsa_data="long-beach"),
    osm=osm([33.7298, -118.219, 33.7898, -118.159], relation=18052024),
    lovely=dict(gp="iracing/longbeach.json"),
)
t.surface()

# -- gp --------------------------------------------------------------------
lap = t.layout(
    "gp",
    "Street Circuit",
    length_m=3167,
    direction="clockwise",
    lovely="gp",
    start_finish=dict(
        location=[-118.187341, 33.762201],
        note="On Shoreline Drive, 390 m after the hairpin. Placed so the Lovely iracing markers land on the measured peaks: the OSM relation starts 0.212 lap early (Lovely T1 0.223 vs peak 0.4366, T11 hairpin 0.882 vs peak/OSM Hairpin way 0.0928, both +0.212). Not a surveyed timing line.",
    ),
)
lap.corner(1, official="Turn 1", driver=None, direction="left", scale=2)
lap.corner(2, official="Turn 2", driver=None, direction="right", scale=2)
lap.corner(3, official="Turn 3", driver=None, direction="left", scale=3)
lap.corner(4, official="Turn 4", driver=None, direction="right", scale=3)
lap.corner(5, official="Turn 5", driver=None, direction="right", scale=2)
lap.corner(6, official="Turn 6", driver=None, direction="left", scale=2)
lap.corner(7, official="Turn 7", driver=None, direction="left", scale=5)
lap.corner(8, official="Turn 8", driver=None, direction="right", scale=2)
lap.corner(9, official="Turn 9", driver=None, direction="right", scale=3)
lap.corner(10, official="Turn 10", driver=None, direction="left", scale=3)
lap.corner(11, official="Turn 11", driver="The Hairpin", direction="right", scale=1)
lap.unnamed(
    0.245,
    "right",
    "unnumbered_bend",
    "R73, -44 deg, 70 m after T1; real (OSM centerline R76 here) but between Lovely T1 0.223 and T2 0.283, and the circuit has 11 numbered turns",
)
lap.unnamed(
    0.2682,
    "left",
    "unnumbered_bend",
    "R24.5, +39 deg, 45 m before T2; real (centerline R22) but unnumbered in Lovely's 11-turn list",
)
lap.unnamed(
    0.7629,
    "left",
    "artefact",
    "R78, +14 deg; centerline straight (R925), left edge seen on 20% of it",
)
lap.unnamed(
    0.8706,
    "left",
    "part_of_corner",
    "second lobe of the T10 left (+57 deg) 37 m before the hairpin; OSM Hairpin way starts at 0.8775",
)

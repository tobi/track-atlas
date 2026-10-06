from lib.dsl import Track, osm

t = Track(
    "miami",
    "Miami International Autodrome",
    aka=["Miami"],
    country="US",
    series=["f1"],
    location=dict(
        lat=25.958,
        lon=-80.2389,
        locality="Miami Gardens, Florida",
        region="Florida",
        timezone="America/New_York",
    ),
    external_ids=dict(imsa_data="miami"),
    osm=osm([25.928, -80.2689, 25.988, -80.2089]),
    lovely=dict(gp="f12025/miami.json"),
)

# -- gp --------------------------------------------------------------------
lap = t.layout("gp", "Grand Prix Circuit", length_m=5412, direction="clockwise", lovely="gp")
lap.summary("T7 scale should be 4 (fast kink); T11 scale should be 1 (tight hairpin)")
lap.corner(1, driver="Turn 1", official="Turn 1", direction="right", scale=2)
lap.corner(2, driver="Turn 2", official="Turn 2", direction="left", scale=3)
lap.corner(3, driver="Turn 3", official="Turn 3", direction="right", scale=5)
lap.corner(4, driver="Turn 4", official="Turn 4", direction="left", scale=3)
lap.corner(5, driver="Turn 5", official="Turn 5", direction="right", scale=3)
lap.corner(6, driver="Turn 6", official="Turn 6", direction="left", scale=3)
lap.corner(
    7,
    driver="Turn 7",
    official="Turn 7",
    direction="left",
    scale=4,
    error="scale should be 4 not 3 - this is a fast left kink leading into T8",
)
lap.corner(8, driver="Turn 8", official="Turn 8", direction="left", scale=2)
lap.corner(9, driver="Turn 9", official="Turn 9", direction="right", scale=5)
lap.corner(10, driver="Turn 10", official="Turn 10", direction="left", scale=6)
lap.corner(
    11,
    driver="Turn 11",
    official="Turn 11",
    direction="left",
    scale=1,
    error="scale should be 1 not 2 - this is the tight hairpin at the end of the back straight",
)
lap.corner(12, driver="Turn 12", official="Turn 12", direction="right", scale=2)
lap.corner(13, driver="Turn 13", official="Turn 13", direction="left", scale=3)
lap.corner(14, driver="Turn 14", official="Turn 14", direction="left", scale=2)
lap.corner(15, driver="Turn 15", official="Turn 15", direction="right", scale=2)
lap.corner(16, driver="Turn 16", official="Turn 16", direction="left", scale=2)
lap.corner(17, driver="Turn 17", official="Turn 17", direction="left", scale=1)
lap.corner(18, driver="Turn 18", official="Turn 18", direction="left", scale=3)
lap.corner(19, driver="Turn 19", official="Turn 19", direction="right", scale=4)

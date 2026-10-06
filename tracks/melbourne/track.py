from lib.dsl import Track, osm

t = Track(
    "melbourne",
    "Albert Park Circuit",
    aka=["Melbourne", "Albert Park"],
    country="AU",
    series=["f1"],
    location=dict(
        lat=-37.8497,
        lon=144.968,
        locality="Melbourne",
        region="Victoria",
        timezone="Australia/Melbourne",
    ),
    osm=osm([-37.8797, 144.938, -37.8197, 144.998], relation=280443),
    lovely=dict(gp="f12025/melbourne.json"),
)

# -- gp --------------------------------------------------------------------
lap = t.layout("gp", "Grand Prix Circuit", length_m=5278, direction="clockwise", lovely="gp")
lap.summary(None)
lap.corner(1, driver="Turn 1", official="Turn 1", direction="right", scale=2)
lap.corner(2, driver="Turn 2", official="Turn 2", direction="left", scale=3)
lap.corner(3, driver="Turn 3", official="Turn 3", direction="right", scale=2)
lap.corner(4, driver="Turn 4", official="Turn 4", direction="left", scale=2)
lap.corner(5, driver="Turn 5", official="Turn 5", direction="right", scale=3)
lap.corner(6, driver="Turn 6", official="Turn 6", direction="right", scale=2)
lap.corner(7, driver="Turn 7", official="Turn 7", direction="left", scale=4)
lap.corner(8, driver="Turn 8", official="Turn 8", direction="right", scale=5)
lap.corner(9, driver="Lakeside", official="Turn 9", direction="left", scale=4)
lap.corner(10, driver="Turn 10", official="Turn 10", direction="right", scale=3)
lap.corner(11, driver="Turn 11", official="Turn 11", direction="right", scale=2)
lap.corner(12, driver="Turn 12", official="Turn 12", direction="right", scale=2)
lap.corner(13, driver="Turn 13", official="Turn 13", direction="left", scale=2)
lap.corner(14, driver="Turn 14", official="Turn 14", direction="right", scale=2)

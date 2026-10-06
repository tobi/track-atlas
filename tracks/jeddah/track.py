from lib.dsl import Track, osm

t = Track(
    "jeddah",
    "Jeddah Corniche Circuit",
    aka=["Jeddah"],
    country="SA",
    series=["f1"],
    location=dict(lat=21.6319, lon=39.1044, locality="Jeddah", region="Makkah", timezone="Asia/Riyadh"),
    osm=osm([21.6019, 39.0744, 21.6619, 39.1344]),
    lovely=dict(gp="f12025/jeddah.json"),
)

# -- gp --------------------------------------------------------------------
lap = t.layout("gp", "Grand Prix Circuit", length_m=6174, direction="anticlockwise", lovely="gp")
lap.summary(None)
lap.corner(1, driver="Turn 1", official="Turn 1", direction="left", scale=2)
lap.corner(2, driver="Turn 2", official="Turn 2", direction="right", scale=3)
lap.corner(3, driver="Turn 3", official="Turn 3", direction="left", scale=5)
lap.corner(4, driver="Turn 4", official="Turn 4", direction="left", scale=3)
lap.corner(5, driver="Turn 5", official="Turn 5", direction="right", scale=5)
lap.corner(6, driver="Turn 6", official="Turn 6", direction="left", scale=5)
lap.corner(7, driver="Turn 7", official="Turn 7", direction="left", scale=4)
lap.corner(8, driver="Turn 8", official="Turn 8", direction="right", scale=5)
lap.corner(9, driver="Turn 9", official="Turn 9", direction="right", scale=5)
lap.corner(10, driver="Turn 10", official="Turn 10", direction="left", scale=4)
lap.corner(11, driver="Turn 11", official="Turn 11", direction="right", scale=6)
lap.corner(12, driver="Turn 12", official="Turn 12", direction="left", scale=6)
lap.corner(13, driver="Turn 13", official="Turn 13", direction="left", scale=1)
lap.corner(14, driver="Turn 14", official="Turn 14", direction="right", scale=5)
lap.corner(15, driver="Turn 15", official="Turn 15", direction="left", scale=5)
lap.corner(16, driver="Turn 16", official="Turn 16", direction="right", scale=3)
lap.corner(17, driver="Turn 17", official="Turn 17", direction="left", scale=3)
lap.corner(18, driver="Turn 18", official="Turn 18", direction="left", scale=6)
lap.corner(19, driver="Turn 19", official="Turn 19", direction="right", scale=6)
lap.corner(20, driver="Turn 20", official="Turn 20", direction="left", scale=6)
lap.corner(21, driver="Turn 21", official="Turn 21", direction="right", scale=6)
lap.corner(22, driver="Turn 22", official="Turn 22", direction="left", scale=3)
lap.corner(23, driver="Turn 23", official="Turn 23", direction="right", scale=4)
lap.corner(24, driver="Turn 24", official="Turn 24", direction="right", scale=4)
lap.corner(25, driver="Turn 25", official="Turn 25", direction="left", scale=5)
lap.corner(26, driver="Turn 26", official="Turn 26", direction="left", scale=6)
lap.corner(27, driver="Turn 27", official="Turn 27", direction="left", scale=1)

from lib.dsl import Track, osm

t = Track(
    "shanghai",
    "Shanghai International Circuit",
    aka=["Shanghai"],
    country="CN",
    series=["f1"],
    location=dict(
        lat=31.3389,
        lon=121.2197,
        locality="Jiading, Shanghai",
        region="Shanghai",
        timezone="Asia/Shanghai",
    ),
    osm=osm([31.3089, 121.1897, 31.3689, 121.2497], relation=2094941),
    lovely=dict(gp="f12025/shanghai.json"),
)

# -- gp --------------------------------------------------------------------
lap = t.layout("gp", "Grand Prix Circuit", length_m=5451, direction="clockwise", lovely="gp")
lap.summary(
    "Multiple direction errors found: T5, T6, T10, T13, T15 all have incorrect left/right assignments; T1 scale should be 2 not 3",
)
lap.corner(
    1,
    driver="Turn 1",
    official="Turn 1",
    direction="right",
    scale=2,
    error="scale should be 2 not 3 — tight slow corner from slow speed",
)
lap.corner(2, driver="Turn 2", official="Turn 2", direction="right", scale=3)
lap.corner(3, driver="Turn 3", official="Turn 3", direction="left", scale=2)
lap.corner(4, driver="Turn 4", official="Turn 4", direction="left", scale=3)
lap.corner(
    5,
    driver="Turn 5",
    official="Turn 5",
    direction="left",
    scale=5,
    error="direction should be left not right — track curves left at apex",
)
lap.corner(
    6,
    driver="Turn 6",
    official="Turn 6",
    direction="left",
    scale=1,
    error="direction should be left not right — hairpin turns left",
)
lap.corner(7, driver="Turn 7", official="Turn 7", direction="left", scale=6)
lap.corner(8, driver="Turn 8", official="Turn 8", direction="right", scale=5)
lap.corner(9, driver="Turn 9", official="Turn 9", direction="left", scale=2)
lap.corner(
    10,
    driver="Turn 10",
    official="Turn 10",
    direction="right",
    scale=3,
    error="direction should be right not left — examining coordinates shows rightward movement",
)
lap.corner(11, driver="Turn 11", official="Turn 11", direction="left", scale=2)
lap.corner(12, driver="Turn 12", official="Turn 12", direction="right", scale=3)
lap.corner(
    13,
    driver="Turn 13",
    official="Turn 13",
    direction="left",
    scale=4,
    error="direction should be left not right — track sweeps left based on coordinates",
)
lap.corner(14, driver="Turn 14", official="Turn 14", direction="right", scale=1)
lap.corner(
    15,
    driver="Turn 15",
    official="Turn 15",
    direction="left",
    scale=6,
    error="direction should be left not right — slight kink left after T14",
)
lap.corner(16, driver="Turn 16", official="Turn 16", direction="left", scale=3)

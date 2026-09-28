from lib.dsl import Track, osm

t = Track(
    "zandvoort",
    "Circuit Zandvoort",
    aka=["Zandvoort"],
    country="NL",
    series=["f1"],
    location=dict(
        lat=52.3888,
        lon=4.5409,
        locality="Zandvoort",
        region="North Holland",
        timezone="Europe/Amsterdam",
    ),
    osm=osm([52.3588, 4.5109, 52.4188, 4.5709], relation=13545573),
    lovely=dict(gp="f12025/zandvoort.json"),
)

# -- gp --------------------------------------------------------------------
lap = t.layout("gp", "Grand Prix Circuit", length_m=4259, direction="clockwise", lovely="gp")
lap.summary(None)
lap.corner(1, driver="Tarzan", official="Tarzan", direction="right", scale=1)
lap.corner(2, driver="Gerlachbocht", official="Gerlachbocht", direction="right", scale=3)
lap.corner(3, driver="Hugenholtz", official="Hugenholtz", direction="left", scale=1)
lap.corner(
    4,
    driver="Hondenvlak",
    official="Hondenvlak",
    complex="Hondenvlak",
    direction="right",
    scale=5,
)
lap.corner(
    5,
    driver="Hondenvlak",
    official="Hondenvlak",
    complex="Hondenvlak",
    direction="left",
    scale=4,
)
lap.corner(
    6,
    driver="Hondenvlak",
    official="Hondenvlak",
    complex="Hondenvlak",
    direction="right",
    scale=5,
)
lap.corner(7, driver="Scheivlak", official="Scheivlak", direction="right", scale=3)
lap.corner(8, driver="Mastersbocht", official="Mastersbocht", direction="right", scale=3)
lap.corner(9, driver="Renault", official="Renault", direction="right", scale=2)
lap.corner(10, driver="Vodafone", official="Vodafone", direction="left", scale=1)
lap.corner(11, driver="Hugenholtzbocht", official="Hugenholtzbocht", direction="right", scale=2)
lap.corner(12, driver="Hans Ernst", official="Hans Ernst Bocht", direction="left", scale=1)
lap.corner(13, driver="Kumho", official="Kumho", direction="right", scale=3)
lap.corner(
    14,
    driver="Arie Luyendyk",
    official="Arie Luyendyk Bocht",
    direction="right",
    scale=4,
)

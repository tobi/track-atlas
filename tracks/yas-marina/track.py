from lib.dsl import Track, osm

t = Track(
    "yas-marina",
    "Yas Marina Circuit",
    aka=["Abu Dhabi"],
    country="AE",
    series=["f1"],
    location=dict(
        lat=24.4672,
        lon=54.6031,
        locality="Abu Dhabi",
        region="Abu Dhabi",
        timezone="Asia/Dubai",
    ),
    external_ids=dict(imsa_data="yas-marina"),
    osm=osm([24.4372, 54.5731, 24.4972, 54.6331], relation=11378665),
    lovely=dict(gp="f12025/abu-dhabi.json"),
)

# -- gp --------------------------------------------------------------------
lap = t.layout("gp", "Grand Prix Circuit", length_m=5281, direction="anticlockwise", lovely="gp")
lap.summary(None)
lap.corner(5, driver="Hotel", official="Turn 5", direction="left", scale=1)
lap.corner(6, driver="Turn 6", official="Turn 6", direction="left", scale=1)
lap.corner(7, driver="Turn 7", official="Turn 7", direction="right", scale=2)
lap.corner(8, driver="Turn 8", official="Turn 8", direction="left", scale=4)
lap.corner(9, driver="Turn 9", official="Turn 9", direction="left", scale=2)
lap.corner(11, driver="Turn 11", official="Turn 11", direction="right", scale=3)
lap.corner(12, driver="Turn 12", official="Turn 12", direction="right", scale=2)
lap.corner(13, driver="Turn 13", official="Turn 13", direction="left", scale=2)
lap.corner(14, driver="Turn 14", official="Turn 14", direction="left", scale=2)
lap.corner(15, driver="Turn 15", official="Turn 15", direction="right", scale=3)
lap.corner(16, driver="Turn 16", official="Turn 16", direction="right", scale=3)

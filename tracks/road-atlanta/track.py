from lib.dsl import Track, osm

t = Track(
    "road-atlanta",
    "Michelin Raceway Road Atlanta",
    aka=["Road Atlanta"],
    country="US",
    series=["imsa"],
    location=dict(
        lat=34.1413,
        lon=-83.8173,
        locality="Braselton, Georgia",
        region="Georgia",
        timezone="America/New_York",
    ),
    external_ids=dict(imsa_data="road-atlanta"),
    osm=osm([34.1113, -83.8473, 34.1713, -83.7873]),
    lovely=dict(gp="iracing/roadatlanta-full.json"),
)
t.surface()

# -- gp --------------------------------------------------------------------
lap = t.layout("gp", "Full Course", length_m=4088, direction="clockwise", lovely="gp")
lap.corner(1, code="1", official=None, driver=None, direction="right", marker=0.0858, scale=3)
lap.corner(2, code="2", official=None, driver=None, direction="left", marker=0.1713, scale=4)
lap.corner(3, code="3", official=None, driver=None, direction="right", marker=0.1856, scale=3)
lap.corner(4, code="4", official=None, driver=None, direction="left", marker=0.2209, scale=4)
lap.corner(
    5,
    code="Esses",
    official="The Esses",
    driver="The Esses",
    direction="right",
    marker=0.2559,
    scale=4,
)
lap.corner(6, code="5", official=None, driver=None, direction="left", marker=0.3323, scale=3)
lap.corner(7, code="6", official=None, driver=None, direction="right", marker=0.4718, scale=3)
lap.corner(8, code="7", official=None, driver=None, direction="right", marker=0.5092, scale=1)
lap.corner(9, code="8", official=None, driver=None, direction="left", marker=0.5638, scale=6)
lap.corner(10, code="9", official=None, driver=None, direction="right", marker=0.7213, scale=6)
lap.corner(
    11,
    code="10A",
    official=None,
    driver=None,
    direction="left",
    marker=0.842,
    scale=2,
    complex="Turn 10",
)
lap.corner(
    12,
    code="10B",
    official=None,
    driver=None,
    direction="right",
    marker=0.8617,
    scale=3,
    complex="Turn 10",
)
lap.corner(13, code="11", official=None, driver=None, direction="right", marker=0.8985, scale=3)
lap.corner(14, code="12", official=None, driver=None, direction="right", marker=0.9574, scale=3)

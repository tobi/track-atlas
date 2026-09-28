from lib.dsl import Track, osm

t = Track(
    "baku",
    "Baku City Circuit",
    aka=["Baku"],
    country="AZ",
    series=["f1"],
    location=dict(lat=40.3725, lon=49.8533, locality="Baku", region="Baku", timezone="Asia/Baku"),
    osm=osm([40.3425, 49.8233, 40.4025, 49.8833], relation=11266687),
    lovely=dict(gp="f12025/baku-azerbaijan.json"),
)

# -- gp --------------------------------------------------------------------
lap = t.layout("gp", "Grand Prix Circuit", length_m=6003, direction="anticlockwise", lovely="gp")
lap.summary(
    "Multiple direction errors in corners 1, 2, 3, 7, 15, 16, 18, 20 - appears anticlockwise direction interpretation was inverted in several places",
)
lap.corner(
    1,
    driver="Turn 1",
    official="Turn 1",
    direction="right",
    scale=2,
    error="corner 1 direction should be right not left - track turns right after start/finish straight",
)
lap.corner(
    2,
    driver="Turn 2",
    official="Turn 2",
    direction="right",
    scale=3,
    error="corner 2 direction should be right not left - continues right-hand sweep; scale should be 3 (medium-speed)",
)
lap.corner(
    3,
    driver="Turn 3",
    official="Turn 3",
    direction="right",
    scale=4,
    error="corner 3 direction should be right not left - still part of uphill right sequence; scale should be 4 (fast corner)",
)
lap.corner(
    7,
    driver="Turn 7",
    official="Turn 7",
    direction="left",
    scale=2,
    error="corner 7 direction should be left not right - this is the left-hander before the castle section",
)
lap.corner(
    8,
    driver="Castle",
    official="Turn 8",
    complex="Castle Section",
    direction="left",
    scale=1,
)
lap.corner(
    9,
    driver="Castle",
    official="Turn 9",
    complex="Castle Section",
    direction="right",
    scale=2,
)
lap.corner(
    10,
    driver="Castle",
    official="Turn 10",
    complex="Castle Section",
    direction="left",
    scale=3,
)
lap.corner(
    11,
    driver="Castle",
    official="Turn 11",
    complex="Castle Section",
    direction="right",
    scale=3,
)
lap.corner(12, driver="Turn 12", official="Turn 12", direction="left", scale=2)
lap.corner(
    15,
    driver="Turn 15",
    official="Turn 15",
    direction="right",
    scale=3,
    error="corner 15 direction should be right not left - this is the right-hander after the long straight",
)
lap.corner(
    16,
    driver="Turn 16",
    official="Turn 16",
    direction="right",
    scale=1,
    error="corner 16 direction should be right not left; scale should be 1 (tight 90-degree right-hander)",
)
lap.corner(
    18,
    driver="Turn 18",
    official="Turn 18",
    direction="right",
    scale=5,
    error="corner 18 direction should be right not left - this is the fast right kink on back straight",
)
lap.corner(
    20,
    driver="Turn 20",
    official="Turn 20",
    direction="left",
    scale=4,
    error="corner 20 direction should be left not right; scale should be 4 (fast final corner onto main straight)",
)

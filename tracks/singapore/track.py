from lib.dsl import Track, osm

t = Track(
    "singapore",
    "Marina Bay Street Circuit",
    aka=["Singapore", "Marina Bay"],
    country="SG",
    series=["f1"],
    location=dict(
        lat=1.2914,
        lon=103.864,
        locality="Singapore",
        region="Singapore",
        timezone="Asia/Singapore",
    ),
    osm=osm([1.2614, 103.834, 1.3214, 103.894], relation=421263),
    lovely=dict(gp="f12025/singapore.json"),
)

# -- gp --------------------------------------------------------------------
lap = t.layout("gp", "Grand Prix Circuit", length_m=4940, direction="anticlockwise", lovely="gp")
lap.summary(None)
lap.corner(1, driver="Sheares", official="Sheares Turn", direction="left", scale=1)
lap.corner(7, driver="Memorial", official="Memorial Corner", direction="left", scale=2)
lap.corner(8, driver="Stamford", official="Stamford Corner", direction="right", scale=2)
lap.corner(9, driver="Padang", official="Padang Corner", direction="left", scale=2)
lap.corner(10, driver="Singapore Sling", official="Singapore Sling", direction="left", scale=2)
lap.corner(14, driver="Connaught", official="Connaught Drive", direction="right", scale=2)
lap.corner(16, driver="Anderson Bridge", official="Anderson Bridge", direction="right", scale=2)
lap.corner(17, driver="Esplanade", official="Esplanade Drive", direction="left", scale=3)
lap.corner(
    18,
    driver="Raffles Boulevard",
    official="Raffles Boulevard",
    direction="left",
    scale=2,
)

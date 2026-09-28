from lib.dsl import Track, osm

t = Track(
    "indianapolis",
    "Indianapolis Motor Speedway",
    aka=["IMS", "The Brickyard"],
    country="US",
    series=["imsa"],
    location=dict(
        lat=39.795,
        lon=-86.2346,
        locality="Speedway, Indiana",
        region="Indiana",
        timezone="America/Indiana/Indianapolis",
    ),
    external_ids=dict(imsa_data="indianapolis"),
    osm=osm([39.765, -86.2646, 39.825, -86.2046], relation=20573734),
    lovely=dict(gp="iracing/indianapolis-2022-road.json"),
)
t.surface()
t.bridge(
    "right",
    0.1,
    0.167,
    "pit exit lane merges beside the front straight without a painted line; the imagery edge follows the pit lane's outer side",
)
t.bridge(
    "left",
    0.125,
    0.167,
    "the oval continues past road-course T1; no painted line, the imagery edge wanders onto the oval",
)

# -- gp --------------------------------------------------------------------
lap = t.layout("gp", "Road Course", length_m=3925, direction="clockwise", lovely="gp")

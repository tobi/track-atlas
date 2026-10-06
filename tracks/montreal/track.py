from lib.dsl import Track, osm

t = Track(
    "montreal",
    "Circuit Gilles Villeneuve",
    aka=["Montreal"],
    country="CA",
    series=["f1"],
    location=dict(
        lat=45.5035,
        lon=-73.5227,
        locality="Montreal, Quebec",
        region="Quebec",
        timezone="America/Toronto",
    ),
    external_ids=dict(imsa_data="montreal"),
    osm=osm([45.4735, -73.5527, 45.5335, -73.4927], relation=284595),
    lovely=dict(gp="f12025/montreal.json"),
)

# -- gp --------------------------------------------------------------------
lap = t.layout("gp", "Grand Prix Circuit", length_m=4361, direction="clockwise", lovely="gp")
lap.summary(
    "Multiple direction errors throughout - appears all directions are inverted; T1-T2 should be marked as Senna S complex; T13-T14 should be marked as Wall of Champions complex; T8 naming issue",
)
lap.corner(
    1,
    driver="Senna S",
    official="Turn 1",
    complex="Senna S",
    direction="right",
    scale=2,
    error="direction should be right not left - car turns right at apex",
)
lap.corner(
    2,
    driver="Senna S",
    official="Turn 2",
    complex="Senna S",
    direction="left",
    scale=2,
    error="direction should be left not right - car turns left at apex; scale should be 2 not 1 - not a tight hairpin, more of a medium-slow corner",
)
lap.corner(
    3,
    driver="Turn 3",
    official="Turn 3",
    direction="left",
    scale=2,
    error="direction should be left not right - reviewing track geometry shows left turn here",
)
lap.corner(
    4,
    driver="Turn 4",
    official="Turn 4",
    direction="right",
    scale=3,
    error="direction should be right not left - car turns right at this apex",
)
lap.corner(
    6,
    driver="Turn 6",
    official="Turn 6",
    direction="right",
    scale=2,
    error="direction should be right not left based on track geometry",
)
lap.corner(
    7,
    driver="Turn 7",
    official="Turn 7",
    direction="left",
    scale=3,
    error="direction should be left not right - car turns left here",
)
lap.corner(
    8,
    driver="Hairpin",
    official="Turn 8",
    direction="left",
    scale=1,
    error="direction should be left not right - this is actually the approach to the hairpin complex; commonly called just 'Hairpin' not 'Pont de la Concorde'",
)
lap.corner(
    9,
    driver="Turn 9",
    official="Turn 9",
    direction="right",
    scale=3,
    error="direction should be right not left",
)
lap.corner(
    10,
    driver="Hairpin",
    official="L'Epingle",
    direction="left",
    scale=1,
    error="direction should be left not right - the actual hairpin apex turns left",
)
lap.corner(
    11,
    driver="Turn 11",
    official="Turn 11",
    direction="right",
    scale=5,
    error="direction should be right not left",
)
lap.corner(
    12,
    driver="Turn 12",
    official="Turn 12",
    direction="left",
    scale=6,
    error="direction should be left not right - barely a kink left",
)
lap.corner(
    13,
    driver="Wall of Champions",
    official="Turn 13",
    complex="Wall of Champions",
    direction="left",
    scale=2,
    error="direction should be left not right - final chicane left-hander",
)
lap.corner(
    14,
    driver="Wall of Champions",
    official="Turn 14",
    complex="Wall of Champions",
    direction="right",
    scale=2,
    error="direction should be right not left - final chicane right-hander",
)

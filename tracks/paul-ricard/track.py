from lib.dsl import Track, osm

t = Track(
    "paul-ricard",
    "Circuit Paul Ricard",
    aka=["Le Castellet"],
    country="FR",
    series=["elms"],
    location=dict(
        lat=43.2503,
        lon=5.7883,
        locality="Le Castellet",
        region="Provence-Alpes-Cote d'Azur",
        timezone="Europe/Paris",
    ),
    external_ids=dict(imsa_data="paul-ricard"),
    osm=osm([43.2203, 5.7583, 43.2803, 5.8183], relation=10316343),
    lovely=dict(gp="assettocorsacompetizione/paul-ricard.json"),
)

# -- gp --------------------------------------------------------------------
lap = t.layout("gp", "Grand Prix Circuit", length_m=5770, direction="clockwise", lovely="gp")
lap.summary(
    "Turns 1 and 2 share identical coordinates despite different markers; typo in Turn 8 name (Courde→Courbe)",
)
lap.corner(
    1,
    driver="Virage de la Verrerie",
    official="Virage de la Verrerie",
    direction="right",
    scale=3,
    error="Corners 1 and 2 have identical coordinates [5.785492, 43.254774] but marker 0.1 vs 0.133 - coordinates should differ",
)
lap.corner(
    2,
    driver="Virage de la Verrerie",
    official="Virage de la Verrerie",
    direction="left",
    scale=3,
    error="Same coordinate as Turn 1 but should be further along track around marker 0.133",
)
lap.corner(
    3,
    driver="Virage de l'Hotel",
    official="Virage de l'Hotel",
    direction="right",
    scale=2,
)
lap.corner(
    4,
    driver="Saint Baume",
    official="Virage de Saint Baume",
    direction="right",
    scale=4,
)
lap.corner(5, driver="Virage du Camp", official="Virage du Camp", direction="left", scale=3)
lap.corner(6, driver="Virage du Camp", official="Virage du Camp", direction="right", scale=4)
lap.corner(
    7,
    driver="Sainte-Baume",
    official="Virage de la Sainte-Baume",
    direction="left",
    scale=5,
)
lap.corner(
    8,
    driver="Signes",
    official="Courbe de Signes",
    direction="right",
    scale=6,
    error="Typo in current name: 'Courde' should be 'Courbe'",
)
lap.corner(
    9,
    driver="Beausset",
    official="Double Droite de Beausset",
    direction="right",
    scale=4,
)
lap.corner(10, driver="Bendor", official="Virage de Bendor", direction="left", scale=2)
lap.corner(11, driver="Garbalan", official="Courbe du Garbalan", direction="right", scale=5)
lap.corner(12, driver="La Tour", official="Virage de la Tour", direction="left", scale=4)
lap.corner(13, driver="Pont", official="Virage du Pont", direction="right", scale=2)

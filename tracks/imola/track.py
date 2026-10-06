from lib.dsl import Track, osm

t = Track(
    "imola",
    "Autodromo Enzo e Dino Ferrari",
    aka=["Imola"],
    country="IT",
    series=["wec", "elms", "f1"],
    location=dict(
        lat=44.338,
        lon=11.708,
        locality="Imola",
        region="Emilia-Romagna",
        timezone="Europe/Rome",
    ),
    external_ids=dict(imsa_data="imola"),
    osm=osm([44.308, 11.678, 44.368, 11.738], relation=9291096),
    lovely=dict(gp="lmu/autodromo-enzo-e-dino-ferrari.json"),
)

# -- gp --------------------------------------------------------------------
lap = t.layout("gp", "Grand Prix Circuit", length_m=4909, direction="anticlockwise", lovely="gp")
lap.summary(
    "Variante Bassa name attached to Turn 1 but belongs to Turn 19; T3 scale overrated (chicane element marked 5), T11 scale underrated (Acque Minerali entry marked 6), T16 marker/coordinate appears too late (sits at Rivazza turn-in).",
)
lap.corner(
    1,
    direction="right",
    scale=6,
    error="named 'Variante Bassa' but the Variante Bassa is the right kink BEFORE the start line (Turn 19 at marker 0.94); Turn 1 is just an unnamed gentle kink after the line — name should move to T19",
)
lap.corner(
    2,
    driver="Tamburello",
    official="Variante Tamburello",
    complex="Tamburello",
    direction="left",
    scale=3,
)
lap.corner(
    3,
    driver="Tamburello",
    official="Variante Tamburello",
    complex="Tamburello",
    direction="right",
    scale=3,
    error="current scale 5 is too fast — this is the middle element of a slow/medium chicane taken in 3rd-4th gear",
)
lap.corner(
    4,
    driver="Tamburello",
    official="Variante Tamburello",
    complex="Tamburello",
    direction="left",
    scale=4,
)
lap.corner(
    5,
    driver="Villeneuve",
    official="Variante Villeneuve",
    complex="Villeneuve",
    direction="left",
    scale=5,
)
lap.corner(
    6,
    driver="Villeneuve",
    official="Variante Villeneuve",
    complex="Villeneuve",
    direction="right",
    scale=3,
    error="current scale 4 slightly fast — the right-hand second element of Villeneuve is the slower part of the chicane",
)
lap.corner(7, driver="Tosa", official="Tosa", direction="left", scale=1)
lap.corner(9, driver="Piratella", official="Piratella", direction="left", scale=4)
lap.corner(
    11,
    driver="Acque Minerali 1",
    official="Acque Minerali",
    complex="Acque Minerali",
    direction="right",
    scale=4,
    error="current scale 6 underrates it — this is the first proper right of the Acque Minerali double-right, not a kink",
)
lap.corner(
    12,
    driver="Acque Minerali 2",
    official="Acque Minerali",
    complex="Acque Minerali",
    direction="right",
    scale=3,
)
lap.corner(
    14,
    driver="Variante Alta",
    official="Variante Alta",
    complex="Variante Alta",
    direction="right",
    scale=3,
)
lap.corner(
    15,
    driver="Variante Alta",
    official="Variante Alta",
    complex="Variante Alta",
    direction="left",
    scale=3,
)
lap.corner(
    16,
    direction="right",
    scale=6,
    error="coordinate [11.7248, 44.3438] sits essentially at the Rivazza 1 turn-in point; the gentle right curvature on the downhill run is earlier (~marker 0.78, around lon 11.722-11.723) — marker/coord look late",
)
lap.corner(
    17,
    driver="Rivazza 1",
    official="Rivazza",
    complex="Rivazza",
    direction="left",
    scale=3,
)
lap.corner(
    18,
    driver="Rivazza 2",
    official="Rivazza",
    complex="Rivazza",
    direction="left",
    scale=3,
)
lap.corner(
    19,
    driver="Variante Bassa",
    official="Variante Bassa",
    direction="right",
    scale=6,
    error="this is the actual Variante Bassa (right kink before the start line) — the name is currently misassigned to Turn 1",
)

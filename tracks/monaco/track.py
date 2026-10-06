from lib.dsl import Track, osm

t = Track(
    "monaco",
    "Circuit de Monaco",
    aka=["Monte Carlo"],
    country="MC",
    series=["f1"],
    location=dict(
        lat=43.7347,
        lon=7.4206,
        locality="Monte Carlo",
        region="Monaco",
        timezone="Europe/Monaco",
    ),
    osm=osm([43.7047, 7.3906, 43.7647, 7.4506], relation=148194),
    lovely=dict(gp="f12025/monaco.json"),
)

# -- gp --------------------------------------------------------------------
lap = t.layout("gp", "Grand Prix Circuit", length_m=3337, direction="clockwise", lovely="gp")
lap.summary(
    "Multiple direction errors: T3, T6, T7, T10, T15, T16, T17, T19 have incorrect directions. T5-T7 naming issues around Mirabeau/Portier. T13-T16 should use 'Swimming Pool' not 'Pool' as complex.",
)
lap.corner(1, driver="Sainte Devote", official="Sainte Dévote", direction="right", scale=2)
lap.corner(
    2,
    driver="Beau Rivage",
    official="Beau Rivage",
    direction="left",
    scale=6,
    error="T2 is barely a corner — more of a kink after the climb. Scale should be 6, not 5",
)
lap.corner(
    3,
    driver="Massenet",
    official="Massenet",
    direction="right",
    scale=3,
    error="T3 direction should be right, not left — cars turn right into Massenet",
)
lap.corner(4, driver="Casino", official="Casino Square", direction="right", scale=3)
lap.corner(
    5,
    driver="Mirabeau",
    official="Mirabeau",
    direction="right",
    scale=2,
    error="T5 is called just 'Mirabeau' by drivers, not 'Mirabeau Haute'",
)
lap.corner(
    6,
    driver="Fairmont Hairpin",
    official="Grand Hotel Hairpin",
    direction="right",
    scale=1,
    error="T6 direction should be right, not left — the hairpin turns right. Also, commonly called 'Fairmont Hairpin' or 'Loews Hairpin' colloquially (hotel sponsor name)",
)
lap.corner(
    7,
    driver="Portier",
    official="Portier",
    direction="left",
    scale=3,
    error="T7 is not 'Mirabeau Bas' — it's the exit of the hairpin leading down to Portier. Direction should be left, scale 3-4 (medium-fast kink)",
)
lap.corner(
    8,
    driver="Portier",
    official="Portier",
    direction="right",
    scale=2,
    error="T8 is the actual Portier corner before tunnel entry",
)
lap.corner(
    9,
    driver="Tunnel",
    official="Tunnel Entry",
    direction="right",
    scale=5,
    error="T9 is called 'Tunnel' or 'Tunnel Kink' — the fast right-hander inside/entering the tunnel",
)
lap.corner(
    10,
    driver="Nouvelle Chicane",
    official="Nouvelle Chicane",
    complex="Nouvelle Chicane",
    direction="right",
    scale=2,
    error="T10 first part of chicane turns right, not left",
)
lap.corner(
    11,
    driver="Nouvelle Chicane",
    official="Nouvelle Chicane",
    complex="Nouvelle Chicane",
    direction="left",
    scale=2,
    error="T11 direction should be left (second part of chicane)",
)
lap.corner(12, driver="Tabac", official="Tabac", direction="left", scale=3)
lap.corner(
    13,
    driver="Swimming Pool",
    official="Louis Chiron",
    complex="Swimming Pool",
    direction="left",
    scale=3,
    error="T13 is part of the Swimming Pool section — drivers rarely say 'Louis Chiron', they say 'Swimming Pool' or 'Piscine'",
)
lap.corner(
    14,
    driver="Swimming Pool",
    official="Swimming Pool",
    complex="Swimming Pool",
    direction="right",
    scale=2,
    error="T14-16 are all part of 'Swimming Pool' complex, not 'Pool'",
)
lap.corner(
    15,
    driver="Swimming Pool",
    official="Swimming Pool",
    complex="Swimming Pool",
    direction="left",
    scale=2,
    error="T15 direction should be left (middle of swimming pool chicane)",
)
lap.corner(
    16,
    driver="Swimming Pool",
    official="Swimming Pool",
    complex="Swimming Pool",
    direction="right",
    scale=3,
    error="T16 direction should be right (exit of swimming pool section)",
)
lap.corner(
    17,
    driver="Rascasse",
    official="La Rascasse",
    direction="left",
    scale=1,
    error="T17 direction should be left, not right — Rascasse is a slow left hairpin. Also drivers typically drop 'La' and just say 'Rascasse'",
)
lap.corner(
    18,
    driver="Anthony Noghes",
    official="Virage Anthony Noghès",
    direction="right",
    scale=3,
    error="T18 is typically considered the main Anthony Noghes corner",
)
lap.corner(
    19,
    driver="Anthony Noghes",
    official="Virage Anthony Noghès",
    direction="left",
    scale=4,
    error="T19 direction should be left — it's the exit kink onto the start/finish straight",
)

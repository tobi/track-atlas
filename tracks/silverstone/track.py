from lib.dsl import Track, osm

t = Track(
    "silverstone",
    "Silverstone Circuit",
    aka=["Silverstone", "The Home of British Motor Racing"],
    country="GB",
    series=["f1", "wec", "elms"],
    location=dict(
        lat=52.0733,
        lon=-1.0147,
        locality="Silverstone, Northamptonshire",
        region="England",
        timezone="Europe/London",
    ),
    wikidata="Q180969",
    external_ids=dict(imsa_data="silverstone"),
    osm=osm([52.064, -1.034, 52.082, -0.997], relation=51160),
    lovely=dict(gp="f12025/silverstone.json"),
)
t.note(
    "Silverstone GP. Lovely gives colloquial names but no numbers and repeats names across multi-apex complexes. We layer in numbered grouping via complex. official names largely match colloquial here (British circuits mostly use the colloquial name officially).",
)

# -- gp --------------------------------------------------------------------
lap = t.layout(
    "gp",
    "Grand Prix Circuit",
    aka=["Arena GP"],
    length_m=5891,
    direction="clockwise",
    active_years="2011-",
    lovely="gp",
)
lap.summary(
    "Three pairs of corners (10/11, 12/13, 16/17) have duplicate coordinates; T11 misnamed Maggotts (should be Becketts) and 'Maggots' misspelled throughout; T9 Copse and T1 Abbey severity badly understated; complexes for T1-2 spurious and T3-5 should be 'Arena'; T17 should be Club not Vale",
)
lap.corner(
    1,
    official="Abbey",
    driver="Abbey",
    direction="right",
    scale=5,
    error="scale 3 is too severe — Abbey is taken near-flat in F1, should be 5",
)
lap.corner(
    2,
    official="Farm Curve",
    complex=None,
    driver="Farm",
    direction="left",
    scale=5,
    error="complex 'Abbey / Farm' should be null — drivers don't refer to Abbey-Farm as a single unit (and T1 has complex null, so the pairing is inconsistent anyway)",
)
lap.corner(
    3,
    official="Village",
    complex="Arena",
    driver="Village",
    direction="right",
    scale=2,
    error="complex name 'Village / The Loop / Aintree' is not what drivers say — this section is collectively called the 'Arena'",
)
lap.corner(
    4,
    official="The Loop",
    complex="Arena",
    driver="The Loop",
    direction="left",
    scale=1,
    error="The Loop is the slowest corner on the circuit, a tight ~150° left — scale should be 1, not 2; complex should be 'Arena'",
)
lap.corner(
    5,
    official="Aintree",
    complex="Arena",
    driver="Aintree",
    direction="left",
    scale=4,
    error="Aintree is a fast left onto the Wellington Straight — scale 4 rather than 3; complex should be 'Arena'",
)
lap.corner(6, official="Brooklands")
lap.corner(
    7,
    official="Luffield",
    driver="Luffield",
    direction="right",
    scale=2,
    error="scale 1 overstates it — Luffield is a long slow right but not a hairpin, scale 2 fits better",
)
lap.corner(8, official="Woodcote")
lap.corner(
    9,
    official="Copse",
    driver="Copse",
    direction="right",
    scale=5,
    error="scale 2 is badly wrong — Copse is one of the fastest corners on the calendar, taken near-flat in F1, should be 5",
)
lap.corner(
    10,
    official="Maggotts",
    complex="Maggotts-Becketts-Chapel",
    driver="Maggotts",
    direction="left",
    scale=6,
    error="colloquial spelled 'Maggots' — correct spelling is 'Maggotts'; the first left is barely a deflection taken flat, scale 6; also shares identical coordinates with T11 — one of the two points is misplaced",
)
lap.corner(
    11,
    official="Becketts",
    complex="Maggotts-Becketts-Chapel",
    driver="Becketts",
    direction="right",
    scale=4,
    error="named 'Maggots' but on the official circuit map T11 is the first part of Becketts (T10 is Maggotts, T11-13 Becketts); spelling also wrong; coordinate is a duplicate of T10",
)
lap.corner(
    12,
    official="Becketts",
    complex="Maggotts-Becketts-Chapel",
    driver="Becketts",
    direction="left",
    scale=4,
    error="shares identical coordinates with T13 — apex points should be distinct; scale 4 fits the fast left better than 3",
)
lap.corner(
    13,
    official="Becketts",
    complex="Maggotts-Becketts-Chapel",
    driver="Becketts",
    direction="right",
    scale=3,
    error="coordinate is a duplicate of T12 — one of the two points is misplaced",
)
lap.corner(14, official="Chapel", complex="Maggotts-Becketts-Chapel")
lap.corner(
    15,
    official="Stowe",
    driver="Stowe",
    direction="right",
    scale=4,
    error="Stowe is a fast right at the end of Hangar Straight — scale 4 rather than 3",
)
lap.corner(
    16,
    official="Vale",
    complex=None,
    driver="Vale",
    direction="left",
    scale=2,
    error="shares identical coordinates with T17 — the left (T16) and right (T17) apexes are clearly separate points on track",
)
lap.corner(
    17,
    official="Club",
    complex="Club",
    driver="Club",
    direction="right",
    scale=2,
    error="on the official map T17 is the first part of Club, not Vale (T16 is Vale, T17-18 Club); coordinate is a duplicate of T16",
)
lap.corner(
    18,
    official="Club",
    complex="Club",
    driver="Club",
    direction="right",
    scale=3,
    error="Club exit is a long opening right onto the Hamilton Straight — scale 3 rather than 2",
)

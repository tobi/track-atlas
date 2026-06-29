"""Shared label-layer conventions for the atlas pipeline.

The naming model is a base identifier plus any number of sparse overlay label
layers:

  - Every corner point has a ``code`` (the trackside identifier: "17", or
    "5a"/"5b" when an apex is split) and an always-present ``numbered`` label
    rendered as "Turn <code>". That is the base layer; it covers unnamed corners
    too.
  - Named overlays ("official", "driver", "historical", ...) appear in an
    item's ``labels`` only when a name is actually known. An unnamed corner -- a
    kink drivers don't talk about -- carries only ``numbered``.
  - A layout picks a default display layer (``label_default``, usually
    "driver"). Display resolves in exactly two steps: the default layer if
    present, else the ``numbered`` identifier. It does NOT fall through other
    named layers -- an absent default-layer name means drivers just use the
    number (e.g. Sebring T17 is officially "Sunset Bend" but drivers say
    "Turn 17").

Layer codes follow conventions so tracks don't diverge; clients enumerate a
track's ``label_layers`` registry to offer the user a layer to display.
"""
from __future__ import annotations

# Canonical labels for the 1-6 Lovely severity scale (kept as an int in the
# data; clients render the word). 1 = tightest/slowest, 6 = barely a corner.
SCALE_LABELS = {
    1: "Hairpin",
    2: "Slow",
    3: "Medium",
    4: "Fast",
    5: "Very fast",
    6: "Kink",
}

# Well-known name-layer codes and their human labels / descriptions. Tracks may
# add others (any ^[a-z][a-z0-9_]*$ code); these are the conventional ones.
LAYER_META = {
    "numbered":   {"label": "Numbered",   "description": "Sequential 'Turn N' identifier (always present)."},
    "official":   {"label": "Official",   "description": "Circuit / governing-body name."},
    "driver":     {"label": "Driver",     "description": "What drivers actually call it."},
    "historical": {"label": "Historical", "description": "A former name still in common use."},
    "sponsor":    {"label": "Sponsor",    "description": "Current sponsored / commercial name."},
    "local":      {"label": "Local",      "description": "Regional / fan nickname."},
}

# Layers that always exist in a track's registry, in display order.
MANDATORY_LAYERS = ["numbered", "official"]
DEFAULT_LAYER = "driver"
# Preferred ordering of layers in the registry / UI columns.
LAYER_ORDER = ["numbered", "official", "driver", "historical", "sponsor", "local"]


def numbered_for(code: str) -> str:
    """The 'numbered' identifier string for a corner code ('17' -> 'Turn 17')."""
    return f"Turn {code}"


def resolve_name(names: dict, default_layer: str = DEFAULT_LAYER) -> str:
    """Display name: the default layer if the corner has it, else the numbered
    identifier. No fall-through to other named layers (see module docstring)."""
    return names.get(default_layer) or names["numbered"]


def build_registry(layer_codes) -> dict:
    """Build a track-level label_layers registry from the set of layer codes that
    actually appear on its items, always including the mandatory layers and
    ordered by LAYER_ORDER (unknown codes appended alphabetically)."""
    present = set(layer_codes) | set(MANDATORY_LAYERS)
    ordered = [c for c in LAYER_ORDER if c in present]
    ordered += sorted(c for c in present if c not in LAYER_ORDER)
    reg = {}
    for code in ordered:
        meta = LAYER_META.get(code, {"label": code.replace("_", " ").title()})
        reg[code] = dict(meta)
    return reg

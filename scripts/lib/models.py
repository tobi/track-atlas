"""Pydantic models for a track-atlas track.json — the single source of truth.

These models *define* the schema: `scripts/build_schema.py` emits
`schema/track.schema.json` from them, and `scripts/verify.py` validates every
track against them. Structural invariants (sequential corner numbers, unique
codes, contiguous complexes, mandatory/declared name layers, the naming model)
live here as validators. Geometry/alignment checks that need the GeoJSON and the
filesystem stay in verify.py.

Run anything that imports this under uv (pydantic is a project dependency):
    uv run python scripts/verify.py
"""
from __future__ import annotations

from collections import defaultdict
from typing import Annotated, Literal, Optional

from pydantic import (
    BaseModel, ConfigDict, Field, StringConstraints,
    field_validator, model_validator,
)

from .naming import DEFAULT_LAYER, MANDATORY_LAYERS

# --- scalar / constrained types ----------------------------------------------
Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]
LayerCode = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$")]
LonLat = Annotated[
    list[float],
    Field(min_length=2, max_length=2,
          description="[longitude, latitude] in GeoJSON axis order (WGS84)."),
]
Fraction = Annotated[float, Field(ge=0.0, le=1.0,
                                  description="Lap fraction in [0,1].")]


class Strict(BaseModel):
    """Base: reject unknown keys so typos surface instead of silently passing."""
    model_config = ConfigDict(extra="forbid")


# --- leaf objects ------------------------------------------------------------
class Location(Strict):
    lat: float
    lon: float
    locality: Optional[str] = None
    region: Optional[str] = None
    timezone: Optional[str] = None


class NameLayer(Strict):
    """Registry entry describing one corner-name layer for clients."""
    label: Optional[str] = Field(None, description="Human-readable layer name for UI.")
    description: Optional[str] = None


class Corner(Strict):
    number: int = Field(description="Sequential corner number 1..N, no gaps — the ordering key.")
    code: str = Field(description="Trackside identifier (usually str(number); '5a'/'5b' for split apexes). "
                                  "The 'numbered' layer is this as 'Turn <code>'.")
    names: dict[LayerCode, str] = Field(
        description="Name layers keyed by layer code (see track.name_layers). 'numbered' is always "
                    "present; other layers appear only when a name is known. An unnamed corner carries "
                    "only 'numbered'.")
    complex: Optional[str] = Field(
        None, description="Multi-corner complex this turn belongs to (e.g. 'Porsche Curves'). Corners "
                          "sharing a complex must form one gap-free consecutive run.")
    direction: Optional[Literal["left", "right"]] = None
    scale: Optional[int] = Field(
        None, ge=1, le=6,
        description="Severity 1-6: 1=Hairpin, 2=Slow, 3=Medium, 4=Fast, 5=Very fast, 6=Kink.")
    marker: Optional[Fraction] = Field(None, description="Lap fraction at the apex.")
    start: Optional[Fraction] = Field(
        None, description="Lap fraction where the corner phase begins — the braking/turn-in "
                          "point, a few hundred metres before the apex for slow corners, scaled "
                          "by severity. Computed by lib/phases.py; corners in a complex meet.")
    end: Optional[Fraction] = Field(
        None, description="Lap fraction where the corner phase ends — a short distance after the "
                          "apex, into the throttle on exit.")
    location: Optional[LonLat] = Field(None, description="Apex coordinate, when resolvable.")
    location_source: Optional[Literal["osm-way", "centerline", "manual"]] = None

    @field_validator("names")
    @classmethod
    def _numbered_present(cls, v: dict) -> dict:
        if "numbered" not in v:
            raise ValueError("corner.names must contain the 'numbered' base layer")
        return v


class Sector(Strict):
    name: str = Field(description="Timing sector label: 'S1', 'S2', 'S3'.")
    start: Fraction = Field(description="Lap fraction where the sector begins.")
    end: Fraction = Field(description="Lap fraction where the sector ends (the timing line).")


class Straight(Strict):
    name: str
    aka: list[str] = []
    start: Optional[Fraction] = None
    end: Optional[Fraction] = None


class PointRef(Strict):
    id: Optional[str] = None
    name: Optional[str] = None
    location: LonLat
    marker: Optional[Fraction] = None


class Pit(Strict):
    entry: Optional[Fraction] = None
    exit: Optional[Fraction] = None


class Geometry(Strict):
    outline: str = Field(description="Path (relative to track dir) to the layout's GeoJSON.")
    crs: str = "EPSG:4326"


# --- layout ------------------------------------------------------------------
class Layout(Strict):
    id: Slug
    name: str
    aka: list[str] = []
    series: list[str] = Field(default=[], description="Series that use THIS layout, when it is "
                              "series-specific (e.g. ['imsa'] vs ['wec'] for Sebring's two pit "
                              "configurations). Empty = the track-level series all use this layout.")
    length_m: Optional[float] = Field(None, description="Lap length in metres.")
    direction: Optional[Literal["clockwise", "anticlockwise"]] = None
    active_years: Optional[str] = Field(None, description="Free-form, e.g. '2018-' or '1972,1979-1989'.")
    geometry: Geometry
    start_finish: Optional[PointRef] = None
    name_default: str = Field(
        DEFAULT_LAYER,
        description="Layer code (a key in track.name_layers) used as the default display name. "
                    "Resolution is two steps: corner.names[name_default] if present, else "
                    "corner.names.numbered — it does NOT fall through to other named layers.")
    corners: list[Corner] = []
    straights: list[Straight] = []
    sectors: list[Sector] = []
    pit: Optional[Pit] = None
    marshal_posts: list[PointRef] = []
    access_points: list[PointRef] = []

    @model_validator(mode="after")
    def _corner_invariants(self) -> "Layout":
        nums = [c.number for c in self.corners]
        if nums and sorted(nums) != list(range(1, len(nums) + 1)):
            raise ValueError(f"corner numbers not sequential 1..{len(nums)}: {sorted(nums)}")
        codes = [c.code for c in self.corners]
        dupes = {x for x in codes if codes.count(x) > 1}
        if dupes:
            raise ValueError(f"duplicate corner codes: {sorted(dupes)}")
        runs: dict[str, list[int]] = defaultdict(list)
        for c in self.corners:
            if c.complex:
                runs[c.complex].append(c.number)
        for cname, ns in runs.items():
            s = sorted(ns)
            if s != list(range(s[0], s[0] + len(s))):
                raise ValueError(f"complex '{cname}' is not a contiguous run of corners: {s}")
        return self


# --- top level ---------------------------------------------------------------
class Provenance(BaseModel):
    model_config = ConfigDict(extra="allow")
    generated_at: Optional[str] = None
    sources: Optional[list[dict]] = None
    corner_match: Optional[dict] = None


class Track(Strict):
    slug: Slug
    name: str = Field(description="Official circuit name.")
    aka: list[str] = []
    country: Optional[str] = Field(None, description="ISO 3166-1 alpha-2 code.")
    location: Location
    wikidata: Optional[Annotated[str, StringConstraints(pattern=r"^Q[0-9]+$")]] = None
    series: list[str] = []
    external_ids: dict[str, str] = {}
    name_layers: dict[LayerCode, NameLayer] = Field(
        description="Registry of corner-name layers. Keys are layer codes; clients enumerate these to "
                    "offer a layer to display. 'numbered' and 'official' are mandatory; 'driver' is the "
                    "usual default.")
    layouts: Annotated[list[Layout], Field(min_length=1)]
    provenance: Optional[Provenance] = None

    @field_validator("name_layers")
    @classmethod
    def _mandatory_layers(cls, v: dict) -> dict:
        missing = [m for m in MANDATORY_LAYERS if m not in v]
        if missing:
            raise ValueError(f"name_layers must declare mandatory layer(s): {missing}")
        return v

    @model_validator(mode="after")
    def _layer_references(self) -> "Track":
        declared = set(self.name_layers)
        for lo in self.layouts:
            if lo.name_default not in declared:
                raise ValueError(
                    f"layout '{lo.id}'.name_default '{lo.name_default}' is not a declared "
                    f"name layer {sorted(declared)}")
            for c in lo.corners:
                undeclared = set(c.names) - declared
                if undeclared:
                    raise ValueError(
                        f"layout '{lo.id}' corner {c.number} uses undeclared name layer(s) "
                        f"{sorted(undeclared)} (declare them in track.name_layers)")
        return self

"""Pydantic models for a track-atlas track.json — the single source of truth.

The atlas is layout-first: a physical track/facility has one or more racing
layouts, and every spatial annotation belongs to a layout. Layout annotations
come in two shapes:

  * point_layers: discrete lap locations (corner apexes, start/finish, pit in/out,
    marshal posts, timing loops)
  * range_layers: lap intervals (timing sectors, IMSA microsectors, corner
    phases, complexes, slow zones, straights)

These models define the schema: `scripts/build_schema.py` emits
`schema/track.schema.json` from them, and `scripts/verify.py` validates every
track against them.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, Optional

from pydantic import (
    BaseModel, ConfigDict, Field, StringConstraints,
    field_validator, model_validator,
)

from .naming import DEFAULT_LAYER, MANDATORY_LAYERS

# --- scalar / constrained types ----------------------------------------------
Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]
LayerCode = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$")]
LayerId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$")]
ItemId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_-]*$")]
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


class LabelLayer(Strict):
    """Registry entry describing one label/name layer for clients."""
    label: Optional[str] = Field(None, description="Human-readable layer name for UI.")
    description: Optional[str] = None


class Geometry(Strict):
    centerline: str = Field(description="Path (relative to track dir) to the layout's GeoJSON centerline/layer file.")
    crs: str = "EPSG:4326"


class PointItem(Strict):
    """A discrete annotation on a layout lap coordinate.

    The corners layer uses number/code/direction/scale/labels. Layout control
    points such as start_finish, pit_entry and pit_exit usually use label,
    marker and location.
    """
    id: ItemId
    label: Optional[str] = None
    marker: Optional[Fraction] = None
    location: Optional[LonLat] = None
    location_source: Optional[Literal["osm-way", "centerline", "manual"]] = None
    labels: dict[LayerCode, str] = Field(default_factory=dict)
    number: Optional[int] = None
    code: Optional[str] = None
    direction: Optional[Literal["left", "right"]] = None
    scale: Optional[int] = Field(None, ge=1, le=6,
                                description="Severity 1-6: 1=Hairpin, 2=Slow, 3=Medium, 4=Fast, 5=Very fast, 6=Kink.")


class PointLayer(Strict):
    id: LayerId
    kind: LayerId
    label: str
    description: Optional[str] = None
    series: list[str] = []
    items: list[PointItem] = []

    @model_validator(mode="after")
    def _unique_items(self) -> "PointLayer":
        ids = [i.id for i in self.items]
        dupes = {x for x in ids if ids.count(x) > 1}
        if dupes:
            raise ValueError(f"point layer '{self.id}' duplicate item ids: {sorted(dupes)}")
        if self.kind == "corners":
            nums = [i.number for i in self.items]
            if any(n is None for n in nums):
                raise ValueError("corners point layer items must have number")
            nums_int = [int(n) for n in nums if n is not None]
            if sorted(nums_int) != list(range(1, len(nums_int) + 1)):
                raise ValueError(f"corner numbers not sequential 1..{len(nums_int)}: {sorted(nums_int)}")
            codes = [i.code for i in self.items]
            if any(c in (None, "") for c in codes):
                raise ValueError("corners point layer items must have code")
            dup_codes = {x for x in codes if codes.count(x) > 1}
            if dup_codes:
                raise ValueError(f"duplicate corner codes: {sorted(dup_codes)}")
            missing_numbered = [i.id for i in self.items if "numbered" not in i.labels]
            if missing_numbered:
                raise ValueError(f"corner items missing numbered label: {missing_numbered}")
        return self


class RangeItem(Strict):
    """A lap interval annotation."""
    id: ItemId
    label: Optional[str] = None
    start: Fraction
    end: Fraction
    labels: dict[LayerCode, str] = Field(default_factory=dict)
    anchor: Optional[ItemId] = Field(None, description="Point item this range is derived from, e.g. a corner apex id.")
    members: list[ItemId] = Field(default=[], description="Point items contained in this range, e.g. corners in a complex.")
    entry_ref: Optional[str] = Field(None, description="Upstream timing loop / line where the range starts, when known.")
    exit_ref: Optional[str] = Field(None, description="Upstream timing loop / line where the range ends, when known.")
    length_m: Optional[float] = Field(None, description="Official/source length of this range in metres, when known.")


class RangeLayer(Strict):
    id: LayerId
    kind: LayerId
    label: str
    description: Optional[str] = None
    series: list[str] = []
    coverage: Optional[Literal["partition", "partial", "overlap"]] = None
    generated: bool = False
    provenance: Optional[dict[str, Any]] = None
    items: list[RangeItem] = []

    @model_validator(mode="after")
    def _range_invariants(self) -> "RangeLayer":
        ids = [i.id for i in self.items]
        dupes = {x for x in ids if ids.count(x) > 1}
        if dupes:
            raise ValueError(f"range layer '{self.id}' duplicate item ids: {sorted(dupes)}")
        for item in self.items:
            if not item.start < item.end:
                raise ValueError(f"range '{item.id}' start {item.start} must be < end {item.end}")
        if self.coverage == "partition" and self.items:
            ordered = sorted(self.items, key=lambda i: i.start)
            if abs(ordered[0].start - 0.0) > 1e-6 or abs(ordered[-1].end - 1.0) > 1e-6:
                raise ValueError(f"partition layer '{self.id}' must cover 0.0→1.0")
            for a, b in zip(ordered, ordered[1:]):
                if abs(a.end - b.start) > 1e-6:
                    raise ValueError(f"partition layer '{self.id}' has gap/overlap between {a.id} and {b.id}")
        return self


# --- layout ------------------------------------------------------------------
class Layout(Strict):
    id: Slug
    name: str
    aka: list[str] = []
    series: list[str] = Field(default=[], description="Series that use THIS layout/configuration.")
    length_m: Optional[float] = Field(None, description="Lap length in metres.")
    direction: Optional[Literal["clockwise", "anticlockwise"]] = None
    active_years: Optional[str] = Field(None, description="Free-form, e.g. '2018-' or '1972,1979-1989'.")
    geometry: Geometry
    label_default: str = Field(
        DEFAULT_LAYER,
        description="Label layer code used as the default display name. Resolution is two steps: item.labels[label_default] if present, else item.labels.numbered.")
    point_layers: list[PointLayer] = []
    range_layers: list[RangeLayer] = []

    @model_validator(mode="after")
    def _layer_ids_unique(self) -> "Layout":
        for attr in ("point_layers", "range_layers"):
            ids = [layer.id for layer in getattr(self, attr)]
            dupes = {x for x in ids if ids.count(x) > 1}
            if dupes:
                raise ValueError(f"layout '{self.id}' duplicate {attr} ids: {sorted(dupes)}")
        return self


# --- top level ---------------------------------------------------------------
class Provenance(BaseModel):
    model_config = ConfigDict(extra="allow")
    generated_at: Optional[str] = None
    sources: Optional[list[dict]] = None
    corner_match: Optional[dict] = None


class Track(Strict):
    slug: Slug
    name: str = Field(description="Official circuit/facility name.")
    aka: list[str] = []
    country: Optional[str] = Field(None, description="ISO 3166-1 alpha-2 code.")
    location: Location
    wikidata: Optional[Annotated[str, StringConstraints(pattern=r"^Q[0-9]+$")]] = None
    series: list[str] = []
    external_ids: dict[str, str] = {}
    label_layers: dict[LayerCode, LabelLayer] = Field(
        description="Registry of label/name layers. Keys are label codes used by item.labels. 'numbered' and 'official' are mandatory; 'driver' is the usual default.")
    layouts: Annotated[list[Layout], Field(min_length=1)]
    provenance: Optional[Provenance] = None

    @field_validator("label_layers")
    @classmethod
    def _mandatory_layers(cls, v: dict) -> dict:
        missing = [m for m in MANDATORY_LAYERS if m not in v]
        if missing:
            raise ValueError(f"label_layers must declare mandatory layer(s): {missing}")
        return v

    @model_validator(mode="after")
    def _layer_references(self) -> "Track":
        declared = set(self.label_layers)
        for lo in self.layouts:
            if lo.label_default not in declared:
                raise ValueError(
                    f"layout '{lo.id}'.label_default '{lo.label_default}' is not a declared label layer {sorted(declared)}")
            point_ids = {item.id for layer in lo.point_layers for item in layer.items}
            for layer in lo.point_layers:
                for item in layer.items:
                    undeclared = set(item.labels) - declared
                    if undeclared:
                        raise ValueError(
                            f"layout '{lo.id}' point layer '{layer.id}' item '{item.id}' uses undeclared label layer(s) {sorted(undeclared)}")
            for layer in lo.range_layers:
                for item in layer.items:
                    undeclared = set(item.labels) - declared
                    if undeclared:
                        raise ValueError(
                            f"layout '{lo.id}' range layer '{layer.id}' item '{item.id}' uses undeclared label layer(s) {sorted(undeclared)}")
                    refs = ([item.anchor] if item.anchor else []) + item.members
                    missing = [ref for ref in refs if ref not in point_ids]
                    if missing:
                        raise ValueError(
                            f"layout '{lo.id}' range layer '{layer.id}' item '{item.id}' references missing point item(s) {missing}")
        return self

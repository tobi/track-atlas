"""Run per-track layer source configs and merge produced layers into track.json.

A generation config is intentionally declarative: it names input URLs/files and
a converter tool. The runner resolves every resource to a local file before
invoking the converter, so converter tools are pure stdin -> stdout transforms
with no repo/network assumptions.
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .config import TRACKS, raw_dir, track_json_path
from .models import Track

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "scripts" / "layer_tools"


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _safe_name(s: str) -> str:
    out = "".join(c if c.isalnum() or c in "._-" else "-" for c in s.strip())
    return out.strip(".-") or "resource"


def _resource_filename(name: str, spec: dict[str, Any]) -> str:
    if spec.get("filename"):
        return _safe_name(spec["filename"])
    url = spec.get("url") or spec.get("path") or name
    path = urllib.parse.urlparse(url).path
    base = Path(urllib.parse.unquote(path)).name
    if not base or "." not in base:
        base = name
    return _safe_name(base)


def _resolve_resource(slug: str, config_id: str, name: str, spec: dict[str, Any]) -> dict[str, Any]:
    out_dir = raw_dir(slug) / "layer-sources" / _safe_name(config_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = _resource_filename(name, spec)
    dest = out_dir / filename
    if "url" in spec:
        if not dest.exists() or spec.get("refresh"):
            req = urllib.request.Request(spec["url"], headers={"User-Agent": "track-atlas/0.1 (+https://github.com/tobi/track-atlas)"})
            with urllib.request.urlopen(req, timeout=spec.get("timeout", 60)) as r:
                dest.write_bytes(r.read())
        return {"name": name, "url": spec["url"], "local_path": str(dest), "relative_path": _rel(dest), "content_type": spec.get("content_type")}
    if "path" in spec:
        p = Path(spec["path"])
        if not p.is_absolute():
            p = TRACKS / slug / p
        return {"name": name, "local_path": str(p), "relative_path": _rel(p), "content_type": spec.get("content_type")}
    raise ValueError(f"resource {name!r} must have url or path")


def _merge_layers(layout: dict, produced: dict) -> None:
    for kind in ("point_layers", "range_layers"):
        incoming = produced.get(kind) or []
        if not incoming:
            continue
        by_id = {layer["id"]: layer for layer in layout.get(kind, [])}
        order = [layer["id"] for layer in layout.get(kind, [])]
        for layer in incoming:
            if layer["id"] not in by_id:
                order.append(layer["id"])
            by_id[layer["id"]] = layer
        layout[kind] = [by_id[i] for i in order]


def run_config(slug: str, cfg: dict[str, Any], track: dict[str, Any]) -> dict[str, Any]:
    cid = cfg.get("id") or cfg.get("tool")
    if not cid:
        raise ValueError("layer config needs id or tool")
    layout_id = cfg["layout"]
    layout = next((l for l in track["layouts"] if l["id"] == layout_id), None)
    if not layout:
        raise ValueError(f"layout {layout_id!r} not found for {slug}")

    resources = {
        name: _resolve_resource(slug, cid, name, spec)
        for name, spec in (cfg.get("resources") or {}).items()
    }
    payload = {
        "config_id": cid,
        "slug": slug,
        "track": track,
        "layout": layout,
        "resources": resources,
        "params": cfg.get("params") or {},
    }
    tool_name = cfg["tool"]
    tool_path = TOOLS / f"{tool_name}.py"
    if not tool_path.exists():
        raise FileNotFoundError(f"layer tool not found: {tool_path}")
    proc = subprocess.run(
        [sys.executable, str(tool_path)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"layer tool {tool_name} failed for {slug}/{cid}:\nSTDERR:\n{proc.stderr}\nSTDOUT:\n{proc.stdout}")
    try:
        produced = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"layer tool {tool_name} did not print JSON: {e}\n{proc.stdout[:1000]}") from e
    _merge_layers(layout, produced)
    return produced


def run_layer_configs(slug: str, *, write: bool = True) -> dict[str, Any]:
    cfg_path = TRACKS / slug / "generation-config.json"
    track_path = track_json_path(slug)
    track = json.loads(track_path.read_text())
    if not cfg_path.exists():
        return track
    cfg_doc = json.loads(cfg_path.read_text())
    for cfg in cfg_doc.get("layers", []):
        if cfg.get("enabled", True):
            run_config(slug, cfg, track)
    try:
        Track.model_validate(track)
    except ValidationError:
        raise
    if write:
        track_path.write_text(json.dumps(track, ensure_ascii=False, indent=2))
    return track

"""Shared data-source helpers for track-atlas.

All network access funnels through here so retries, user-agents and the
Overpass busy-server dance live in one place. Raw payloads are always written
verbatim to a track's raw/ dir as artifacts; never mutate them.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

UA = "track-atlas/0.1 (https://github.com/tobi/track-atlas; research)"

LOVELY_BASE = "https://raw.githubusercontent.com/Lovely-Sim-Racing/lovely-track-data/main/data"
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]


def _get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_lovely(path: str) -> dict:
    """path is the manifest 'path' field, e.g. 'lmu/circuit-de-la-sarthe.json'."""
    return json.loads(_get(f"{LOVELY_BASE}/{path}"))


def fetch_lovely_manifest() -> dict:
    return json.loads(_get(f"{LOVELY_BASE}/manifest.json"))


def overpass(query: str, retries: int = 6, pause: int = 12, timeout: int = 120) -> dict:
    """Run an Overpass QL query with endpoint rotation + busy-server backoff.

    Overpass returns an HTML error page (not JSON) when overloaded; we detect
    that and retry rather than crashing.
    """
    last = None
    for attempt in range(retries):
        endpoint = OVERPASS_ENDPOINTS[attempt % len(OVERPASS_ENDPOINTS)]
        try:
            data = urllib.parse.urlencode({"data": query}).encode()
            req = urllib.request.Request(endpoint, data=data, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
            if body[:1] in (b"{", b"["):
                return json.loads(body)
            last = body[:200]
        except Exception as e:  # noqa: BLE001
            last = repr(e)
        time.sleep(pause)
    raise RuntimeError(f"Overpass failed after {retries} attempts: {last!r}")


def write_raw(track_dir: Path, name: str, payload) -> Path:
    """Persist a raw artifact under <track_dir>/raw/<name>. Bytes or json-able."""
    raw = Path(track_dir) / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    dest = raw / name
    if isinstance(payload, (bytes, bytearray)):
        dest.write_bytes(payload)
    elif isinstance(payload, str):
        dest.write_text(payload)
    else:
        dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return dest

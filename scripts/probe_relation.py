#!/usr/bin/env python3
"""Probe Overpass for route/circuit relations covering a track's bbox.

Usage: python scripts/probe_relation.py <slug> [<slug>...]
Prints candidate relation ids + names so a human (or agent) can pick the right
one and put it into source.json osm.relation.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.config import load_source  # noqa: E402

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
UA = "track-atlas/1.0 (github.com/tobi/track-atlas)"


def query(q):
    data = urllib.parse.urlencode({"data": q}).encode()
    for ep in ENDPOINTS:
        for attempt in range(3):
            try:
                req = urllib.request.Request(ep, data=data, headers={"User-Agent": UA})
                body = urllib.request.urlopen(req, timeout=120).read()
                if body[:1] in (b"{", b"["):
                    return json.loads(body)
            except Exception:
                pass
            time.sleep(4 * (attempt + 1))
    return None


def probe(slug):
    src = load_source(slug)
    s, w, n, e = src["osm"]["bbox"]
    bbox = f"{s},{w},{n},{e}"
    q = (f'[out:json][timeout:90];('
         f'relation["type"~"route|circuit"]({bbox});'
         f'relation["sport"="motor"]({bbox});'
         f'relation["highway"="raceway"]({bbox});'
         f');out tags;')
    res = query(q)
    print(f"\n== {slug} (bbox {bbox})")
    if not res:
        print("  overpass unavailable")
        return
    for el in res.get("elements", []):
        t = el.get("tags", {})
        print(f"  {el['id']:>10}  type={t.get('type','')!s:8} "
              f"route={t.get('route','')!s:6} name={t.get('name')}")
    if not res.get("elements"):
        print("  no relations found -- needs bbox-stitch fallback or manual geometry")


if __name__ == "__main__":
    for slug in sys.argv[1:]:
        probe(slug)
        time.sleep(3)

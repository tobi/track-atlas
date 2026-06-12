#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["anthropic"]
# ///
"""
annotate_all.py — run annotate.py across all tracks, commit after each one.

Usage:
    python scripts/annotate_all.py [--skip already-done,another]
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACKS = ROOT / "tracks"
ANNOTATE = ROOT / "scripts" / "annotate.py"
GENERATE = ROOT / "scripts" / "generate.py"
RENDER   = ROOT / "scripts" / "render.py"
VERIFY   = ROOT / "scripts" / "verify.py"


def run(cmd, **kw):
    return subprocess.run(cmd, **{"capture_output": True, "text": True, "cwd": ROOT, **kw})


def slugs():
    return sorted(
        p.name for p in TRACKS.iterdir()
        if p.is_dir() and (p / "source.json").exists()
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip", default="", help="comma-separated slugs to skip")
    args = ap.parse_args()
    skip = set(s.strip() for s in args.skip.split(",") if s.strip())

    all_slugs = [s for s in slugs() if s not in skip]
    print(f"Annotating {len(all_slugs)} tracks (skipping {len(skip)})\n")

    results = {}
    for i, slug in enumerate(all_slugs, 1):
        print(f"[{i}/{len(all_slugs)}] {slug}")

        # 1. annotate
        r = run([sys.executable, str(ANNOTATE), slug])
        print(r.stdout.strip())
        if r.returncode != 0:
            print(f"  ANNOTATE FAILED:\n{r.stderr[-500:]}")
            results[slug] = "annotate-failed"
            continue

        # 2. generate + render
        r2 = run([sys.executable, str(GENERATE), slug])
        r3 = run([sys.executable, str(RENDER), slug])

        # 3. verify
        r4 = run([sys.executable, str(VERIFY), slug])
        verdict = "PASS" if r4.returncode == 0 else "FAIL"
        if verdict == "FAIL":
            print(f"  verify output:\n{r4.stdout[-400:]}")
        results[slug] = verdict

        # 4. commit
        run(["git", "add", "-A"])
        run(["git", "commit", "-m",
             f"annotate {slug}: model corner names, complexes, scale, errors"])
        print(f"  → committed ({verdict})\n")

        # be polite to the API
        if i < len(all_slugs):
            time.sleep(2)

    # push once at the end
    print("Pushing…")
    rp = run(["git", "push", "-q", "origin", "main"])
    print(rp.stdout or "(ok)")

    # summary
    passed = [s for s, v in results.items() if v == "PASS"]
    failed = [s for s, v in results.items() if v != "PASS"]
    print(f"\nDone: {len(passed)}/{len(all_slugs)} PASS")
    if failed:
        print("Failed:", ", ".join(failed))


if __name__ == "__main__":
    main()

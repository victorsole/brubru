#!/usr/bin/env python3.12
"""
Turn the validated `data/europa_eu/discovered_feeds.csv` into
YAML ingestion configs at `backend/services/ingestion/configs/`.

One YAML per feed_url. Skips rows that already have a matching YAML
(tracked by slug) so hand-curated configs aren't overwritten.

Usage:
    python3.12 scripts/configs_from_discovered.py
    python3.12 scripts/configs_from_discovered.py --overwrite
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DISCOVERED = REPO_ROOT / "data" / "europa_eu" / "discovered_feeds.csv"
CONFIGS_DIR = REPO_ROOT / "backend" / "services" / "ingestion" / "configs"


def slugify(base_url: str) -> str:
    host = base_url.replace("https://", "").replace("http://", "").split("/")[0]
    parts = host.replace(".europa.eu", "").split(".")
    slug = "_".join(reversed(parts))
    return re.sub(r"[^a-z0-9_]+", "_", slug).strip("_") or "unknown"


def institution_slug(institution: str) -> str:
    base = institution.lower()
    base = re.split(r"[-–:]", base)[0]
    base = re.sub(r"[^a-z0-9]+", "_", base).strip("_")
    return base[:60]


def write_config(feed_url: str, institution: str, slug: str, overwrite: bool) -> bool:
    path = CONFIGS_DIR / f"{slug}.yaml"
    if path.exists() and not overwrite:
        return False
    content = (
        f"slug: {slug}\n"
        f"institution_slug: {institution_slug(institution)}\n"
        f"url: {feed_url}\n"
        f"language: en\n"
    )
    path.write_text(content)
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if not DISCOVERED.exists():
        print(f"[ERROR] {DISCOVERED} not found. Run discover_feeds.py first.", file=sys.stderr)
        return 1

    CONFIGS_DIR.mkdir(parents=True, exist_ok=True)

    written = 0
    skipped = 0
    with DISCOVERED.open() as fp:
        for row in csv.DictReader(fp):
            feed = row["feed_url"].strip()
            if not feed:
                continue
            slug = slugify(row["base_url"])
            if write_config(feed, row["institution"], slug, args.overwrite):
                written += 1
                print(f"  [WRITE] {slug}.yaml  <- {feed}")
            else:
                skipped += 1

    print(f"\n[done] wrote={written}  skipped={skipped}  total rows processed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3.12
"""
Feed discovery crawler.

Takes the 519-domain inventory in `data/europa_eu/europa.eu_all_sources.md`
(or any CSV of `url,institution`), probes each base domain for RSS/Atom
feeds via two methods:

    1. Parse the home page HTML, look for
       <link rel="alternate" type="application/rss+xml" href="...">
    2. Try common feed paths (/rss, /rss.xml, /feed, /news/rss, etc.)

Writes a validated catalog to `data/europa_eu/discovered_feeds.csv` with
columns: base_url, institution, feed_url, feed_title, status_code, method.

Usage:
    python3.12 scripts/discover_feeds.py
    python3.12 scripts/discover_feeds.py --limit 20
    python3.12 scripts/discover_feeds.py --only ema.europa.eu echa.europa.eu
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import aiohttp
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY = REPO_ROOT / "data" / "europa_eu" / "europa.eu_all_sources.md"
OUT_CSV = REPO_ROOT / "data" / "europa_eu" / "discovered_feeds.csv"

UA = "Mozilla/5.0 (compatible; Brubru/1.0; +https://brubru.beresol.eu)"
TIMEOUT = aiohttp.ClientTimeout(total=15)

COMMON_PATHS = [
    "/rss", "/rss.xml", "/feed", "/feed.xml", "/atom.xml",
    "/news/rss", "/news/rss.xml", "/news.rss",
    "/en/rss.xml", "/en/feed", "/en/news/rss",
    "/press/rss", "/press-releases/rss",
    "/@@rss.xml", "/index.rss",
]

CSV_LINE_RE = re.compile(r"^https?://([^,]+),\s*(.+?)\s*(?:\[INFRA\])?\s*$")


def parse_inventory(path: Path) -> List[Tuple[str, str]]:
    """Return [(base_url, institution), ...] from the markdown CSV block."""
    out: List[Tuple[str, str]] = []
    seen: set[str] = set()
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line.startswith("https://"):
            continue
        m = CSV_LINE_RE.match(line)
        if not m:
            continue
        host, inst = m.group(1).rstrip("/"), m.group(2).strip()
        base = f"https://{host}"
        if base in seen:
            continue
        seen.add(base)
        if "[INFRA]" in line:
            continue  # skip infrastructure-only hosts
        out.append((base, inst))
    return out


async def _fetch(session: aiohttp.ClientSession, url: str) -> Tuple[int, str]:
    try:
        async with session.get(url, timeout=TIMEOUT, allow_redirects=True) as r:
            body = await r.text(errors="ignore")
            return r.status, body
    except Exception:
        return 0, ""


async def _probe_one(session: aiohttp.ClientSession, base: str, institution: str) -> List[dict]:
    """Return discovered feeds for a single base URL."""
    found: List[dict] = []

    # Method 1: parse base HTML for <link rel="alternate" type="application/rss+xml">
    status, body = await _fetch(session, base)
    if status == 200 and body:
        try:
            soup = BeautifulSoup(body, "html.parser")
            for link in soup.find_all("link", rel=lambda v: v and "alternate" in (v if isinstance(v, list) else [v])):
                t = (link.get("type") or "").lower()
                href = link.get("href") or ""
                if not href:
                    continue
                if "rss" in t or "atom" in t:
                    feed_url = href if href.startswith("http") else f"{base.rstrip('/')}/{href.lstrip('/')}"
                    found.append({
                        "base_url": base,
                        "institution": institution,
                        "feed_url": feed_url,
                        "feed_title": link.get("title") or "",
                        "status_code": status,
                        "method": "link_rel_alternate",
                    })
        except Exception:
            pass

    # Method 2: try common paths (only if we didn't find anything yet)
    if not found:
        for p in COMMON_PATHS:
            url = base.rstrip("/") + p
            status2, body2 = await _fetch(session, url)
            if status2 == 200 and body2 and ("<rss" in body2[:2000].lower() or "<feed" in body2[:2000].lower()):
                found.append({
                    "base_url": base,
                    "institution": institution,
                    "feed_url": url,
                    "feed_title": "",
                    "status_code": status2,
                    "method": "common_path",
                })
                break  # one working path is enough

    return found


async def discover(targets: List[Tuple[str, str]], concurrency: int = 20) -> List[dict]:
    sem = asyncio.Semaphore(concurrency)
    found: List[dict] = []
    headers = {"User-Agent": UA}
    async with aiohttp.ClientSession(headers=headers) as session:
        async def _worker(base: str, inst: str):
            async with sem:
                feeds = await _probe_one(session, base, inst)
                for f in feeds:
                    print(f"  [OK] {f['method']:20s} {f['feed_url']}")
                    found.append(f)
                if not feeds:
                    print(f"  [-]  no feed  {base}")

        await asyncio.gather(*(_worker(b, i) for b, i in targets))
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Probe only the first N targets")
    parser.add_argument("--only", nargs="*", help="Only probe hosts matching these substrings")
    parser.add_argument("--out", default=str(OUT_CSV))
    args = parser.parse_args()

    targets = parse_inventory(INVENTORY)
    if args.only:
        targets = [t for t in targets if any(s in t[0] for s in args.only)]
    if args.limit:
        targets = targets[: args.limit]
    print(f"[discover] probing {len(targets)} hosts")

    found = asyncio.run(discover(targets))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=["base_url", "institution", "feed_url", "feed_title", "status_code", "method"])
        w.writeheader()
        for row in sorted(found, key=lambda r: (r["institution"], r["feed_url"])):
            w.writerow(row)

    print(f"[discover] wrote {len(found)} rows to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

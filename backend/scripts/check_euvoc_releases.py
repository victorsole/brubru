#!/usr/bin/env python3
"""
Monthly check of EU Vocabularies releases.

Scrapes https://op.europa.eu/en/web/eu-vocabularies/releases (the
Publications Office "Releases" page) and diffs against a saved
snapshot at data/eu_vocabularies/releases_snapshot.json.

Output (stdout, JSON):
    {
        "checked_at": "2026-05-02T...",
        "new_releases": [{"title": "...", "url": "...", "date": "..."}],
        "updated_releases": [...],
        "total_seen": N,
        "snapshot_age_days": M
    }

Exit code:
    0 - no new/updated releases
    1 - new or updated releases found (calling skill should re-trigger
        sync_eu_authority_labels for the affected NAL)
    2 - scrape failed (Cellar/OP outage; do not crash /news)

Run from repo root:
    python3.12 backend/scripts/check_euvoc_releases.py

Cadence: monthly via /news (1st of every month, sub-step 1d).
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = ROOT / "data" / "eu_vocabularies" / "releases_snapshot.json"
RELEASES_URL = "https://op.europa.eu/en/web/eu-vocabularies/releases"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("check-euvoc-releases")

# Realistic browser UA — the OP page is behind a CDN that 403s "bot"-shaped UAs.
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)


def _fetch_releases_html() -> str:
    req = urllib.request.Request(
        RELEASES_URL,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


# Releases page renders each release as <li> or <article> with anchors
# linking into /en/web/eu-vocabularies/dataset/-/resource?... — match the
# anchor text + href + nearest visible date.
_ANCHOR_RE = re.compile(
    r'<a[^>]+href="(?P<href>[^"]+(?:dataset|news|content)[^"]*)"[^>]*>'
    r'(?P<text>[^<]{6,200})</a>',
    re.IGNORECASE,
)
_DATE_RE = re.compile(r"(\d{1,2}\s+\w+\s+202\d|\d{4}-\d{2}-\d{2})")


def _parse_releases(html: str) -> List[Dict[str, str]]:
    """Best-effort extraction. Returns list of {title, url, date}."""
    out: List[Dict[str, str]] = []
    seen_urls = set()
    for m in _ANCHOR_RE.finditer(html):
        href = m.group("href").strip()
        text = re.sub(r"\s+", " ", m.group("text")).strip()
        if not href.startswith("http"):
            href = "https://op.europa.eu" + href if href.startswith("/") else f"https://op.europa.eu/{href}"
        if href in seen_urls:
            continue
        seen_urls.add(href)

        # Look for a date within ~200 chars of the anchor for context.
        anchor_pos = m.start()
        window = html[max(0, anchor_pos - 200) : anchor_pos + 400]
        date_match = _DATE_RE.search(window)
        date = date_match.group(0) if date_match else ""

        out.append({"title": text, "url": href, "date": date})
    return out


def _load_snapshot() -> Dict[str, Any]:
    if not SNAPSHOT_PATH.exists():
        return {"releases": [], "snapshotted_at": None}
    return json.loads(SNAPSHOT_PATH.read_text())


def _save_snapshot(releases: List[Dict[str, str]]) -> None:
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(
        json.dumps(
            {
                "snapshotted_at": datetime.now(timezone.utc).isoformat(),
                "releases": releases,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


def _diff(prev: List[Dict[str, str]], curr: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    prev_index = {r["url"]: r for r in prev}
    curr_index = {r["url"]: r for r in curr}

    new = [r for url, r in curr_index.items() if url not in prev_index]
    updated = [
        r
        for url, r in curr_index.items()
        if url in prev_index and prev_index[url].get("title") != r.get("title")
    ]
    return {"new": new, "updated": updated}


def main() -> int:
    try:
        html = _fetch_releases_html()
    except (urllib.error.URLError, TimeoutError) as e:
        log.error(f"Failed to fetch releases page: {e}")
        print(json.dumps({"error": str(e), "checked_at": datetime.now(timezone.utc).isoformat()}))
        return 2

    curr = _parse_releases(html)
    if not curr:
        log.warning("Parsed 0 releases — page structure may have changed")
        print(json.dumps({"warning": "no releases parsed", "html_len": len(html)}))
        return 2

    snapshot = _load_snapshot()
    diff = _diff(snapshot.get("releases", []), curr)

    snapshotted_at = snapshot.get("snapshotted_at")
    age_days = None
    if snapshotted_at:
        try:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(snapshotted_at)
            age_days = age.days
        except ValueError:
            pass

    result = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "new_releases": diff["new"],
        "updated_releases": diff["updated"],
        "total_seen": len(curr),
        "snapshot_age_days": age_days,
    }

    # Always update the snapshot if we got a clean parse.
    _save_snapshot(curr)

    print(json.dumps(result, indent=2, ensure_ascii=False))

    if diff["new"] or diff["updated"]:
        log.info(f"Found {len(diff['new'])} new, {len(diff['updated'])} updated")
        return 1
    log.info(f"No changes ({len(curr)} releases tracked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

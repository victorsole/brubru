"""
Apify-based LinkedIn competitor scraper for Brubru's /competitors skill.

Scrapes the 5 canonical competitor LinkedIn company pages locked 22 May 2026:
  - Spaak: https://be.linkedin.com/company/spaak-technologies
  - Prismos: https://be.linkedin.com/company/prismos
  - Lobium: https://uk.linkedin.com/company/lobium
  - Moonlit: https://www.linkedin.com/company/moonlit-ai/
  - EU Matrix: https://be.linkedin.com/company/eumatrix-eu

Uses Apify's `run-sync-get-dataset-items` endpoint. The actor is configurable
(env var APIFY_LINKEDIN_ACTOR; defaults to `harvestapi~linkedin-company-posts`)
so we can swap actors without editing this script.

Output: prints a per-URL 1-line summary to stdout, and writes the full JSON
of all returned items to /tmp/competitors_linkedin_YYYY-MM-DD.json.

The /competitors skill calls this script as Step 0 and then reads the JSON
file to build its findings table.

Usage:
    python3.12 scripts/scrape_competitor_linkedin.py            # normal run
    python3.12 scripts/scrape_competitor_linkedin.py --debug    # extra logging
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# Load .env so APIFY_API_KEY is available when the script runs from a non-shell env.
try:
    from dotenv import load_dotenv  # type: ignore
    _project_root = Path(__file__).resolve().parents[2]
    load_dotenv(_project_root / ".env")
except Exception:
    pass


COMPETITORS = [
    ("Spaak",     "https://be.linkedin.com/company/spaak-technologies"),
    ("Prismos",   "https://be.linkedin.com/company/prismos"),
    ("Lobium",    "https://uk.linkedin.com/company/lobium"),
    ("Moonlit",   "https://www.linkedin.com/company/moonlit-ai/"),
    ("EU Matrix", "https://be.linkedin.com/company/eumatrix-eu"),
]

DEFAULT_ACTOR = os.environ.get(
    "APIFY_LINKEDIN_ACTOR",
    "harvestapi~linkedin-company-posts",
)

OUTPUT_PATH = Path(f"/tmp/competitors_linkedin_{datetime.utcnow().strftime('%Y-%m-%d')}.json")


def _api_call(actor_id: str, token: str, input_payload: dict, timeout_seconds: int = 120, debug: bool = False) -> list[dict]:
    """Call Apify run-sync-get-dataset-items endpoint, return parsed JSON list.

    If the actor takes longer than `timeout_seconds`, Apify will return whatever
    items the actor produced up to that point. We pass `timeout` and `memory`
    explicitly to avoid surprises.
    """
    url = (
        f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
        f"?token={urllib.parse.quote(token)}"
        f"&timeout={timeout_seconds}"
        f"&memory=1024"
    )
    body = json.dumps(input_payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    if debug:
        print(f"[debug] POST {url}", file=sys.stderr)
        print(f"[debug] body={input_payload}", file=sys.stderr)
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds + 30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        print(f"[ERROR] Apify HTTP {e.code}: {body[:400]}", file=sys.stderr)
        return []
    except Exception as exc:
        print(f"[ERROR] Apify call failed: {exc}", file=sys.stderr)
        return []
    try:
        data = json.loads(raw)
    except Exception as exc:
        print(f"[ERROR] Apify returned non-JSON: {exc}", file=sys.stderr)
        if debug:
            print(raw[:500], file=sys.stderr)
        return []
    if isinstance(data, list):
        return data
    return []


def _summarise_competitor(name: str, items: list[dict]) -> str:
    """Build a 1-line summary for a competitor based on Apify output items."""
    if not items:
        return f"  [{name}] no posts returned"
    dates = []
    for item in items:
        for key in ("date", "postedAt", "publishedAt", "time", "timestamp", "postedDate"):
            val = item.get(key)
            if val:
                dates.append(str(val))
                break
    most_recent = max(dates) if dates else "(no date field)"
    return f"  [{name}] {len(items)} item(s), most-recent: {most_recent}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--debug", action="store_true", help="extra logging")
    parser.add_argument("--actor", default=DEFAULT_ACTOR, help=f"Apify actor id (default {DEFAULT_ACTOR})")
    args = parser.parse_args()

    token = os.environ.get("APIFY_API_KEY", "").strip()
    if not token:
        print("[ERROR] APIFY_API_KEY not set in environment or .env", file=sys.stderr)
        return 2

    print(f"[INFO] Apify actor: {args.actor}")
    print(f"[INFO] Scraping {len(COMPETITORS)} LinkedIn pages")

    all_results: dict = {
        "scraped_at": datetime.utcnow().isoformat() + "Z",
        "actor": args.actor,
        "competitors": {},
    }

    for name, url in COMPETITORS:
        if args.debug:
            print(f"[debug] {name}: {url}", file=sys.stderr)
        # Schema for `harvestapi~linkedin-company-posts` (verified 22 May 2026):
        #   targetUrls: array of LinkedIn company URLs
        #   maxPosts: per-input cap
        #   postedLimit: time filter ("week" | "month" | "any")
        payload = {
            "targetUrls": [url],
            "maxPosts": 20,
            "postedLimit": "month",
            "includeQuotePosts": True,
            "includeReposts": True,
            "scrapeReactions": False,
            "scrapeComments": False,
        }
        items = _api_call(args.actor, token, payload, timeout_seconds=90, debug=args.debug)
        all_results["competitors"][name] = {
            "url": url,
            "count": len(items),
            "items": items,
        }
        print(_summarise_competitor(name, items))
        # Be polite to Apify rate limits between runs
        time.sleep(2)

    OUTPUT_PATH.write_text(json.dumps(all_results, indent=2, default=str))
    print(f"\n[OK] Wrote {OUTPUT_PATH}")
    total = sum(c["count"] for c in all_results["competitors"].values())
    print(f"[OK] Total items: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

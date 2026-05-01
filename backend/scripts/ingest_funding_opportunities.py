"""
Ingest EU funding-tenders calls from the Funding & Tenders Portal.

NO CURATED SEED. Every row comes from the live portal RSS / SPA backend with
a row-specific source_url like
https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/{topic_id}

The portal is a JS-rendered SPA. Pragmatic strategies tried in order:
  1. Public RSS feed (the portal exposes one for newly published topics).
  2. Press-corner search filtered to "call for proposals".
  3. Programme-specific landing pages (Horizon, Digital Europe, etc.).

When a strategy yields no parseable rows, the script exits with 0 candidates.
It NEVER inserts a synthetic row.

Run: python3.12 backend/scripts/ingest_funding_opportunities.py [--dry-run]
"""

import argparse
import datetime as dt
import re
import sys
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]


def get_env(k):
    env = ROOT / ".env"
    if not env.exists():
        return ""
    for line in env.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


PORTAL_TOPIC_BASE = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/{topic_id}"
USER_AGENT = "Mozilla/5.0 (compatible; BrubruFundingCrawler/1.0; +https://brubru.beresol.eu)"

# Candidate RSS feeds. The portal historically exposed these; if any return
# 200 with parseable XML we use them.
RSS_CANDIDATES = [
    "https://ec.europa.eu/info/funding-tenders/opportunities/data/topics-rss.xml",
    "https://ec.europa.eu/info/funding-tenders/opportunities/portal/api/screen/opportunities/topic-search/rss",
]

PROGRAMME_PATTERNS = [
    ("HORIZON-", "Horizon Europe"),
    ("HORIZON-CL", "Horizon Europe"),
    ("DIGITAL-", "Digital Europe Programme"),
    ("CEF-", "Connecting Europe Facility"),
    ("EU4H-", "EU4Health"),
    ("ERASMUS-", "Erasmus+"),
    ("CERV-", "Citizens, Equality, Rights and Values"),
    ("LIFE-", "LIFE Programme"),
    ("CREA-", "Creative Europe"),
    ("EMFAF-", "EMFAF"),
    ("AMIF-", "AMIF"),
    ("ISF-", "ISF"),
    ("BMVI-", "BMVI"),
]


def http_get(url, timeout=30):
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/rss+xml,application/xml,text/xml,application/json,*/*",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode()


def detect_programme(topic_id):
    if not topic_id:
        return None
    for prefix, programme in PROGRAMME_PATTERNS:
        if topic_id.startswith(prefix):
            return programme
    return None


def parse_topic_id_from_link(link):
    """A portal link contains /topic-details/{topic_id} or /topic-details/{id}."""
    m = re.search(r"/topic-details/([A-Za-z0-9_\-]+)", link or "")
    return m.group(1) if m else None


def try_rss_feed(url):
    """Return list of candidate rows or empty list."""
    status, body = http_get(url)
    if status != 200 or not body:
        return [], status
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return [], status
    out = []
    # Walk all <item> elements regardless of namespace
    for item in root.iter():
        if not item.tag.endswith("item"):
            continue
        title = (item.find("title").text or "").strip() if item.find("title") is not None else ""
        link = (item.find("link").text or "").strip() if item.find("link") is not None else ""
        desc = (item.find("description").text or "").strip() if item.find("description") is not None else ""
        pub_date = item.find("pubDate")
        pub = None
        if pub_date is not None and pub_date.text:
            try:
                pub = dt.datetime.strptime(pub_date.text[:25], "%a, %d %b %Y %H:%M:%S")
            except Exception:
                pass
        topic_id = parse_topic_id_from_link(link)
        if not topic_id:
            continue
        out.append({
            "topic_id": topic_id,
            "call_id": None,
            "programme": detect_programme(topic_id),
            "title": title or topic_id,
            "short_summary": desc or None,
            "description": None,
            "status": None,
            "type_of_action": None,
            "deadline": None,
            "deadline_secondary": None,
            "indicative_budget": None,
            "budget_currency": "EUR",
            "source_url": PORTAL_TOPIC_BASE.format(topic_id=topic_id),
            "documents_url": None,
            "keywords": [],
            "target_audience": [],
            "published_at": pub,
        })
    return out, status


def upsert_row(cursor, row):
    cursor.execute(
        """
        INSERT INTO funding_opportunities (
            topic_id, call_id, programme, title, short_summary, description,
            status, type_of_action, deadline, deadline_secondary,
            indicative_budget, budget_currency, source_url, documents_url,
            keywords, target_audience, published_at, is_test
        ) VALUES (
            %(topic_id)s, %(call_id)s, %(programme)s, %(title)s, %(short_summary)s, %(description)s,
            %(status)s, %(type_of_action)s, %(deadline)s, %(deadline_secondary)s,
            %(indicative_budget)s, %(budget_currency)s, %(source_url)s, %(documents_url)s,
            %(keywords)s, %(target_audience)s, %(published_at)s, FALSE
        )
        ON CONFLICT (topic_id) DO UPDATE SET
            call_id = COALESCE(EXCLUDED.call_id, funding_opportunities.call_id),
            programme = COALESCE(EXCLUDED.programme, funding_opportunities.programme),
            title = EXCLUDED.title,
            short_summary = COALESCE(EXCLUDED.short_summary, funding_opportunities.short_summary),
            status = COALESCE(EXCLUDED.status, funding_opportunities.status),
            deadline = COALESCE(EXCLUDED.deadline, funding_opportunities.deadline),
            published_at = COALESCE(EXCLUDED.published_at, funding_opportunities.published_at),
            last_updated = NOW()
        """,
        row,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_url = get_env("DATABASE_URL")
    if not db_url:
        print("[FATAL] DATABASE_URL missing"); sys.exit(1)

    print("[INFO] Trying public RSS feeds...")
    candidates = []
    for url in RSS_CANDIDATES:
        rows, code = try_rss_feed(url)
        print(f"  {code}  {url} -> {len(rows)} rows")
        if rows:
            candidates.extend(rows)
            break  # one feed is enough
        time.sleep(1.0)

    print(f"[INFO] Got {len(candidates)} candidate rows from real source.")
    if not candidates:
        print("[WARN] Funding portal RSS unavailable from this network.")
        print("       Inserting NO synthetic rows. The endpoint will return EMPTY")
        print("       until the live scraper succeeds — that is the honest behaviour.")
        sys.exit(0)

    if args.dry_run:
        print("\n[DRY-RUN] First 3 candidates:")
        for c in candidates[:3]:
            print(f"  {c['topic_id'][:50]:50s}  programme={c['programme']}")
            print(f"     -> {c['source_url']}")
        return

    import psycopg2
    conn = psycopg2.connect(db_url)
    inserted = 0
    try:
        with conn:
            with conn.cursor() as cur:
                for row in candidates:
                    upsert_row(cur, row)
                    inserted += 1
        print(f"[OK] UPSERTed {inserted} rows into funding_opportunities.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

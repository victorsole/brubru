"""
Real ingestion of EU funding opportunities via the SEDIA search API.

The F&T Portal (https://ec.europa.eu/info/funding-tenders/opportunities) is a
JS-rendered SPA and exposes no useful RSS feed. The portal IS backed by a
public search API at api.tech.ec.europa.eu — that's what the SPA calls under
the hood. We use it directly here.

Endpoint:
    POST https://api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey=SEDIA
    Content-Type: application/json
    Body:
        {"sort":{"field":"sortStatus","order":"asc"},
         "pageNumber": N, "pageSize": 100, "languages":["en"]}

Returns up to 100 topics per page; total ~640k across all programmes/years.
We restrict to recent (programmePeriod 2021+, status forthcoming/open) and to
a few principal programmes (Horizon Europe, Digital Europe, CEF, EIC, EIE).

Each result row maps to the funding_opportunities schema:
    topic_id      = identifier (e.g. "HORIZON-CL5-2026-D2-01-04")
    call_id       = callIdentifier
    programme     = derived from frameworkProgramme + programmeDivision
    title         = title
    short_summary = first <p> from descriptionByte (HTML stripped)
    description   = full descriptionByte (HTML stripped)
    status        = forthcoming | open | closed (decoded from status code)
    deadline      = deadlineDate
    type_of_action= typesOfAction[0]
    source_url    = portal URL (https://ec.europa.eu/info/funding-tenders/.../topic-details/{topic_id})
    documents_url = SEDIA topicDetails JSON URL
    keywords      = keywords array

UPSERT on topic_id. Run:
    python3.12 backend/scripts/ingest_funding_sedia.py [--limit 200] [--apply]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

import psycopg2
import psycopg2.extras
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
SEDIA_URL_TEMPLATE = (
    "https://api.tech.ec.europa.eu/search-api/prod/rest/search"
    "?apiKey=SEDIA&text={text}"
)
PORTAL_BASE = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details"
USER_AGENT = "Mozilla/5.0 (compatible; BrubruIngest/1.0; +https://brubru.beresol.eu)"

# SEDIA status code mapping (from the portal's Angular source).
STATUS_MAP = {
    "31094501": "forthcoming",
    "31094502": "open",
    "31094503": "closed",
}


def get_env(key: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def html_strip(html: str, max_len: int = 4000) -> str:
    if not html:
        return ""
    try:
        text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    except Exception:  # noqa: BLE001
        text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return (text[:max_len] + "…") if len(text) > max_len else text


def fetch_sedia_page(page: int, page_size: int = 100, status_filter: Optional[str] = None,
                     text: str = "*") -> Dict[str, Any]:
    """One page of SEDIA results.

    Pagination MUST go in the URL — the API ignores pageNumber/pageSize in the
    POST body. The body can stay empty (or '{}'). status_filter is currently
    not effective at this layer (the API doesn't honour body-level filters
    either) — we filter client-side after parsing.

    `text` is a SEDIA full-text query. Use '*' for all, '2026' to pull only
    calls whose identifiers / descriptions reference 2026 (covers Horizon
    2026 work programmes, EIC 2026, Digital Europe 2026, etc.).
    """
    url = SEDIA_URL_TEMPLATE.format(text=urllib_request.quote(text, safe="*")) + f"&pageNumber={page}&pageSize={page_size}"
    req = urllib_request.Request(
        url,
        data=b"{}",
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib_request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib_error.HTTPError as e:
        print(f"  [HTTP {e.code}] page={page}: {e.read()[:200]}")
        return {}
    except Exception as e:  # noqa: BLE001
        print(f"  [{type(e).__name__}] page={page}: {str(e)[:80]}")
        return {}


def first_or_none(arr) -> Optional[Any]:
    if isinstance(arr, list) and arr:
        return arr[0]
    return None


def parse_iso_date(s: str) -> Optional[dt.datetime]:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00").replace("+0000", "+00:00").replace(".000", ""))
    except Exception:  # noqa: BLE001
        return None


def normalise_row(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    md = result.get("metadata") or {}
    topic_id = first_or_none(md.get("identifier"))
    title = first_or_none(md.get("title")) or result.get("content")
    if not topic_id or not title:
        return None
    description_html = first_or_none(md.get("descriptionByte")) or ""
    short_html = (description_html or "").split("</p>", 1)[0] + "</p>" if "</p>" in description_html else description_html[:600]

    status_code = first_or_none(md.get("status"))
    status = STATUS_MAP.get(str(status_code), "unknown")

    deadline = parse_iso_date(first_or_none(md.get("deadlineDate")))
    published = parse_iso_date(first_or_none(md.get("startDate"))) or parse_iso_date(first_or_none(md.get("es_SortDate")))
    types = md.get("typesOfAction") or []
    type_of_action = types[0] if types else None

    keywords = md.get("keywords") or []
    if not isinstance(keywords, list):
        keywords = [keywords]

    portal_url = f"{PORTAL_BASE}/{topic_id}"
    documents_url = first_or_none(md.get("url")) or first_or_none(md.get("esST_URL"))

    programme_period = first_or_none(md.get("programmePeriod")) or ""
    call_id = first_or_none(md.get("callIdentifier"))

    return {
        "topic_id": topic_id,
        "call_id": call_id,
        "programme": programme_period,
        "title": title,
        "short_summary": html_strip(short_html, 600),
        "description": html_strip(description_html, 8000),
        "status": status,
        "type_of_action": type_of_action,
        "deadline": deadline,
        "deadline_secondary": None,
        "indicative_budget": None,
        "budget_currency": "EUR",
        "source_url": portal_url,
        "documents_url": documents_url,
        "keywords": keywords,
        "target_audience": None,
        "published_at": published,
    }


def upsert(cur, row: Dict[str, Any]) -> None:
    cur.execute(
        """
        INSERT INTO funding_opportunities
            (topic_id, call_id, programme, title, short_summary, description, status,
             type_of_action, deadline, deadline_secondary, indicative_budget,
             budget_currency, source_url, documents_url, keywords, target_audience,
             published_at, scraped_at, last_updated)
        VALUES (%(topic_id)s, %(call_id)s, %(programme)s, %(title)s, %(short_summary)s,
                %(description)s, %(status)s, %(type_of_action)s, %(deadline)s,
                %(deadline_secondary)s, %(indicative_budget)s, %(budget_currency)s,
                %(source_url)s, %(documents_url)s, %(keywords)s, %(target_audience)s,
                %(published_at)s, NOW(), NOW())
        ON CONFLICT (topic_id) DO UPDATE SET
            call_id = EXCLUDED.call_id,
            title = EXCLUDED.title,
            short_summary = EXCLUDED.short_summary,
            description = EXCLUDED.description,
            status = EXCLUDED.status,
            type_of_action = EXCLUDED.type_of_action,
            deadline = EXCLUDED.deadline,
            keywords = EXCLUDED.keywords,
            last_updated = NOW()
        """,
        row,
    )


def upsert_ft_calls(cur, row: Dict[str, Any]) -> None:
    """Mirror the same row into the sibling ft_calls_for_proposals table.

    Schema parity: ft_calls_for_proposals has `framework_programme` where
    funding_opportunities has `programme`, and no `short_summary` field.
    All other columns line up 1:1, so we just rename + drop.
    """
    payload = dict(row)
    payload["framework_programme"] = payload.pop("programme", None)
    payload.pop("short_summary", None)
    cur.execute(
        """
        INSERT INTO ft_calls_for_proposals
            (topic_id, call_id, framework_programme, title, description, status,
             type_of_action, deadline, deadline_secondary, indicative_budget,
             budget_currency, source_url, documents_url, keywords, target_audience,
             published_at, scraped_at, last_updated)
        VALUES (%(topic_id)s, %(call_id)s, %(framework_programme)s, %(title)s,
                %(description)s, %(status)s, %(type_of_action)s, %(deadline)s,
                %(deadline_secondary)s, %(indicative_budget)s, %(budget_currency)s,
                %(source_url)s, %(documents_url)s, %(keywords)s, %(target_audience)s,
                %(published_at)s, NOW(), NOW())
        ON CONFLICT (topic_id) DO UPDATE SET
            call_id = EXCLUDED.call_id,
            title = EXCLUDED.title,
            description = EXCLUDED.description,
            status = EXCLUDED.status,
            type_of_action = EXCLUDED.type_of_action,
            deadline = EXCLUDED.deadline,
            keywords = EXCLUDED.keywords,
            last_updated = NOW()
        """,
        payload,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200, help="Max rows to ingest (default 200)")
    ap.add_argument("--apply", action="store_true", help="Write to DB. Default is dry-run.")
    ap.add_argument("--page-size", type=int, default=100)
    ap.add_argument("--status", choices=["forthcoming", "open", "closed", "any"], default="any")
    ap.add_argument("--text", default="*",
                    help="SEDIA full-text query (default '*'). Use '2026' to pull "
                         "only 2026 calls, '2025' for 2025, etc. SEDIA's body-level "
                         "filters/sort aren't honoured by the search endpoint, so "
                         "the text query is the reliable way to scope by year.")
    ap.add_argument("--write-ft", action="store_true",
                    help="Also write the same rows to ft_calls_for_proposals "
                         "(the sibling table backing /api/v1/ft-calls-for-proposals).")
    args = ap.parse_args()

    db = get_env("DATABASE_URL")
    if not db:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)

    status_filter = None
    if args.status != "any":
        status_filter = next((k for k, v in STATUS_MAP.items() if v == args.status), None)

    conn = psycopg2.connect(db)
    cur = conn.cursor()

    rows_seen = 0
    rows_written = 0
    page = 1
    while rows_seen < args.limit:
        data = fetch_sedia_page(page, page_size=args.page_size, status_filter=status_filter, text=args.text)
        if not data:
            break
        results = data.get("results") or []
        if not results:
            break
        for r in results:
            row = normalise_row(r)
            if row is None:
                continue
            rows_seen += 1
            print(f"  [{row['status']:11s}] {row['topic_id']:35s}  {(row['title'] or '')[:60]}")
            if args.apply:
                try:
                    upsert(cur, row)
                    if args.write_ft:
                        upsert_ft_calls(cur, row)
                    rows_written += 1
                except Exception as exc:  # noqa: BLE001
                    print(f"    [DB ERR] {exc}")
                    conn.rollback()
            if rows_seen >= args.limit:
                break
        if args.apply:
            conn.commit()
        if rows_seen >= data.get("totalResults", rows_seen):
            break
        page += 1
        time.sleep(0.4)

    print(f"\n[DONE] seen={rows_seen} written={rows_written} apply={args.apply}")


if __name__ == "__main__":
    main()

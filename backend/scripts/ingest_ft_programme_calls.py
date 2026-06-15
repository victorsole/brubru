"""
Ingest F&T Portal grant calls for a SPECIFIC programme into economy_items.

Some EU funding programmes are on the Funding & Tenders Portal but are NOT
distinguishable in our generic ft_calls_for_proposals store (that table keeps
`framework_programme = programmePeriod`, e.g. "2021 - 2027", which cannot tell
Justice calls from Horizon calls). For programmes that warrant a dedicated
`/api/v2/funding/<slug>` endpoint, we ingest their calls into economy_items —
the canonical funding-item store that already carries the full 5-datapoint
contract and that /api/v2/funding/all already reads (item_type='grant').

The discriminator is the topic_id PREFIX (e.g. JUST-2024-JCOO, INNOVFUND-2024-
NZT-GENERAL-LSP), never the noisy SEDIA full-text match. We query SEDIA with a
set of prefix-anchored texts, then keep only rows whose identifier starts with
the configured prefix.

Source: SEDIA search API (same endpoint the F&T Portal SPA calls under the hood).

    POST https://api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey=SEDIA

Run (dry-run prints what it would write):
    python3.12 backend/scripts/ingest_ft_programme_calls.py --programme justice
    python3.12 backend/scripts/ingest_ft_programme_calls.py --programme innovation-fund --apply
    python3.12 backend/scripts/ingest_ft_programme_calls.py --all --apply
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import sys
import time
from typing import Any, Dict, List

import psycopg2

# Reuse the proven SEDIA fetch + row-normaliser.
from ingest_funding_sedia import fetch_sedia_page, normalise_row, get_env, PORTAL_BASE


# ---------------------------------------------------------------------------
# Programme registry. Each entry = one dedicated /api/v2/funding/<slug>.
#   body_code : economy_items.body_code (lowercase, stable)
#   name      : human programme name (used in the composed body)
#   prefixes  : identifier prefixes that mark a row as this programme
#   queries   : SEDIA full-text queries to paginate (prefix-anchored to limit noise)
# ---------------------------------------------------------------------------
PROGRAMMES: Dict[str, Dict[str, Any]] = {
    "justice": {
        "body_code": "just",
        "name": "Justice Programme",
        "prefixes": ("JUST-",),
        "queries": ["JUST-2021", "JUST-2022", "JUST-2023", "JUST-2024",
                    "JUST-2025", "JUST-2026", "JUST-2027"],
    },
    "innovation-fund": {
        "body_code": "innovfund",
        "name": "Innovation Fund",
        "prefixes": ("INNOVFUND", "INNOVFUND-", "InnovFund"),
        "queries": ["INNOVFUND-", "INNOVFUND-2023", "INNOVFUND-2024",
                    "INNOVFUND-2025", "INNOVFUND-2026", "InnovFund-2021", "InnovFund-2022"],
        # Innovation Fund calls are also F&T-Portal calls — mirror them into
        # ft_calls_for_proposals so the startup-funding feed (/api/v2/funding/
        # startups, which reads that single table) can bundle them in.
        "ft_calls": True,
    },
}

MAX_PAGES_PER_QUERY = 4


def _matches(topic_id: str, prefixes) -> bool:
    tid = (topic_id or "").upper()
    return any(tid.startswith(p.upper()) for p in prefixes)


def compose_body(name: str, row: Dict[str, Any]) -> tuple[str, str]:
    """Build the plain-text and HTML body for one call (the 5-datapoint contract)."""
    title = row.get("title") or ""
    desc = (row.get("description") or "").strip()
    status = row.get("status") or "unknown"
    toa = row.get("type_of_action")
    deadline = row.get("deadline")
    dl_str = deadline.date().isoformat() if isinstance(deadline, dt.datetime) else None
    call_id = row.get("call_id")
    topic_id = row.get("topic_id")

    meta_lines: List[tuple[str, str]] = [("Programme", name), ("Topic", topic_id)]
    if call_id:
        meta_lines.append(("Call", call_id))
    meta_lines.append(("Status", status))
    if toa:
        meta_lines.append(("Type of action", toa))
    if dl_str:
        meta_lines.append(("Deadline", dl_str))

    txt_parts = [title, ""]
    txt_parts += [f"{k}: {v}" for k, v in meta_lines]
    if desc:
        txt_parts += ["", desc]
    body_txt = "\n".join(txt_parts).strip()

    html_meta = "".join(
        f"<li><strong>{html.escape(k)}:</strong> {html.escape(str(v))}</li>" for k, v in meta_lines
    )
    body_html = (
        f"<h1>{html.escape(title)}</h1>"
        f"<ul>{html_meta}</ul>"
        + (f"<div class=\"description\"><p>{html.escape(desc)}</p></div>" if desc else "")
    )
    return body_txt, body_html


def summarise(name: str, row: Dict[str, Any]) -> str:
    status = row.get("status") or "unknown"
    deadline = row.get("deadline")
    bits = [name, status]
    if isinstance(deadline, dt.datetime):
        bits.append(f"deadline {deadline.date().isoformat()}")
    return " · ".join(bits)


UPSERT_SQL = """
INSERT INTO economy_items
    (body_code, item_type, title, summary, public_url, body_txt, body_html,
     document_date, creation_date, source_kind, guid, fetched_at)
VALUES
    (%(body_code)s, 'grant', %(title)s, %(summary)s, %(public_url)s, %(body_txt)s,
     %(body_html)s, %(document_date)s, NOW(), 'sedia', %(guid)s, NOW())
ON CONFLICT (body_code, item_type, public_url) DO UPDATE SET
    title = EXCLUDED.title,
    summary = EXCLUDED.summary,
    body_txt = EXCLUDED.body_txt,
    body_html = EXCLUDED.body_html,
    document_date = EXCLUDED.document_date,
    fetched_at = NOW()
"""


# Mirror into ft_calls_for_proposals (the table /api/v2/funding/startups reads),
# with framework_programme set to the real programme NAME so the feed can label
# it. Keyed on topic_id (the table's unique key).
UPSERT_FT_SQL = """
INSERT INTO ft_calls_for_proposals
    (topic_id, call_id, framework_programme, title, description, status,
     type_of_action, deadline, deadline_secondary, indicative_budget,
     budget_currency, source_url, documents_url, keywords, target_audience,
     published_at, scraped_at, last_updated)
VALUES
    (%(topic_id)s, %(call_id)s, %(framework_programme)s, %(title)s, %(description)s,
     %(status)s, %(type_of_action)s, %(deadline)s, %(deadline_secondary)s,
     %(indicative_budget)s, %(budget_currency)s, %(source_url)s, %(documents_url)s,
     %(keywords)s, %(target_audience)s, %(published_at)s, NOW(), NOW())
ON CONFLICT (topic_id) DO UPDATE SET
    framework_programme = EXCLUDED.framework_programme,
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    status = EXCLUDED.status,
    type_of_action = EXCLUDED.type_of_action,
    deadline = EXCLUDED.deadline,
    keywords = EXCLUDED.keywords,
    last_updated = NOW()
"""


def _ft_payload(name: str, row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "topic_id": row["topic_id"],
        "call_id": row.get("call_id"),
        "framework_programme": name,
        "title": row.get("title") or row["topic_id"],
        "description": row.get("description"),
        "status": row.get("status"),
        "type_of_action": row.get("type_of_action"),
        "deadline": row.get("deadline"),
        "deadline_secondary": row.get("deadline_secondary"),
        "indicative_budget": row.get("indicative_budget"),
        "budget_currency": row.get("budget_currency") or "EUR",
        "source_url": row.get("source_url") or f"{PORTAL_BASE}/{row['topic_id']}",
        "documents_url": row.get("documents_url"),
        "keywords": row.get("keywords") or [],
        "target_audience": row.get("target_audience"),
        "published_at": row.get("published_at"),
    }


def ingest_programme(cur, slug: str, *, apply: bool) -> int:
    cfg = PROGRAMMES[slug]
    name = cfg["name"]
    body_code = cfg["body_code"]
    prefixes = cfg["prefixes"]
    also_ft = bool(cfg.get("ft_calls"))

    seen: Dict[str, Dict[str, Any]] = {}
    for qtext in cfg["queries"]:
        for page in range(1, MAX_PAGES_PER_QUERY + 1):
            data = fetch_sedia_page(page, page_size=100, text=qtext)
            if not data:
                break
            results = data.get("results") or []
            if not results:
                break
            for r in results:
                row = normalise_row(r)
                if row is None:
                    continue
                if not _matches(row["topic_id"], prefixes):
                    continue
                seen[row["topic_id"]] = row
            if len(results) < 100:
                break
            time.sleep(0.3)

    print(f"[{slug}] {len(seen)} distinct {name} calls matched (prefix {prefixes})")
    written = 0
    for topic_id, row in sorted(seen.items()):
        body_txt, body_html = compose_body(name, row)
        public_url = row.get("source_url") or f"{PORTAL_BASE}/{topic_id}"
        payload = {
            "body_code": body_code,
            "title": row.get("title") or topic_id,
            "summary": summarise(name, row),
            "public_url": public_url,
            "body_txt": body_txt,
            "body_html": body_html,
            "document_date": row.get("published_at"),
            "guid": topic_id,
        }
        print(f"  [{row.get('status'):11s}] {topic_id:34s} {(row.get('title') or '')[:48]}")
        if apply:
            cur.execute(UPSERT_SQL, payload)
            if also_ft:
                cur.execute(UPSERT_FT_SQL, _ft_payload(name, row))
            written += 1
    if also_ft:
        print(f"  [{slug}] also mirrored into ft_calls_for_proposals (framework_programme='{name}')")
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--programme", choices=sorted(PROGRAMMES), help="Which programme to ingest")
    ap.add_argument("--all", action="store_true", help="Ingest every registered programme")
    ap.add_argument("--apply", action="store_true", help="Write to DB (default dry-run)")
    args = ap.parse_args()

    if not args.all and not args.programme:
        ap.error("pass --programme <slug> or --all")

    db = get_env("DATABASE_URL")
    if not db:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)

    slugs = sorted(PROGRAMMES) if args.all else [args.programme]
    conn = psycopg2.connect(db)
    cur = conn.cursor()
    total = 0
    for slug in slugs:
        try:
            total += ingest_programme(cur, slug, apply=args.apply)
            if args.apply:
                conn.commit()
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            print(f"  [DB ERR] {slug}: {exc}")
    print(f"\n[DONE] written={total} apply={args.apply}")


if __name__ == "__main__":
    main()

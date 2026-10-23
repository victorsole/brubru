"""
Ingest the Funding & Tenders Portal's calls for funding in cascade into ``ft_cascade_calls``.

EU-funded projects issue open calls of their own (financial support to third parties). The
portal lists them under its calls for proposals as "Calls for funding in cascade (issued by
funded projects)" (SEDIA type 8) and files each under the identifier of the topic that funds it,
so one identifier can carry many different calls (102 under one topic on 23 Oct 2026). Each call
has its own number, `callccm2Id`, which is also the id of the portal's page for it
(competitive-calls-cs/<number>); the record's `ccm2Id` and `url` belong to the topic.

Every English type-8 record is read each run (about 17 pages): the history is kept, closed calls
included (Victor, 23 Oct). A call indexed twice keeps the record read last at the source. Status
comes from the call's own dates, not SEDIA's status field, which lags them (580 of 1,044 current
records on 23 Oct). The page's three text sections are the body; the search record carries them.

The daily tier records this job's run (api/cron.py, _TENDERATOR_CHAIN); the script records none itself.

Run: python3.12 backend/scripts/ingest_ft_cascade_calls.py [--apply] [--dump-json PATH]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import Json

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent))

from ingest_funding_sedia import (  # noqa: E402
    CASCADE_TYPES, _to_number, derive_status, first_or_none, get_env, html_strip, iter_structured,
    load_programme_labels, parse_iso_date, pick_deadlines, programme_label,
)
from services.news.page_widgets import clean_html  # noqa: E402

PAGE_BASE = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/competitive-calls-cs"
# The portal page's sections, in its order, and the record fields that carry them.
SECTIONS = (
    ("Task description", ("description",)),
    ("Submission & evaluation process", ("destinationDetails", "beneficiaryAdministration")),
    ("Further information", ("furtherInformation",)),
)


def _text(md: Dict[str, Any], key: str) -> str:
    return str(first_or_none(md.get(key)) or "").strip()


def body_sections(md: Dict[str, Any]) -> tuple[str, str]:
    """(plain text, HTML) of the page's sections; a section the record leaves empty is left out."""
    texts, htmls = [], []
    for heading, keys in SECTIONS:
        raw = next((first_or_none(md.get(k)) for k in keys if first_or_none(md.get(k))), None)
        if not raw:
            continue
        plain = html_strip(raw, 20000)
        if not plain:
            continue
        texts.append(f"{heading}\n{plain}")
        htmls.append(f"<h2>{heading}</h2>\n{clean_html(raw)}")
    return "\n\n".join(texts), "\n".join(htmls)


def normalise(result: Dict[str, Any], today: Optional[dt.date] = None) -> Optional[Dict[str, Any]]:
    today = today or dt.date.today()
    md = result.get("metadata") or {}
    call_id = _text(md, "callccm2Id")
    title = _text(md, "callTitle") or _text(md, "caName")
    if not call_id or not title or str(first_or_none(md.get("type")) or "") not in CASCADE_TYPES:
        return None
    topic_id = _text(md, "identifier") or None
    deadline, final_deadline = pick_deadlines(md.get("deadlineDate"), today)
    published = parse_iso_date(first_or_none(md.get("startDate")))
    # The dates decide, as for every call (derive_status); no SEDIA flag is passed in.
    status = derive_status(None, published, final_deadline, today)
    text, html = body_sections(md)
    return {
        "call_id": call_id,
        "topic_id": topic_id,
        "title": title,
        "topic_title": _text(md, "title") or None,
        "project_id": _text(md, "projectId") or None,
        "project_acronym": _text(md, "projectAcronym") or None,
        "project_name": _text(md, "projectName") or None,
        "framework_programme": programme_label(md, topic_id or ""),
        "status": status,
        "deadline_model": _text(md, "deadlineModel") or None,
        "published_at": published,
        "deadline": deadline,
        "deadline_secondary": final_deadline if final_deadline and final_deadline != deadline else None,
        "duration": _text(md, "duration") or None,
        "indicative_budget": _to_number(first_or_none(md.get("budget"))),
        "budget_currency": "EUR",
        "source_url": f"{PAGE_BASE}/{call_id}",
        "description": text or None,
        "description_html": html or None,
        "raw": md,
        "_ingested": _text(md, "esDA_IngestDate"),
    }


def collect(pages) -> tuple[Dict[str, Dict[str, Any]], int]:
    """One row per call; a call indexed twice keeps the record the source ingested last."""
    rows: Dict[str, Dict[str, Any]] = {}
    seen = 0
    for _page, results in pages:
        if results is None:
            raise RuntimeError("SEDIA page fetch failed")
        for r in results:
            row = normalise(r)
            if row is None:
                continue
            seen += 1
            held = rows.get(row["call_id"])
            if held is None or row["_ingested"] >= held["_ingested"]:
                rows[row["call_id"]] = row
    return rows, seen


UPSERT = """
INSERT INTO ft_cascade_calls
    (call_id, topic_id, title, topic_title, project_id, project_acronym, project_name,
     framework_programme, status, deadline_model, published_at, deadline, deadline_secondary,
     duration, indicative_budget, budget_currency, source_url, description, description_html, raw)
VALUES (%(call_id)s, %(topic_id)s, %(title)s, %(topic_title)s, %(project_id)s, %(project_acronym)s,
        %(project_name)s, %(framework_programme)s, %(status)s, %(deadline_model)s, %(published_at)s,
        %(deadline)s, %(deadline_secondary)s, %(duration)s, %(indicative_budget)s, %(budget_currency)s,
        %(source_url)s, %(description)s, %(description_html)s, %(raw)s)
ON CONFLICT (call_id) DO UPDATE SET
    topic_id = EXCLUDED.topic_id, title = EXCLUDED.title, topic_title = EXCLUDED.topic_title,
    project_id = EXCLUDED.project_id, project_acronym = EXCLUDED.project_acronym,
    project_name = EXCLUDED.project_name,
    framework_programme = COALESCE(EXCLUDED.framework_programme, ft_cascade_calls.framework_programme),
    status = EXCLUDED.status, deadline_model = EXCLUDED.deadline_model,
    published_at = COALESCE(EXCLUDED.published_at, ft_cascade_calls.published_at),
    deadline = COALESCE(EXCLUDED.deadline, ft_cascade_calls.deadline),
    deadline_secondary = EXCLUDED.deadline_secondary, duration = EXCLUDED.duration,
    indicative_budget = COALESCE(EXCLUDED.indicative_budget, ft_cascade_calls.indicative_budget),
    budget_currency = EXCLUDED.budget_currency, source_url = EXCLUDED.source_url,
    -- A record that comes back without its text keeps the text already held.
    description = COALESCE(EXCLUDED.description, ft_cascade_calls.description),
    description_html = COALESCE(EXCLUDED.description_html, ft_cascade_calls.description_html),
    raw = EXCLUDED.raw, scraped_at = now()
"""


def write(conn, rows: Dict[str, Dict[str, Any]]) -> int:
    cur = conn.cursor()
    for row in rows.values():
        cur.execute(UPSERT, {**{k: v for k, v in row.items() if not k.startswith("_")}, "raw": Json(row["raw"])})
    conn.commit()
    return len(rows)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("--apply", action="store_true", help="Write to the database (default: dry run).")
    ap.add_argument("--dump-json", default=None, help="Write the normalised rows to this file.")
    args = ap.parse_args(argv)
    db = get_env("DATABASE_URL")
    if args.apply and not db:
        print("[FATAL] DATABASE_URL missing")
        return 1
    print(f"[INFO] programme labels: {load_programme_labels()}")
    query = {"bool": {"must": [{"terms": {"type": CASCADE_TYPES}}]}}
    try:
        rows, seen = collect(iter_structured(query, page_size=100, max_pages=60, pause=0.3))
    except RuntimeError as exc:
        print(f"[ERROR] {exc}")
        return 1
    if not rows:
        # An empty index is a failed read, not a portal without cascade calls (1,420 on 23 Oct).
        print("[ERROR] no cascade call read from SEDIA")
        return 1
    by_status: Dict[str, int] = {}
    for r in rows.values():
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    print(f"[INFO] {seen} records, {len(rows)} cascade calls, by status {by_status}")
    if args.dump_json:
        Path(args.dump_json).write_text(json.dumps(rows, default=str, ensure_ascii=False, indent=1))
    if not args.apply:
        print("[DRY-RUN] nothing written (use --apply)")
        return 0
    conn = psycopg2.connect(db)
    try:
        n = write(conn, rows)
    finally:
        conn.close()
    print(f"[OK] {n} cascade calls written")
    return 0


if __name__ == "__main__":
    sys.exit(main())

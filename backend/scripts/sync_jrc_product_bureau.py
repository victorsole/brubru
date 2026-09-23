#!/usr/bin/env python3.12
"""JRC Product Bureau -> the DPP corpus (economy_items, body_code='dpp').

Why (23 September 2026)
-----------------------
The Joint Research Centre's Product Bureau runs the two consultations that
shape the Digital Product Passport before any delegated act exists: the ESPR
methodology consultation (product group 654: eleven methodological reports,
one of them on DPP data requirements, workshops from October 2026) and the
textile products preparatory study (product group 467, including the "Study on
DPP content for textile apparel products under ESPR"). Victor promised Joana
Castella (Terraqui, LIFE DPP-TEX) on 11 September that her DPP connector would
answer about them. Nothing was ingested.

What it writes (idempotent: unique on body_code + item_type + public_url)
- item_type 'event'              one row per consultation workshop in the
                                 indicative plan (dated to the day when the page
                                 gives a day, else the first of the month, and the
                                 title says which)
- item_type 'jrc_report'         the methodological reports open for comment
- item_type 'jrc_study_document' the textile preparatory study documents

The pages are behind a WAF that rejects plain requests ("Request Rejected"), so
they are rendered with the project's Playwright fetcher.

A run that parses nothing from a page is a FAILURE, recorded in sync_runs: the
calendar and the document lists are never legitimately empty.

Usage (from backend/):
    python3.12 scripts/sync_jrc_product_bureau.py            # write
    python3.12 scripts/sync_jrc_product_bureau.py --dry-run  # parse and print only
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import text  # noqa: E402

BASE = "https://susproc.jrc.ec.europa.eu/product-bureau/product-groups"
PAGES = {
    "plan": f"{BASE}/654/project-plan",
    "methods": f"{BASE}/654/documents",
    "textiles": f"{BASE}/467/documents",
}
SOURCE_KEY = "jrc_product_bureau"
_MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"], start=1)}
_FOOTER = re.compile(r"^(This site is managed|Contact the European|Dates are indicative)")


def _lines(text_: str) -> list[str]:
    return [l.strip() for l in text_.splitlines() if l.strip()]


def _slug(s: str, n: int = 60) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:n]


def parse_plan(page_text: str, url: str) -> list[dict]:
    """The indicative consultation plan: month headers, then either
    "23 October (9:00-13:00): <method>" lines or bare method lines for a
    one-day month, closed by a "Format:" line."""
    out, year, month, fmt_pending = [], None, None, []
    lines = _lines(page_text)
    try:
        start = next(i for i, l in enumerate(lines) if l.startswith("Stakeholder consultations"))
    except StopIteration:
        return []
    for l in lines[start + 1:]:
        if _FOOTER.match(l):
            break
        m = re.match(r"^(January|February|March|April|May|June|July|August|September|October|"
                     r"November|December) (\d{4})\b", l)
        if m:
            month, year = _MONTHS[m.group(1)], int(m.group(2))
            continue
        if l.startswith("Format:"):
            for row in fmt_pending:
                row["summary"] += " " + l
            fmt_pending = []
            continue
        if not year:
            continue
        d = re.match(r"^(\d{1,2}) (January|February|March|April|May|June|July|August|September|"
                     r"October|November|December)\s*(\(([^)]*)\))?:\s*(.+)$", l)
        if d:
            day = dt.date(year, _MONTHS[d.group(2)], int(d.group(1)))
            topic, hours = d.group(5).strip(), d.group(4)
            when = f"{day.day} {d.group(2)} {year}" + (f", {hours} CET" if hours else "")
            exact = True
        else:
            day, topic, exact = dt.date(year, month, 1), l, False
            when = f"{day.strftime('%B')} {year} (day not yet fixed)"
        row = {
            "item_type": "event",
            "title": f"JRC ESPR methodology consultation workshop, {when}: {topic}",
            "summary": (f"Online workshop of the JRC Product Bureau consultation on the ESPR "
                        f"methodological reports ({'date fixed' if exact else 'indicative month'}). "
                        "Registered stakeholders receive the questionnaire link after the workshop; "
                        "written comments stay open for about 1.5 months."),
            "document_date": day,
            "public_url": f"{url}#{day.isoformat()}-{_slug(topic, 40)}",
        }
        out.append(row)
        fmt_pending.append(row)
    return out


def parse_methods(page_text: str, url: str) -> list[dict]:
    """"Authors, Title, Publisher, year, JRC-id — https://doi..." citations.

    Every title starts "Method", "Methods" or "Developing a method", which is
    the only reliable boundary: author lists vary in shape ("Magrini, C. and
    Gama Caldas, M.", "Chwala, K., Chirvasuta T., ..."). The year is known,
    the day is not, so no date is invented; the year goes in the summary.
    """
    out = []
    for l in _lines(page_text):
        m = re.match(r"^(.+?)\s+[—-]\s+(https?://\S+)$", l)
        if not m:
            continue
        cite, link = m.group(1), m.group(2)
        tm = re.search(r"((?:Developing a method|Methods?) (?:for|of)\b.+?)(?:, (?:Publications Office|TNO)\b|$)", cite)
        if not tm:
            continue
        year = re.search(r"\b(20\d{2})\b", cite[tm.end():] or cite)
        out.append({
            "item_type": "jrc_report",
            "title": f"JRC ESPR methodological report: {tm.group(1).strip()}",
            "summary": (f"Open for stakeholder consultation (JRC Product Bureau)"
                        + (f", published {year.group(1)}" if year else "") + f". Citation: {cite}"),
            "document_date": None,
            "public_url": link,
        })
    return out


def parse_textiles(page_text: str, html: str, url: str) -> list[dict]:
    """ECL file blocks: title, file name, YYYY-MM-DD, language, then the link."""
    from bs4 import BeautifulSoup
    out = []
    for info in BeautifulSoup(html or "", "html.parser").select("div.ecl-file__info"):
        title_el = info.select_one(".ecl-file__title")
        props = [p.get_text(strip=True) for p in info.select(".ecl-file__properties")]
        date_s = next((p for p in props if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p)), None)
        a = info.find_next("a", href=True)
        if not title_el or not a:
            continue
        link = a["href"]
        if link.startswith("/"):
            link = "https://susproc.jrc.ec.europa.eu" + link
        fname = props[0] if props else ""
        out.append({
            "item_type": "jrc_study_document",
            "title": f"JRC textile products preparatory study: {title_el.get_text(strip=True)}",
            "summary": f"Document of the JRC preparatory study on textile products under ESPR (file {fname}).",
            "document_date": dt.date.fromisoformat(date_s) if date_s else None,
            "public_url": link,
        })
    return out


def _fetch(url: str) -> tuple[str, str]:
    from services.scrapers.waf_browser_fetcher import fetch_one
    r = fetch_one(url, expand_accordions=False, strip_chrome=False)
    if not getattr(r, "ok", False):
        raise RuntimeError(f"fetch failed for {url} (status {getattr(r, 'nav_status', None)})")
    return (getattr(r, "text", "") or ""), (getattr(r, "html", "") or "")


def upsert(db, rows: list[dict]) -> int:
    new = 0
    for r in rows:
        res = db.execute(text("""
            INSERT INTO economy_items (body_code, item_type, title, summary, public_url, document_date,
                                       creation_date, fetched_at, source_kind, guid)
            VALUES ('dpp', :t, :title, :summary, :url, :d, now(), now(), 'html', :guid)
            ON CONFLICT (body_code, item_type, public_url) DO UPDATE
               SET title = EXCLUDED.title, summary = EXCLUDED.summary,
                   document_date = EXCLUDED.document_date, fetched_at = now()
            RETURNING (xmax = 0) AS inserted"""),
            {"t": r["item_type"], "title": r["title"][:1000], "summary": r["summary"],
             "url": r["public_url"], "d": r["document_date"],
             "guid": f"jrc-pb-{_slug(r['public_url'], 90)}"}).scalar()
        new += int(bool(res))
    db.commit()
    return new


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    started = dt.datetime.now(dt.timezone.utc)
    parsed, problems = {}, []
    try:
        t, _ = _fetch(PAGES["plan"])
        parsed["plan"] = parse_plan(t, PAGES["plan"])
        t, _ = _fetch(PAGES["methods"])
        parsed["methods"] = parse_methods(t, PAGES["methods"])
        t, h = _fetch(PAGES["textiles"])
        parsed["textiles"] = parse_textiles(t, h, PAGES["textiles"])
    except Exception as exc:  # noqa: BLE001 -- recorded below, then re-raised
        problems.append(f"{type(exc).__name__}: {exc}"[:300])
    for k, v in parsed.items():
        if not v:
            problems.append(f"nothing parsed from {k}")
    for k, v in parsed.items():
        print(f"[INFO] {k}: {len(v)} item(s)")
        for r in v:
            print(f"   {r['document_date']}  {r['item_type']:<19} {r['title'][:110]}")
    if a.dry_run:
        return 1 if problems else 0

    from core.database import SessionLocal
    from services.sync.freshness import record_run
    db = SessionLocal()
    try:
        rows = [r for v in parsed.values() for r in v]
        new = upsert(db, rows) if rows else 0
        status = "failed" if (problems and not rows) else ("degraded" if problems else "success")
        record_run(db, source_key=SOURCE_KEY, tier="daily", status=status, items_added=new,
                   error="; ".join(problems) or None, started_at=started)
        print(f"[{'OK' if status == 'success' else status.upper()}] {len(rows)} rows, {new} new"
              + (f"; {'; '.join(problems)}" if problems else ""))
    finally:
        db.close()
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

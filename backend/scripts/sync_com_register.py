#!/usr/bin/env python3.12
"""COM-register radar: which Commission documents exist on the register that we do not hold yet?

Why (9 Oct 2026). COM(2026) 546 final, the fifth annual report on the Recovery and Resilience Facility,
is dated 7 October. A client found it on LinkedIn on the 9th. Brubru discovers COM documents through
Cellar and EUR-Lex RSS, and Cellar did not hold the record until the morning of the 9th, two days after
its date: a Cellar-only radar cannot see a COM document on the day it is adopted, and it cannot tell
"nothing was adopted" from "Cellar has not caught up". The Commission's own document register lists a
COM document on its date (verified the same day: four documents dated 9 Oct were there before Cellar
held any of them), so this reads the register and diffs it against commission_documents.

It reports; it does not ingest. A document stays "on the register, not in our store" until Cellar has it
and the normal sync stores it, and that interval is exactly what this makes visible. It also records when
the register FIRST showed each document (com_register_seen, migration 287), so the lead over Cellar can be
measured instead of assumed.

Usage (from backend/):
    python3.12 scripts/sync_com_register.py                 # dry-run report, no writes
    python3.12 scripts/sync_com_register.py --days 14       # look back 14 days of document dates
    python3.12 scripts/sync_com_register.py --apply         # also record what the register showed (com_register_seen)
    python3.12 scripts/sync_com_register.py --apply --record   # and one sync_runs row (the daily cron passes both)

Exit code: 0 ok; 1 the register could not be read or returned nothing (a job that stores nothing must fail).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import re
import sys
import urllib.request
from typing import Callable

logging.disable(logging.WARNING)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

SOURCE_KEY = "com_register"
BASE = "https://ec.europa.eu/transparency/documents-register"
SEARCH = f"{BASE}/api/groupSearch"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")
PAGE_SIZE = 50
MAX_PAGES = 8

# The payload the register UI posts, with the COM category. Same endpoint and same strictness as the
# College agenda job (scripts/sync_college_tentative_agendas.py): keep the shape.
QUERY = {
    "categories": ["COM"], "types": [], "departments": [], "language": "en",
    "keywordsSearchType": "AT_LEAST_ONE", "target": "TITLE_AND_CONTENT",
    "sortBy": "DOCUMENT_DATE_DESC", "isRegular": True,
}

_REF = re.compile(r"COM\((\d{4})\)\s*(\d+)", re.I)
# COM documents in commission_documents are stored under their CELEX (5YYYY + PC or DC + 4 digits) or
# as "COM(YYYY) N". SC is a staff working document and JC a joint communication: separate number
# series that would collide with COM numbers, so they are never counted as holding a COM document.
_HELD_CELEX = re.compile(r"^5(\d{4})(?:PC|DC)(\d{4})$")


# --------------------------------------------------------------------------
# Pure functions (tested without a network or a database)
# --------------------------------------------------------------------------

def ref_parts(reference: str) -> tuple[int, int] | None:
    m = _REF.search(reference or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def eurlex_url(year: int, number: int) -> str:
    return f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=COM:{year}:{number}:FIN"


def english_title(doc: dict) -> str | None:
    """The English title of the main attachment; the list response carries none at top level."""
    for att in doc.get("attachments") or []:
        if att.get("main"):
            for lang in ("en", att.get("original")):
                t = ((att.get("linguisticVersions") or {}).get(lang) or {}).get("title")
                if t:
                    return " ".join(str(t).split())
    for att in doc.get("attachments") or []:
        t = ((att.get("linguisticVersions") or {}).get("en") or {}).get("title")
        if t:
            return " ".join(str(t).split())
    return None


def parse_doc(doc: dict) -> dict | None:
    """One register entry as a flat dict, or None when it has no usable COM reference or date."""
    parts = ref_parts(doc.get("reference") or "")
    date_s = str(doc.get("date") or "")[:10]
    try:
        d = dt.date.fromisoformat(date_s)
    except ValueError:
        return None
    if not parts:
        return None
    year, number = parts
    return {
        "reference": f"COM({year}){number}", "year": year, "number": number,
        "doc_type": doc.get("type") or "", "doc_date": d, "department": doc.get("responsibleDepartment"),
        "version": doc.get("version"), "celex": doc.get("celex") or None,
        "title": english_title(doc), "url": doc.get("url"),
        "latest": doc.get("isLatestVersion", True),
    }


def held_numbers(references: list[str]) -> set[tuple[int, int]]:
    """(year, number) of every COM document our store already holds, from its stored reference."""
    held: set[tuple[int, int]] = set()
    for r in references:
        m = _HELD_CELEX.match(r or "")
        if m:
            held.add((int(m.group(1)), int(m.group(2))))
            continue
        parts = ref_parts(r or "") if (r or "").upper().startswith("COM(") else None
        if parts:
            held.add(parts)
    return held


def missing(entries: list[dict], held: set[tuple[int, int]], today: dt.date, days: int) -> list[dict]:
    """Register entries dated inside the window that our store does not hold, newest first."""
    since = today - dt.timedelta(days=days)
    out = [e for e in entries
           if e["doc_date"] >= since and (e["year"], e["number"]) not in held and e.get("latest", True)]
    return sorted(out, key=lambda e: (e["doc_date"], e["number"]), reverse=True)


def fetch_pages(post: Callable[[int], dict], today: dt.date, days: int,
                max_pages: int = MAX_PAGES) -> tuple[list[dict], dict]:
    """Newest COM entries until the oldest date reaches past the window (plus a margin), or max_pages.

    The register can return fewer documents than it claims, so coverage is MEASURED, not assumed: the
    result says how far back the pages actually reached. Raises when page 1 holds nothing."""
    cutoff = today - dt.timedelta(days=days + 3)
    entries: dict[str, dict] = {}
    unparsed = 0
    pages = 0
    reached = None
    for page in range(1, max_pages + 1):
        body = post(page)
        docs = body.get("documents") or []
        if page == 1 and not docs:
            raise RuntimeError("the register answered but listed no COM documents")
        pages += 1
        for raw in docs:
            e = parse_doc(raw)
            if e is None:
                unparsed += 1
                continue
            prev = entries.get(e["reference"])
            if prev is None or (e.get("latest") and not prev.get("latest")):
                entries[e["reference"]] = e
        dates = [parse_doc(r)["doc_date"] for r in docs if parse_doc(r)]
        if dates:
            reached = min(dates)
            if reached < cutoff:
                break
        if len(docs) < PAGE_SIZE:
            break
    meta = {"pages": pages, "unparsed": unparsed, "oldest": reached,
            "covers_window": bool(reached and reached <= today - dt.timedelta(days=days))}
    return list(entries.values()), meta


# --------------------------------------------------------------------------
# I/O
# --------------------------------------------------------------------------

def _post(page: int) -> dict:
    body = dict(QUERY, page=page)
    req = urllib.request.Request(
        f"{SEARCH}?size={PAGE_SIZE}&page={page}", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": UA},
        method="POST")
    import ssl
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        ctx = None
    with urllib.request.urlopen(req, timeout=90, context=ctx) as r:
        return json.load(r)


def cellar_numbers(days: int) -> set[tuple[int, int]] | None:
    """(year, number) of every COM document Cellar holds with a document date in the window, or None when
    Cellar could not be read (then the state of each missing entry is reported as unknown, never guessed)."""
    try:
        import asyncio
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import cellar_news_helper as h
        res = asyncio.run(h.oj_today(days + 3, None, "5", 3000))
        if res.get("query_failed"):
            return None
        out: set[tuple[int, int]] = set()
        for act in res.get("acts") or []:
            m = _HELD_CELEX.match(act.get("celex") or "")
            if m:
                out.add((int(m.group(1)), int(m.group(2))))
        return out
    except Exception:  # noqa: BLE001
        return None


def state_of(e: dict, in_cellar: set[tuple[int, int]] | None) -> str:
    """Why a register entry is not in our store: Cellar lag (the blind spot), an ingestion gap, or unknown."""
    if in_cellar is None:
        return "cellar state unknown"
    return "in Cellar, never ingested" if (e["year"], e["number"]) in in_cellar else "NOT IN CELLAR YET"


def load_held(db) -> set[tuple[int, int]]:
    from sqlalchemy import text
    refs = [r[0] for r in db.execute(text(
        "SELECT reference FROM commission_documents "
        "WHERE reference ~ '^5[0-9]{4}(PC|DC)[0-9]{4}$' OR reference ~* '^COM\\([0-9]{4}\\)'"))]
    return held_numbers(refs)


def record_seen(db, entries: list[dict], held: set[tuple[int, int]], in_cellar: set[tuple[int, int]] | None) -> int:
    """Upsert what the register showed. first_seen_at is when THIS job first saw the entry."""
    from sqlalchemy import text
    n = 0
    for e in entries:
        db.execute(text("""
            INSERT INTO com_register_seen
                (reference, doc_year, doc_number, doc_type, doc_date, department, version, title, celex, url,
                 celex_first_seen_at, cellar_first_seen_at, held_first_seen_at)
            VALUES (:ref, :y, :n, :t, :d, :dep, :ver, :title, :celex, :url,
                    CASE WHEN CAST(:celex AS TEXT) IS NOT NULL THEN now() END,
                    CASE WHEN :cel THEN now() END,
                    CASE WHEN :held THEN now() END)
            ON CONFLICT (reference) DO UPDATE SET
                last_seen_at = now(),
                doc_type = EXCLUDED.doc_type, doc_date = EXCLUDED.doc_date,
                department = EXCLUDED.department, version = EXCLUDED.version,
                title = COALESCE(EXCLUDED.title, com_register_seen.title),
                url = COALESCE(EXCLUDED.url, com_register_seen.url),
                celex = COALESCE(EXCLUDED.celex, com_register_seen.celex),
                celex_first_seen_at = COALESCE(com_register_seen.celex_first_seen_at,
                                               CASE WHEN EXCLUDED.celex IS NOT NULL THEN now() END),
                cellar_first_seen_at = COALESCE(com_register_seen.cellar_first_seen_at,
                                                CASE WHEN :cel THEN now() END),
                held_first_seen_at = COALESCE(com_register_seen.held_first_seen_at,
                                              CASE WHEN :held THEN now() END)"""),
            {"ref": e["reference"], "y": e["year"], "n": e["number"], "t": e["doc_type"], "d": e["doc_date"],
             "dep": e["department"], "ver": e["version"], "title": e["title"], "celex": e["celex"],
             "url": e["url"], "held": (e["year"], e["number"]) in held,
             "cel": bool(in_cellar is not None and (e["year"], e["number"]) in in_cellar)})
        n += 1
    db.commit()
    return n


def known_before(db, references: list[str]) -> set[str]:
    from sqlalchemy import text
    if not references:
        return set()
    return {r[0] for r in db.execute(text("SELECT reference FROM com_register_seen WHERE reference = ANY(:r)"),
                                     {"r": references})}


def _record(status: str, error: str | None, added: int, started: dt.datetime) -> None:
    from core.database import SessionLocal
    from services.sync.freshness import record_run
    db = SessionLocal()
    try:
        record_run(db, source_key=SOURCE_KEY, tier="hot_6h", status=status, items_added=added,
                   error=error, started_at=started)
    finally:
        db.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--days", type=int, default=10, help="document-date window to check (default 10)")
    ap.add_argument("--apply", action="store_true", help="record what the register showed in com_register_seen")
    ap.add_argument("--record", action="store_true",
                    help="also write one sync_runs row (the daily cron passes both; a local run should not claim to be it)")
    ap.add_argument("--limit", type=int, default=25, help="rows printed")
    a = ap.parse_args()
    started = dt.datetime.now(dt.timezone.utc)
    today = dt.date.today()

    try:
        entries, meta = fetch_pages(_post, today, a.days)
    except Exception as e:  # noqa: BLE001
        msg = f"register unreadable: {type(e).__name__}: {str(e)[:160]}"
        print(f"[ERROR] {msg}")
        if a.record:
            _record("failed", msg, 0, started)
        return 1

    from core.database import SessionLocal
    db = SessionLocal()
    try:
        held = load_held(db)
        gone = missing(entries, held, today, a.days)
        in_cellar = cellar_numbers(a.days)
        fresh_refs = known_before(db, [e["reference"] for e in entries])
        recorded = record_seen(db, entries, held, in_cellar) if a.apply else 0
    finally:
        db.close()

    window = [e for e in entries if e["doc_date"] >= today - dt.timedelta(days=a.days)]
    print(f"COM-REGISTER RADAR  {today}   (document dates from {today - dt.timedelta(days=a.days)})")
    print("=" * 78)
    print(f"register: {len(entries)} COM entries read in {meta['pages']} page(s), oldest {meta['oldest']}"
          f"{'' if meta['covers_window'] else '  [WARN: pages did not reach back to the start of the window]'}")
    print(f"window  : {len(window)} entries; our store holds {len(held)} COM numbers in all")
    for e in gone:
        e["state"] = state_of(e, in_cellar)
    lag = [e for e in gone if e["state"] == "NOT IN CELLAR YET"]
    gap = [e for e in gone if e["state"] == "in Cellar, never ingested"]
    unk = [e for e in gone if e["state"] == "cellar state unknown"]
    print(f"missing : {len(gone)} on the register but NOT in our store:")
    print(f"          {len(lag):>3}  NOT IN CELLAR YET   <- the blind spot: no Cellar-based radar can see these")
    print(f"          {len(gap):>3}  in Cellar, never ingested  (a coverage gap in commission_documents, API session)")
    if unk:
        print(f"          {len(unk):>3}  Cellar could not be read, state unknown")
    new_on_register = [e for e in lag if e["reference"] not in fresh_refs]
    if a.apply:
        print(f"new to this radar: {len(new_on_register)}   recorded: {recorded}")
    print("\nNOT IN CELLAR YET (newest first):")
    for e in lag[:a.limit]:
        flag = "NEW " if e["reference"] not in fresh_refs else "    "
        print(f"  {flag}{e['doc_date']}  {e['reference']:<14} {e['doc_type']:<14} {str(e['department'] or '-'):<8} "
              f"{str(e['title'] or '(no title)')[:84]}")
        print(f"         read it: {eurlex_url(e['year'], e['number'])}")
    if not lag:
        print("  (none)")
    if len(lag) > a.limit:
        print(f"  ... and {len(lag) - a.limit} more (--limit)")
    if gap:
        print(f"\nin Cellar, never ingested: {len(gap)} (first {min(len(gap), 5)}): "
              + ", ".join(e['reference'] for e in gap[:5]))
    if unparsed := meta["unparsed"]:
        print(f"[WARN] {unparsed} register entr{'y' if unparsed == 1 else 'ies'} could not be parsed and were skipped")

    problems = []
    if not meta["covers_window"]:
        problems.append("pages did not reach the start of the window")
    if meta["unparsed"]:
        problems.append(f"{meta['unparsed']} unparsed")
    if in_cellar is None:
        problems.append("Cellar unreadable, lag not separated from coverage gap")
    if a.record:
        names = ", ".join(e["reference"] for e in lag[:12])
        _record("degraded" if problems else "success",
                ("; ".join(problems) + ". " if problems else "")
                + (f"AHEAD OF CELLAR: {names}" if names else "nothing ahead of Cellar")
                + f" ({len(new_on_register)} new this run; {len(gap)} in Cellar but never ingested)",
                len(new_on_register), started)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

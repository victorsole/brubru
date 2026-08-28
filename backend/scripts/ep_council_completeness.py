#!/usr/bin/env python3.12
"""Gap detector for the EP and Council text corpora.

Why this exists
---------------
Every defect fixed on 27 August 2026 was a corpus that looked fine. The endpoints
returned 200, the rows were well formed, and nothing in the system said anything
was missing:

  * `/api/v1/council-documents` served a CALENDAR for months, because its
    documents branch held zero rows.
  * `texts_adopted` opened on 20 January 2026, so the EP's November 2025
    resolution on protecting minors online was invisible to every search.
  * A backfill I ran myself left an eight-week hole across December 2025 and
    February 2026. The run reported "292 dates, 0 errors" -- true, and useless,
    because the range itself was wrong.
  * 47 stored bodies were a language picker, which passes every length,
    non-null and distinctness check.

A backfill that reports success over its own range proves nothing about the
range. This asks the opposite question: given what we hold, what is MISSING?

It is deliberately loud and deliberately specific. Each check names the rows it
is complaining about, so the fix is a command rather than an investigation.

Exit codes:
    0  no gaps, or only gaps explained by the EU calendar (August recess)
    1  at least one real gap -- the cron records this and /api/sync/health shows it

Usage:
    python3.12 scripts/ep_council_completeness.py
    python3.12 scripts/ep_council_completeness.py --json
"""
import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR.parent / ".env")

# The Parliament does not sit in August. A month with no adopted texts is only a
# gap OUTSIDE recess -- encoding the calendar is what stops this alerting every
# summer and being switched off.
RECESS_MONTHS = {8}
# Council documents are pulled per policy term + press feed; more than this
# without a single new document means the ingest has stopped, not that the
# Council fell silent.
COUNCIL_STALE_DAYS = 10


def _engine():
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("[ERROR] DATABASE_URL not set")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return create_engine(url, pool_pre_ping=True)


def _months_between(lo: date, hi: date):
    y, m = lo.year, lo.month
    while (y, m) <= (hi.year, hi.month):
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1


def run_checks(conn) -> list[dict]:
    """Each check returns a dict; `gap` True means something is genuinely missing."""
    out: list[dict] = []

    def add(name, gap, detail, fix=None):
        out.append({"check": name, "gap": bool(gap), "detail": detail, "fix": fix})

    # --- 1. EP: a month inside the corpus window with no adopted texts -------
    lo, hi = conn.execute(text(
        "SELECT min(adoption_date)::date, max(adoption_date)::date FROM texts_adopted"
    )).fetchone()
    if not lo:
        add("ep.corpus_exists", True, "texts_adopted holds no dated rows at all",
            "scripts/sync_texts_adopted.py --date-range <from> <to>")
    else:
        have = {r[0] for r in conn.execute(text(
            "SELECT to_char(adoption_date,'YYYY-MM') FROM texts_adopted "
            "WHERE adoption_date IS NOT NULL GROUP BY 1"))}
        missing = [f"{y:04d}-{m:02d}" for y, m in _months_between(lo, hi)
                   if f"{y:04d}-{m:02d}" not in have and m not in RECESS_MONTHS]
        add("ep.no_month_gaps", bool(missing),
            (f"{len(missing)} month(s) inside {lo}..{hi} have no adopted text: "
             f"{', '.join(missing[:6])}" if missing
             else f"every non-recess month between {lo} and {hi} has texts"),
            "scripts/sync_texts_adopted.py --date-range <month-start> <month-end>")

    # --- 2. EP: bodies -------------------------------------------------------
    n, with_body = conn.execute(text(
        "SELECT count(*), count(full_text) FROM texts_adopted")).fetchone()
    add("ep.every_text_has_a_body", with_body < n,
        f"{with_body}/{n} adopted texts hold their real text",
        "scripts/backfill_texts_adopted_bodies.py --apply")

    # --- 3. EP: bodies that are actually navigation --------------------------
    chrome = conn.execute(text(
        "SELECT count(*) FROM texts_adopted WHERE full_text IS NOT NULL AND ("
        "  left(full_text,500) ILIKE '%Choisissez la langue%' OR"
        "  left(full_text,400) ILIKE '%we use cookies%' OR"
        "  left(full_text,400) ILIKE '%skip to main%')")).scalar()
    add("ep.no_chrome_stored_as_text", chrome > 0,
        f"{chrome} stored bod(y|ies) are page furniture, not documents",
        "clear those rows' full_text and re-run backfill_texts_adopted_bodies.py")

    # --- 4. EP: the resolutions corpus tracks the adopted texts --------------
    missing_res = conn.execute(text(r"""
        SELECT count(*) FROM texts_adopted t
        WHERE t.text_type::text IN ('resolution','legislative_resolution')
          AND t.procedure_ref IS NOT NULL
          AND substring(t.procedure_ref from '\(([A-Z]+)\)') IN ('INI','RSP','INL')
          AND NOT EXISTS (SELECT 1 FROM ep_resolutions r
                          WHERE r.procedure_ref = t.procedure_ref)""")).scalar()
    add("ep.resolutions_corpus_complete", missing_res > 0,
        f"{missing_res} INI/RSP/INL adopted text(s) have no ep_resolutions row",
        "scripts/backfill_ep_resolutions_corpus.py --apply")

    # --- 5. EP: an adopted resolution with no date ---------------------------
    undated = conn.execute(text("""
        SELECT count(*) FROM ep_resolutions r
        WHERE r.adoption_date IS NULL
          AND EXISTS (SELECT 1 FROM texts_adopted t
                      WHERE t.procedure_ref = r.procedure_ref
                        AND t.adoption_date IS NOT NULL)""")).scalar()
    add("ep.no_adopted_resolution_is_undated", undated > 0,
        f"{undated} resolution(s) are undated although their adopted text has a date",
        "scripts/backfill_resolution_dates.py --apply")

    # --- 6. Council: the documents branch is not empty -----------------------
    council = conn.execute(text(
        "SELECT count(*) FROM institutional_publications "
        "WHERE institution_slug ILIKE '%council%'")).scalar()
    add("council.documents_branch_not_empty", council == 0,
        f"{council} Council document(s) held",
        "scripts/ingest_council_documents.py --apply")

    # --- 7. Council: freshness ----------------------------------------------
    newest = conn.execute(text(
        "SELECT max(published_date)::date FROM institutional_publications "
        "WHERE institution_slug ILIKE '%council%'")).scalar()
    age = (date.today() - newest).days if newest else None
    add("council.corpus_is_fresh", age is None or age > COUNCIL_STALE_DAYS,
        (f"newest Council document is {age} day(s) old ({newest})" if newest
         else "no dated Council document at all"),
        "scripts/ingest_council_documents.py --since-days 14 --apply")

    # --- 8. Council: bodies --------------------------------------------------
    cn, cb = conn.execute(text(
        "SELECT count(*), count(html_content) FROM institutional_publications "
        "WHERE institution_slug ILIKE '%council%'")).fetchone()
    add("council.every_document_has_a_body", cb < cn,
        f"{cb}/{cn} Council documents hold their text",
        "scripts/ingest_council_documents.py --fetch-bodies --apply")

    # --- 9. EP: committee agendas hold the agenda document -------------------
    # Counted only against agendas that HAVE a document URL. 40 of the 226 carry
    # a committee homepage as their only link, and a homepage is not a missing
    # agenda -- folding those in would make the check permanently red.
    ag_total, ag_cached = conn.execute(text(
        "SELECT count(*) FILTER (WHERE agenda_url IS NOT NULL), "
        "       count(*) FILTER (WHERE agenda_url IS NOT NULL "
        "                          AND related_documents ? 'agenda_body_txt') "
        "FROM eu_calendar_events WHERE source = 'ep_committee_agenda'")).fetchone()
    add("ep.agendas_hold_their_document", ag_cached < ag_total,
        f"{ag_cached}/{ag_total} committee agendas with a document URL hold its text",
        "scripts/backfill_committee_agenda_bodies.py --apply")

    # --- 10. Carriages: OEIL roles parsed where the page is stored ------------
    unparsed = conn.execute(text(
        "SELECT count(*) FROM legislative_carriages "
        "WHERE oeil_text_body IS NOT NULL AND oeil_roles_parsed_at IS NULL")).scalar()
    add("carriages.roles_parsed", unparsed > 0,
        f"{unparsed} carriage(s) have a stored OEIL page whose roles were never parsed",
        "scripts/backfill_oeil_committee_roles.py --apply")

    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    with _engine().connect() as conn:
        results = run_checks(conn)

    gaps = [r for r in results if r["gap"]]
    if args.json:
        print(json.dumps({"gaps": len(gaps), "checks": results}, default=str))
    else:
        for r in results:
            mark = "GAP " if r["gap"] else "ok  "
            print(f"[{mark}] {r['check']:42} {r['detail']}")
            if r["gap"] and r["fix"]:
                print(f"         fix: {r['fix']}")
        print(f"\n>>> {len(gaps)} GAP(S) of {len(results)} checks")

    # Non-zero so the cron records a failure rather than a quiet success.
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())

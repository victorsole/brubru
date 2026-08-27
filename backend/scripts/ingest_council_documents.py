#!/usr/bin/env python3.12
"""Ingest real Council of the EU documents into `institutional_publications`.

Why (D1)
--------
`/api/v1/council-documents` unions two branches. Branch 1 reads Council-tagged
`institutional_publications` and has held **0 rows since it shipped**; branch 2
reads `eu_calendar_events` and holds 61 Council MEETINGS. So a documents-named
endpoint has only ever served a calendar, and `?q=minors` returned 200 with an
empty list -- from which a caller concludes the Council has said nothing about
minors online. It has: 25 Member States and 2 EFTA countries signed the Jutland
Declaration on 10 October 2025 (Council doc ST 15875/25).

This fills branch 1.

Coverage
--------
Breadth comes from ENUMERATING the register by date window
(`?DateFrom=..&DateTo=..&page=N`), not from guessing vocabulary.

The first version of this script searched Brubru's 35 policy-area LABELS. It
ingested 222 documents and STILL returned nothing for "minors", because a policy
domain ("Single Market", "Digital and Technology") is not a word that appears in
a document's subject line. A term-driven corpus is only ever as good as the term
list, and there is no term list that covers what users ask.

The register caps any result set at 1,000 documents (50 pages x 20). A window
that hits the cap is reported by name so it can be re-run narrower -- it is never
silently truncated.

Targeted `--terms` remain, searching BOTH the subject line and the full text, for
closing a specific known gap.

Usage:
    python3.12 scripts/ingest_council_documents.py                          # dry-run
    python3.12 scripts/ingest_council_documents.py --apply
    python3.12 scripts/ingest_council_documents.py --since 2025-09-01 --window-days 15 --apply
    python3.12 scripts/ingest_council_documents.py --no-window --terms minors --apply
"""
import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR.parent / ".env")

from services.scrapers.council_register import (  # noqa: E402
    CouncilDoc, fetch_by_reference, fetch_document_text, fetch_press_releases, search_by_date,
    search_full_text, search_register,
)

logger = logging.getLogger("ingest_council_documents")

INSTITUTION_SLUG = "council_of_the_eu"   # matches COUNCIL_INSTITUTION_SLUGS in the API
SOURCE_REGISTER = "consilium_register"
SOURCE_PRESS = "consilium_press"

# `ON CONFLICT (source_slug, external_id)` -- the table's real unique index.
# COALESCE on update so a later run that cannot re-derive a field does not blank
# a good value it already had.
_UPSERT = """
INSERT INTO institutional_publications
    (id, source_slug, institution_slug, category, external_id, url, title,
     summary, html_content, language, published_date, policy_areas, tags, extra_metadata,
     fetched_at, created_at)
VALUES
    (gen_random_uuid(), :source, :inst, :category, :ext_id, :url, :title,
     :summary, :body, 'en', :published, :policy_areas, :tags, CAST(:meta AS jsonb),
     now(), now())
ON CONFLICT (source_slug, external_id) DO UPDATE SET
    title         = EXCLUDED.title,
    url           = EXCLUDED.url,
    category      = EXCLUDED.category,
    summary       = COALESCE(EXCLUDED.summary, institutional_publications.summary),
    html_content  = COALESCE(EXCLUDED.html_content, institutional_publications.html_content),
    published_date= COALESCE(EXCLUDED.published_date, institutional_publications.published_date),
    policy_areas  = EXCLUDED.policy_areas,
    tags          = EXCLUDED.tags,
    extra_metadata= EXCLUDED.extra_metadata,
    fetched_at    = now()
RETURNING (xmax = 0) AS inserted
"""


def _engine():
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("[ERROR] DATABASE_URL not set")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return create_engine(url, pool_pre_ping=True)


def policy_terms() -> list[str]:
    """The 35 canonical policy leaves — the maintained source of truth."""
    path = BACKEND_DIR / "knowledge_base" / "policy_taxonomy.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    terms: list[str] = []
    for cat in data.get("categories", []):
        for leaf in (cat.get("areas") or cat.get("policy_areas") or []):
            label = leaf.get("label") or leaf.get("name") or leaf.get("id")
            if label:
                terms.append(label)
    if not terms:
        raise RuntimeError(
            "policy_taxonomy.json yielded 0 terms -- refusing to run with an "
            "empty term list, which would silently ingest nothing and look fine"
        )
    return terms


def _persist(conn, doc: CouncilDoc, source: str, body: Optional[str] = None) -> bool:
    row = conn.execute(text(_UPSERT), {
        "source": source,
        "inst": INSTITUTION_SLUG,
        "category": doc.category,
        "ext_id": doc.external_id,
        "url": doc.url,
        "title": doc.title,
        "summary": (body[:900] if body else None),
        "published": doc.published,
        "policy_areas": doc.subject_matters or [],
        "tags": [doc.doc_type] if doc.doc_type else [],
        "body": body,
        "meta": json.dumps({
            "doc_type": doc.doc_type,
            "subject_matters": doc.subject_matters,
            "register_ref": doc.external_id,
        }),
    }).fetchone()
    return bool(row.inserted) if row else False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="Persist (default dry-run)")
    ap.add_argument("--terms", nargs="*",
                    help="Targeted subject/full-text terms (backfill a known gap)")
    ap.add_argument("--since", default="2025-01-01", help="Window start (YYYY-MM-DD)")
    ap.add_argument("--since-days", type=int,
                    help="Window start as N days back from today. Overrides --since; "
                         "an absolute date in a cron entry silently rots.")
    ap.add_argument("--until", help="Window end (YYYY-MM-DD, default today)")
    ap.add_argument("--press-only", action="store_true", help="Only the press-release feed")
    ap.add_argument("--no-window", action="store_true",
                    help="Skip date enumeration (terms only)")
    ap.add_argument("--window-days", type=int, default=30,
                    help="Split the range into windows of N days. Narrower windows "
                         "avoid the register's 1,000-document cap.")
    ap.add_argument("--limit-terms", type=int, help="Cap the number of terms (smoke runs)")
    ap.add_argument("--refs", nargs="*",
                    help="Ingest specific register references directly, e.g. "
                         "ST-15875-2025-INIT. Uses data.consilium (plain HTTP), so a "
                         "document you can name is always ingestable even when the "
                         "register search does not surface it.")
    ap.add_argument("--fetch-bodies", action="store_true",
                    help="Also download each register document's text. Needed for the "
                         "endpoint's body_txt contract AND for `q` to find documents "
                         "whose subject line does not contain the search term.")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    since = (date.today() - timedelta(days=args.since_days)) if args.since_days \
        else datetime.strptime(args.since, "%Y-%m-%d").date()
    collected: list[tuple[CouncilDoc, str]] = []
    failures: list[str] = []

    # Press releases first: broad, cheap, and the endpoint names them explicitly.
    try:
        for d in fetch_press_releases():
            collected.append((d, SOURCE_PRESS))
    except Exception as exc:  # noqa: BLE001
        # Recorded, never swallowed: a failed fetch must not read as "no press releases".
        failures.append(f"press_releases: {type(exc).__name__}: {exc}")
        logger.warning("[FAIL] press releases: %s", exc)

    truncated_windows: list[str] = []

    if not args.press_only:
        # BREADTH: enumerate the register by date window. This replaced a
        # term-driven slice. The first cut searched Brubru's 35 policy-area
        # LABELS, ingested 222 documents, and still returned nothing for
        # "minors" -- because policy DOMAINS are not the words that appear in a
        # document's subject line. Enumeration does not depend on guessing
        # vocabulary at all.
        if not args.no_window:
            until = (datetime.strptime(args.until, "%Y-%m-%d").date()
                     if args.until else date.today())
            cursor = since
            step = max(1, args.window_days)
            while cursor <= until:
                wend = min(until, cursor + timedelta(days=step - 1))
                try:
                    docs, truncated = search_by_date(cursor, wend)
                    for d in docs:
                        collected.append((d, SOURCE_REGISTER))
                    if truncated:
                        # NEVER a silent cap: name the window that was clipped so
                        # it can be re-run with a narrower --window-days.
                        truncated_windows.append(f"{cursor}..{wend}")
                except Exception as exc:  # noqa: BLE001
                    failures.append(f"{cursor}..{wend}: {type(exc).__name__}: {exc}")
                    logger.warning("[FAIL] window %s..%s %s", cursor, wend, exc)
                cursor = wend + timedelta(days=1)

        # BY REFERENCE: a named document, straight from the primary source.
        for ref in (args.refs or []):
            try:
                d = fetch_by_reference(ref)
                if d:
                    collected.append((d, SOURCE_REGISTER))
                else:
                    failures.append(f"ref:{ref}: unreadable")
            except Exception as exc:  # noqa: BLE001
                failures.append(f"ref:{ref}: {type(exc).__name__}: {exc}")
                logger.warning("[FAIL] ref %s %s", ref, exc)

        # TARGETED: close a known gap by subject AND full text.
        terms = args.terms or []
        if args.limit_terms:
            terms = terms[: args.limit_terms]
        for term in terms:
            for fn, kind in ((search_register, "subject"), (search_full_text, "text")):
                try:
                    for d in fn(term, date_from=since):
                        collected.append((d, SOURCE_REGISTER))
                except Exception as exc:  # noqa: BLE001
                    failures.append(f"{kind}:{term}: {type(exc).__name__}: {exc}")
                    logger.warning("[FAIL] %s:%-24s %s", kind, term, exc)

    # Deduplicate on the upsert key: the same document legitimately matches
    # several policy terms, and counting it once per term would overstate the run.
    unique: dict[tuple[str, str], tuple[CouncilDoc, str]] = {}
    for doc, source in collected:
        unique[(source, doc.external_id)] = (doc, source)

    logger.info("[INFO] %d fetched, %d unique document(s)", len(collected), len(unique))
    if failures:
        logger.warning("[WARN] %d source(s) FAILED and contributed nothing: %s",
                       len(failures), "; ".join(failures[:5]))
    if truncated_windows:
        logger.warning("[WARN] %d window(s) hit the register's 1,000-document cap and are "
                       "INCOMPLETE -- re-run them with a smaller --window-days: %s",
                       len(truncated_windows), ", ".join(truncated_windows[:6]))

    if not args.apply:
        for doc, source in list(unique.values())[:15]:
            logger.info("   [%s] %-24s %s  %s", source, doc.external_id,
                        doc.published, doc.title[:58])
        logger.info("[DRY-RUN] %d document(s) would be written. Re-run with --apply.",
                    len(unique))
        return 0

    inserted = updated = 0
    with _engine().connect() as conn:
        bodies_read = bodies_failed = 0
        for doc, source in unique.values():
            body = None
            if args.fetch_bodies and source == SOURCE_REGISTER:
                body = fetch_document_text(doc)
                if body:
                    bodies_read += 1
                else:
                    bodies_failed += 1
            try:
                if _persist(conn, doc, source, body):
                    inserted += 1
                else:
                    updated += 1
            except Exception as exc:  # noqa: BLE001
                failures.append(f"persist {doc.external_id}: {exc}")
                conn.rollback()
        conn.commit()
        # Count PERSISTED rows, not attempts -- `feedback_silent_failure_reports_success`.
        held = conn.execute(text(
            "SELECT count(*) FROM institutional_publications WHERE institution_slug = :i"),
            {"i": INSTITUTION_SLUG}).scalar()

    logger.info("[APPLIED] inserted=%d updated=%d | Council rows now held: %d",
                inserted, updated, held)
    if args.fetch_bodies:
        # Report both halves: a body count without its failures reads as complete.
        logger.info("[BODIES ] read=%d unreadable=%d", bodies_read, bodies_failed)
    if failures:
        logger.error("[ERROR] %d failure(s) during the run", len(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

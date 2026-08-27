#!/usr/bin/env python3.12
"""Backfill `texts_adopted.full_text` — the actual adopted text.

Why this is separate from the date backfill
-------------------------------------------
The D2 backfill recovered 452 adopted texts, and every one of them arrived with
`full_text = NULL`. The TOC page carries metadata only; the text itself lives on
each item's own detail page.

That gap was easy to miss, because `/api/v1/texts-adopted` returns a NON-NULL
`body_txt` regardless: when `full_text` is NULL it falls back to a body
synthesised from the structured row (title, procedure, committees, rapporteur,
dates). The fallback is deliberate and documented -- but it means a coverage
check on "is body_txt present" answers 50/50 while only 125 of 703 rows hold the
real text. A datapoint that is always present is not the same as a datapoint that
is always REAL.

So this script measures and reports the two separately, and only ever writes the
genuine article.

Fetching is bounded and resumable: `--limit` caps a run, rows already carrying a
body are skipped, and progress is committed per batch so a long run that dies
does not discard what it had.

Usage:
    python3.12 scripts/backfill_texts_adopted_bodies.py --stats
    python3.12 scripts/backfill_texts_adopted_bodies.py --limit 20        # dry-run
    python3.12 scripts/backfill_texts_adopted_bodies.py --limit 200 --apply
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR.parent / ".env")

# Below this, what came back is a nav shell or an error page, not an adopted text.
#
# Set to 400 at first, which REJECTED a genuine document: P10_TA(2025)0101 is
# 320 characters because the matter was referred back for interinstitutional
# negotiations, so there is no adopted text beyond the procedural note. A
# threshold tuned to catch junk was quietly discarding the shortest real
# documents, and "0 bodies for this row" read as a fetch problem.
MIN_BODY_CHARS = 250


def _engine():
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("[ERROR] DATABASE_URL not set")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return create_engine(url, pool_pre_ping=True)


def _stats(conn) -> dict:
    r = conn.execute(text("""
        SELECT count(*) AS total,
               count(full_text) AS with_body,
               count(*) FILTER (WHERE full_text IS NULL AND COALESCE(full_text_url,
                    CASE WHEN source_url LIKE '%.pdf' THEN source_url END) IS NOT NULL) AS fetchable,
               count(*) FILTER (WHERE full_text IS NULL AND full_text_url IS NULL
                    AND (source_url IS NULL OR source_url NOT LIKE '%.pdf')) AS no_url
        FROM texts_adopted
    """)).mappings().one()
    return dict(r)


async def _run(args) -> int:
    from services.scrapers.texts_adopted_scraper import TextsAdoptedScraper

    engine = _engine()
    with engine.connect() as conn:
        st = _stats(conn)
        print(f"[INFO] texts_adopted: {st['total']} rows | real full_text: {st['with_body']} "
              f"| fetchable (url, no body): {st['fetchable']} | no url at all: {st['no_url']}")
        # Say the synthesised-body caveat out loud every run, so nobody reads
        # "body_txt present" as "text held".
        print(f"[INFO] the endpoint returns a SYNTHESISED body for the "
              f"{st['total'] - st['with_body']} rows without full_text -- present, but not the text")
        if args.stats:
            return 0

        # `full_text_url` is NULL on 108 rows whose `source_url` points at the PDF
        # (..._EN.pdf). doceo serves the same document as HTML at the same path,
        # so the HTML URL is derivable and those rows are NOT unreachable -- they
        # only looked that way because one column was empty.
        rows = conn.execute(text(
            "SELECT id, ta_reference, "
            "       COALESCE(full_text_url, "
            "                CASE WHEN source_url LIKE '%.pdf' "
            "                     THEN left(source_url, length(source_url)-4) || '.html' "
            "                END) AS url "
            "FROM texts_adopted "
            "WHERE full_text IS NULL "
            "  AND COALESCE(full_text_url, "
            "               CASE WHEN source_url LIKE '%.pdf' THEN source_url END) IS NOT NULL "
            "ORDER BY adoption_date DESC NULLS LAST"
            + (" LIMIT :lim" if args.limit else "")),
            ({"lim": args.limit} if args.limit else {})).fetchall()

    print(f"[INFO] {len(rows)} row(s) to fetch")
    if not rows:
        print("[OK] nothing to do")
        return 0

    scraper = TextsAdoptedScraper()
    ok = too_short = failed = 0

    # A long browser walk holds this connection across minutes of network work.
    # `pool_pre_ping` fires on CHECKOUT, so it cannot protect a connection already
    # held -- Supabase drops it and the next UPDATE dies with
    # "SSL SYSCALL error: No route to host". That is exactly what killed this run
    # at row 588 of 703. Catch it, rebuild, continue, and COUNT the reconnects so
    # a flaky link is visible rather than silently halving the run.
    # (feedback_long_session_needs_reconnect)
    engine2 = _engine()
    conn = engine2.connect()
    reconnects = 0

    def _write(row_id, body):
        nonlocal conn, reconnects
        from sqlalchemy.exc import OperationalError
        for attempt in (1, 2):
            try:
                conn.execute(text(
                    "UPDATE texts_adopted SET full_text = :b, last_updated = now() "
                    "WHERE id = :i"), {"b": body, "i": row_id})
                return True
            except OperationalError:
                if attempt == 2:
                    raise
                reconnects += 1
                try:
                    conn.close()
                except Exception:  # noqa: BLE001
                    pass
                conn = _engine().connect()
                print(f"  [RECONNECT] #{reconnects} -- database connection rebuilt")
        return False

    try:
        for i, r in enumerate(rows, 1):
            try:
                detail = await scraper.scrape_text_detail(r.ta_reference, r.url)
                body = (getattr(detail, "full_text", None) or "") if detail else ""
            except Exception as exc:  # noqa: BLE001
                # A fetch failure is not an empty document. Counted separately.
                print(f"  [FAIL] {r.ta_reference}: {type(exc).__name__}: {str(exc)[:70]}")
                failed += 1
                continue

            if len(body.strip()) < MIN_BODY_CHARS:
                too_short += 1
                continue

            ok += 1
            if args.apply:
                _write(r.id, body)
                # Commit per batch: a long browser walk that dies at row 300 must
                # not discard the first 299.
                if ok % 25 == 0:
                    try:
                        conn.commit()
                    except Exception:  # noqa: BLE001
                        conn = _engine().connect()
                        reconnects += 1
                    print(f"  [{i}/{len(rows)}] committed, {ok} bodies so far")
        if args.apply:
            try:
                conn.commit()
            except Exception:  # noqa: BLE001
                pass
    finally:
        conn.close()

    print(f"[{'APPLIED' if args.apply else 'DRY-RUN'}] bodies={ok} "
          f"too_short_or_empty={too_short} fetch_failed={failed} reconnects={reconnects}")

    if args.apply:
        with _engine().connect() as conn:
            st2 = _stats(conn)
            print(f"[VERIFY] real full_text: {st['with_body']} -> {st2['with_body']} "
                  f"of {st2['total']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="Persist (default dry-run)")
    ap.add_argument("--limit", type=int, help="Cap rows per run (resumable)")
    ap.add_argument("--stats", action="store_true", help="Report coverage and exit")
    args = ap.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())

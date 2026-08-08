"""
Fill legislative_carriages.short_title with a human-readable name per file.

The briefing cards and the file modal need a name they can put on one line.
The official title cannot be that name: it runs 150-400 characters and hides
the subject at the end. This script resolves one, in the order the product
trusts them:

  1. A curated alias (procedure_aliases.json by OEIL reference, the
     legislation acronym KB by CELEX). Free, instant, never wrong.
  2. Otherwise an AI-synthesised subject line, checked for faithfulness
     against the source title before it is accepted.

Rows where neither works are left NULL, which the UI reads as "use the parsed
instrument designation". NULL is a normal outcome, not a failure.

Runs offline so a dashboard load never waits on a model.

    # See what would change, touch nothing:
    python3.12 scripts/backfill_carriage_short_titles.py --dry-run --limit 20

    # Fill the files most likely to surface first:
    python3.12 scripts/backfill_carriage_short_titles.py --limit 200

    # Re-do rows that already have a name:
    python3.12 scripts/backfill_carriage_short_titles.py --force --limit 50

Idempotent: without --force it only touches rows where short_title IS NULL.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from services.legislative.title_display import curated_alias, split_celex_prefix  # noqa: E402
from services.legislative.title_synthesiser import synthesise_short_title  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("backfill_short_titles")


async def _resolve(title: str, ref: str | None) -> tuple[str | None, str]:
    """Return (short_title, source) for one file. source is for the log."""
    clean_title, celex = split_celex_prefix(title or "")

    alias = curated_alias(ref, celex, "en")
    if alias:
        return alias, "curated"

    synthesised = await synthesise_short_title(clean_title)
    if synthesised:
        return synthesised, "ai"

    return None, "none"


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100,
                        help="how many rows to process (default 100)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would change, write nothing")
    parser.add_argument("--force", action="store_true",
                        help="also re-resolve rows that already have a name")
    parser.add_argument("--sleep", type=float, default=1.5,
                        help="seconds to wait between AI calls (default 1.5). "
                             "The head of the provider chain rate-limits, and "
                             "its SDK answers a 429 by sleeping ~60s rather "
                             "than falling through, so pacing beats retrying.")
    parser.add_argument("--match", type=str, default=None,
                        help="only rows whose title contains this string")
    args = parser.parse_args()

    clauses = [] if args.force else ["short_title IS NULL"]
    params = {"lim": args.limit}
    if args.match:
        clauses.append("title ILIKE :match")
        params["match"] = f"%{args.match}%"
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                f"""
                SELECT id, title, oeil_procedure_ref
                FROM legislative_carriages
                {where}
                ORDER BY first_seen DESC NULLS LAST
                LIMIT :lim
                """
            ),
            params,
        ).mappings().all()

        if not rows:
            logger.info("[INFO] nothing to do")
            return 0

        counts = {"curated": 0, "ai": 0, "none": 0}
        for row in rows:
            short, source = await _resolve(row["title"], row["oeil_procedure_ref"])
            counts[source] += 1

            marker = {"curated": "[KB]", "ai": "[AI]", "none": "[--]"}[source]
            logger.info("%s %-58s  <- %s", marker, (short or "")[:58],
                        (row["title"] or "")[:70])

            if short and not args.dry_run:
                db.execute(
                    text(
                        "UPDATE legislative_carriages "
                        "SET short_title = :s WHERE id = :i"
                    ),
                    {"s": short, "i": row["id"]},
                )
                # Commit per row. A long run WILL be interrupted — rate limits,
                # a stopped terminal — and batching the commit to the end threw
                # away every name resolved up to that point.
                db.commit()

            # Pace the AI calls. Curated hits cost nothing, so only wait when
            # a model was actually asked.
            if source == "ai" and args.sleep > 0:
                await asyncio.sleep(args.sleep)

        if args.dry_run:
            db.rollback()
            logger.info("\n[INFO] dry run, nothing written")
        else:
            logger.info("\n[OK] committed as it went")

        logger.info(
            "[INFO] %d rows: %d curated, %d synthesised, %d left for the "
            "instrument fallback",
            len(rows), counts["curated"], counts["ai"], counts["none"],
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

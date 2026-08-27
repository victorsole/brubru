#!/usr/bin/env python3.12
"""D4: recover committee roles, rapporteur and forecasts from stored OEIL pages.

The defect
----------
`oeil_sync_service` sets `lead_committee = item.committees[0]` -- whichever
committee happens to come first in a flat list from the OEIL XML feed, which does
not distinguish the committee RESPONSIBLE from a committee FOR OPINION. For
2025/2081(INI) that recorded IMCO as the lead when OEIL says CULT, with IMCO
holding an opinion alongside LIBE and FEMM, and left the rapporteur NULL.

Measured across all 2,789 carriages before this ran:

    rapporteur_mep_id populated ......      0
    lead_committee populated .........  1,038
    opinion_committees non-empty .....      1
    committees non-empty .............      1

So two columns had never been written and a third came from a list whose order
carries no meaning. This is not one bad row.

Why it is a backfill and not a re-scrape
----------------------------------------
Brubru already stores the OEIL procedure page in `oeil_text_body` for 892
carriages, and that page states the roles explicitly. Re-fetching OEIL 2,789
times to recover something already on disk would be slow and rude to the source.
Carriages without a stored page are counted and reported, never silently skipped.

Usage:
    python3.12 scripts/backfill_oeil_committee_roles.py            # dry-run
    python3.12 scripts/backfill_oeil_committee_roles.py --apply
    python3.12 scripts/backfill_oeil_committee_roles.py --ref 2025/2081(INI)
"""
import argparse
import json
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

from services.scrapers.oeil_procedure_parser import parse_procedure_text  # noqa: E402

_UPDATE = """
UPDATE legislative_carriages SET
    lead_committee       = COALESCE(:responsible, lead_committee),
    opinion_committees   = :opinions,
    committees           = :all_committees,
    rapporteur_name      = COALESCE(:rapporteur, rapporteur_name),
    rapporteur_appointed = COALESCE(CAST(:appointed AS date), rapporteur_appointed),
    oeil_forecasts       = CAST(:forecasts AS json),
    oeil_roles_parsed_at = now()
WHERE id = :id
"""


def _engine():
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("[ERROR] DATABASE_URL not set")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return create_engine(url, pool_pre_ping=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="Persist (default dry-run)")
    ap.add_argument("--ref", help="Only this oeil_procedure_ref")
    ap.add_argument("--limit", type=int, help="Cap rows processed")
    args = ap.parse_args()

    where = "oeil_text_body IS NOT NULL"
    params: dict = {}
    if args.ref:
        where += " AND oeil_procedure_ref = :ref"
        params["ref"] = args.ref

    with _engine().connect() as conn:
        total_carriages = conn.execute(
            text("SELECT count(*) FROM legislative_carriages")).scalar()
        rows = conn.execute(text(
            f"SELECT id, oeil_procedure_ref, lead_committee, oeil_text_body "
            f"FROM legislative_carriages WHERE {where} ORDER BY oeil_procedure_ref"
            + (" LIMIT :lim" if args.limit else "")),
            {**params, **({"lim": args.limit} if args.limit else {})}
        ).fetchall()

        print(f"[INFO] {len(rows)} carriage(s) with a stored OEIL page, "
              f"of {total_carriages} total")
        # Say what is NOT covered. A backfill that reports only what it touched
        # reads as complete.
        if not args.ref:
            print(f"[INFO] {total_carriages - len(rows)} carriage(s) have no stored "
                  f"page and are UNTOUCHED -- they keep oeil_roles_parsed_at NULL, "
                  f"which means 'never parsed', not 'no opinion committees'")

        changed = corrected = 0
        # "unparseable" was one bucket hiding three different facts. Audited:
        # of 104, 96 pages carry no "Committee responsible" heading at all and
        # 8 say "Pending final decision on the referral" -- the committee is not
        # assigned yet. Zero were parser failures. Keeping them apart means a
        # real parser regression cannot hide inside an expected count.
        no_heading = pending_referral = parse_failed = 0
        samples = []
        for r in rows:
            facts = parse_procedure_text(r.oeil_text_body)
            if not facts.responsible_committee and not facts.opinion_committees \
               and not facts.rapporteur_name:
                body = r.oeil_text_body or ""
                if "Committee responsible" not in body:
                    no_heading += 1
                elif "Pending final decision on the referral" in body:
                    pending_referral += 1
                else:
                    parse_failed += 1
                # Stamp it anyway. `oeil_roles_parsed_at` is the third state that
                # separates "never looked at this page" from "looked, and the page
                # genuinely carries no roles". Leaving it NULL here made the
                # completeness check report 104 unparsed carriages that had in
                # fact all been read -- a monitor crying about its own blind spot.
                if args.apply:
                    conn.execute(text(
                        "UPDATE legislative_carriages SET oeil_roles_parsed_at = now() "
                        "WHERE id = :id"), {"id": r.id})
                continue
            was_wrong = (
                facts.responsible_committee
                and r.lead_committee
                and facts.responsible_committee != r.lead_committee
            )
            if was_wrong:
                corrected += 1
                if len(samples) < 12:
                    samples.append(
                        f"{r.oeil_procedure_ref:22} {r.lead_committee} -> "
                        f"{facts.responsible_committee}  (opinions: "
                        f"{','.join(facts.opinion_committees) or '-'})")
            changed += 1

            if args.apply:
                conn.execute(text(_UPDATE), {
                    "id": r.id,
                    "responsible": facts.responsible_committee,
                    "opinions": facts.opinion_committees,
                    "all_committees": facts.all_committees,
                    "rapporteur": facts.rapporteur_name,
                    "appointed": facts.rapporteur_appointed,
                    "forecasts": json.dumps(facts.forecasts),
                })

        if args.apply:
            conn.commit()

        print(f"[{'APPLIED' if args.apply else 'DRY-RUN'}] parsed={changed} "
              f"lead_committee_corrected={corrected}")
        print(f"[INFO] not parsed: no_committee_section={no_heading} "
              f"referral_still_pending={pending_referral} parse_failed={parse_failed}")
        if parse_failed:
            # The only one of the three that is a defect.
            print(f"[WARN] {parse_failed} page(s) HAVE a committee section the "
                  f"parser could not read -- that is a parser gap, not a data gap")
        if samples:
            print("[INFO] committees that were WRONG (stored -> OEIL):")
            for s in samples:
                print("   " + s)

        if args.apply:
            # Verify from the table, not from the loop counter.
            got = conn.execute(text(
                "SELECT count(*) FILTER (WHERE rapporteur_name IS NOT NULL), "
                "       count(*) FILTER (WHERE oeil_roles_parsed_at IS NOT NULL), "
                "       count(*) FILTER (WHERE array_length(opinion_committees,1) > 0) "
                "FROM legislative_carriages")).fetchone()
            print(f"[VERIFY] rapporteur_name={got[0]}  roles_parsed={got[1]}  "
                  f"with_opinion_committees={got[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

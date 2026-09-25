"""
Update Legislative Carriage Statuses Based on OEIL Key Events

This script fetches each carriage's live OEIL procedure page and writes what the
page states: key events, forecasts, rapporteur, committee responsible, opinion
committees, the cleaned page body, and the status those events prove.

Status inference rules (strongest signal wins; status only ever ADVANCES):
  - "Final act signed" / "Final act published" / "Entry into force" -> ADOPTED
  - "Act adopted by Council", or OEIL stage "Procedure completed" -> COMPLETED
  - "Decision by Parliament", "Vote in committee", "Committee report",
    "Committee recommendation tabled", "Approval in committee of the text
    agreed" -> CLOSE_TO_ADOPTION
  - "Legislative proposal" or "Committee referral" -> TABLED

Every page that cannot be fetched or parses to nothing is an ERROR (counted,
listed, exit code 1), never a skip. Until 15 Sep 2026 the parser returned one
guessed event per page, forecasts never, opinion committees never, and the
script persisted only key events + status, so a run "changed nothing" while
OEIL had moved on.
"""

import argparse
import time
import asyncio
from sqlalchemy import text
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / '.env')

from sqlalchemy.exc import OperationalError, DBAPIError
from sqlalchemy.orm.attributes import flag_modified
from core.database import SessionLocal
from models.legislative_train import LegislativeCarriage, CarriageStatusEnum
from services.scrapers.oeil_scraper import OEILScraper, OEILFetchError
from services.scrapers.oeil_body_scraper import parse_body
from services.scrapers.oeil_procedure_parser import (
    STATUS_RANK as _PARSER_STATUS_RANK, advance_status, carriage_fields_from_procedure,
    infer_carriage_status,
)


_ap = argparse.ArgumentParser(description="Update carriage statuses from OEIL key events")
# action="append", never nargs="+": a repeated flag with nargs silently
# overwrites earlier values, which this repo has hit three times.
_ap.add_argument("--refs", action="append", default=None,
                 help="Procedure ref to refresh, e.g. --refs '2026/0074(COD)'. Repeatable. "
                      "Omit to sweep every non-adopted carriage.")
_ap.add_argument("--limit", type=int, default=None, help="Cap the number of carriages checked.")
_ap.add_argument("--stalest-first", action="store_true",
                 help="Check the carriages whose OEIL page is oldest (never fetched first). "
                      "The scheduled run uses this so a --limit never starves the same rows.")
_ap.add_argument("--budget", type=int, default=0,
                 help="Stop starting new carriages after this many seconds (0 = none).")
_args, _ = _ap.parse_known_args()
REFS = _args.refs
LIMIT = _args.limit
STALEST_FIRST = _args.stalest_first
BUDGET = _args.budget


_OWNED_BY_ROLES = frozenset({"lead_committee", "opinion_committees", "committees",
                             "rapporteur_name", "rapporteur_appointed"})


def log(msg):
    """Print and flush immediately."""
    print(msg, flush=True)


# Status rules and the progression live in services/scrapers/oeil_procedure_parser.py
# (infer_carriage_status / advance_status) so this script and the OEIL feed sync
# cannot drift apart. See that docstring for why "Decision by Parliament" no
# longer means COMPLETED (15 Sep 2026).
STATUS_RANK = {CarriageStatusEnum(k): v for k, v in _PARSER_STATUS_RANK.items()}


def infer_status_from_events(events, stage=None) -> CarriageStatusEnum | None:
    """Infer the most advanced status from OEIL key events (+ OEIL stage)."""
    value = infer_carriage_status([e.event_type for e in events], stage)
    return CarriageStatusEnum(value) if value else None


async def update_statuses():
    """Update carriage statuses based on OEIL key events."""

    db = SessionLocal()
    # Browser fallback on: a walled/empty OEIL answer is retried in one reused
    # headless browser (closed in the finally below).
    scraper = OEILScraper(allow_browser_fallback=True)

    try:
        log("=" * 60)
        log("Update Carriage Statuses from OEIL Key Events")
        log("=" * 60)

        # Get all carriages with OEIL procedure refs that are not already ADOPTED
        q = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.oeil_procedure_ref != None,
            LegislativeCarriage.oeil_procedure_ref != '',
            LegislativeCarriage.current_status != CarriageStatusEnum.ADOPTED,
            LegislativeCarriage.current_status != CarriageStatusEnum.WITHDRAWN
        )

        # --refs narrows the sweep to named procedures (11 September 2026).
        #
        # Without it this is all-or-nothing: 1,903 carriages at 0.5s of pacing
        # plus a fetch each, which is hours of sustained requests to an EU server.
        # The routine need is far smaller -- after a committee week, refresh the
        # dozen or so files that actually reached a vote -- and firing the whole
        # sweep for fourteen of them is not proportionate to what changed.
        if REFS:
            q = q.filter(LegislativeCarriage.oeil_procedure_ref.in_(REFS))
        # Only the columns the loop needs: loading every full row (page bodies
        # included) for a 1,900-row sweep was tens of MB for three fields.
        carriages = q.with_entities(
            LegislativeCarriage.id, LegislativeCarriage.oeil_procedure_ref, LegislativeCarriage.title,
        ).order_by(
            # Scheduled on the warm tier since 24 Sep 2026. Ordered by reference,
            # a --limit run re-checked the same rows forever: 398 of the live
            # files had an OEIL page older than 7 days and 19 had never been
            # fetched, so new rapporteurs and draft reports waited for someone
            # to run /carriages by hand.
            *((LegislativeCarriage.oeil_body_fetched_at.asc().nullsfirst(),) if STALEST_FIRST and not REFS else ()),
            LegislativeCarriage.oeil_procedure_ref,
        ).all()
        if LIMIT:
            carriages = carriages[:LIMIT]

        if REFS:
            found = {c.oeil_procedure_ref for c in carriages}
            missing = [r for r in REFS if r not in found]
            log(f"\n1. --refs: {len(REFS)} requested, {len(carriages)} matched")
            # Say which refs matched nothing. Silently checking 12 of 14 and
            # reporting success is the shape of defect this repo keeps finding.
            if missing:
                log(f"   NOT FOUND as carriages (no row, or already ADOPTED/WITHDRAWN): {', '.join(missing)}")
        else:
            log(f"\n1. Found {len(carriages)} carriages to check")

        updated_count = 0
        updated_key_events = 0
        errors = 0
        reconnects = 0
        rows_changed = 0
        status_changes = []
        failed_refs = []
        not_on_oeil = []
        no_events = []
        started = time.monotonic()

        # Plain tuples, then re-load each row by id AFTER its fetch: ORM objects
        # from a session that was replaced on reconnect are detached, and writes
        # to them were silently never persisted. Loading after the fetch also
        # keeps the pooled connection idle during the network wait.
        targets = [(c.id, c.oeil_procedure_ref, c.title or "") for c in carriages]
        db.commit()

        for i, (carriage_id, procedure_ref, title) in enumerate(targets):
            if BUDGET and time.monotonic() - started > BUDGET:
                log(f"\n[INFO] budget spent; {len(targets) - i} carriage(s) left for the next run")
                break
            log(f"\n[{i+1}/{len(targets)}] {procedure_ref}: {title[:50]}...")

            try:
                try:
                    data, page = await scraper.get_procedure_with_page(procedure_ref)
                except OEILFetchError as fe:
                    if fe.status == 404:
                        # Third state, not an error: OEIL answers 404 "does not
                        # exist or is in the process of being initiated" for a
                        # proposal the Commission adopted days ago (COM(2026) 498,
                        # 2026/0289(COD), on 24 Sep). Stamp the row so it goes to
                        # the back of a --stalest-first queue and is retried next
                        # cycle; report it by name.
                        not_on_oeil.append(procedure_ref)
                        row = db.get(LegislativeCarriage, carriage_id)
                        if row is not None:
                            row.oeil_body_fetched_at = datetime.now(timezone.utc).replace(tzinfo=None)
                            db.commit()
                        log("   -> [INFO] not on OEIL yet (404); retried next cycle")
                        await asyncio.sleep(0.5)
                        continue
                    errors += 1
                    failed_refs.append(f"{procedure_ref}: {fe.reason}")
                    log(f"   -> [ERROR] FETCH/PARSE FAILED: {fe}")
                    await asyncio.sleep(0.5)
                    continue

                fields = carriage_fields_from_procedure(data)
                if not fields.get("oeil_key_events"):
                    # A named state, not an error (24 Sep 2026). OEIL renders no
                    # "Key events" section at all for some files: immunity cases
                    # awaiting a committee decision, some completed RSP
                    # resolutions (checked on the live pages). Counting them as
                    # errors turned the scheduled run red every time, and
                    # skipping the write left them unstamped, so a stalest-first
                    # queue re-picked them forever. The rest of the page is still
                    # written; existing events are never wiped; OEIL's own stage
                    # line still drives the status. A parser regression stays
                    # visible through the majority guard after the loop.
                    no_events.append(procedure_ref)
                    fields.pop("oeil_key_events", None)
                    log("   -> [INFO] OEIL page carries no key events (kept existing events)")

                carriage = db.get(LegislativeCarriage, carriage_id)
                if carriage is None:
                    errors += 1
                    failed_refs.append(f"{procedure_ref}: row vanished during the run")
                    continue
                changed = []
                for col, val in fields.items():
                    # One owner per field (24 Sep 2026). Committees and the
                    # rapporteur are owned by oeil_roles (backfill_oeil_committee_
                    # roles.py), which runs right after this job on the warm tier
                    # and parses the page this job has just stored. Written here
                    # too, the two disagreed on joint files (this parse kept
                    # {INTA, ENVI} for the Industrial Accelerator Act where the
                    # roles parser holds {INTA, ITRE, IMCO, ENVI, BUDG}) and
                    # flipped the row on every run.
                    if col in _OWNED_BY_ROLES:
                        continue
                    if col in ("rapporteur_name", "rapporteur_mep_id", "rapporteur_appointed") and val is None:
                        continue   # never blank a known rapporteur from a page that omits one
                    if getattr(carriage, col) != val:
                        setattr(carriage, col, val)
                        changed.append(col)

                body = parse_body(page.html)
                now = datetime.now(timezone.utc)
                if body is not None:
                    if carriage.oeil_text_body != body.text_body:
                        carriage.oeil_html_body = body.html_body
                        carriage.oeil_text_body = body.text_body
                        changed.append("oeil_body")
                    carriage.oeil_body_fetched_at = now.replace(tzinfo=None)
                carriage.oeil_roles_parsed_at = now

                # Infer status from events (+ OEIL's own stage line)
                inferred_value = infer_carriage_status(
                    [e.event_type for e in data.key_events.events], data.basic_info.status)
                current_value = carriage.current_status.value if carriage.current_status else None
                new_value = advance_status(current_value, inferred_value)
                if new_value:
                    carriage.current_status = CarriageStatusEnum(new_value)
                    log(f"   -> Status advancing: {current_value} -> {new_value}")
                    changed.append("current_status")
                elif inferred_value:
                    log(f"   -> Status stays {current_value} (events prove: {inferred_value})")
                else:
                    log("   -> No status signal from events")

                if not changed:
                    # The stamps above would otherwise fire last_updated's
                    # onupdate and make an unchanged row look freshly updated.
                    flag_modified(carriage, "last_updated")
                log(f"   -> via {page.route}: {len(fields.get('oeil_key_events') or [])} events, "
                    f"{len(fields['oeil_forecasts'])} forecasts, rapporteur={fields.get('rapporteur_name')}, "
                    f"opinions={fields.get('opinion_committees')}; changed={changed or 'nothing'}")

                # Commit after each successful update to avoid losing progress
                db.commit()
                # Count only what is now PERSISTED.
                if changed:
                    rows_changed += 1
                if "oeil_key_events" in changed:
                    updated_key_events += 1
                if new_value:
                    updated_count += 1
                    status_changes.append(f"{procedure_ref}: {current_value} -> {new_value}")

                # Rate limiting
                await asyncio.sleep(0.5)

            except Exception as e:
                # A dropped Supabase connection must not end the run. This loop
                # holds a session across ~2 seconds of OEIL fetch per carriage
                # and runs for half an hour; on 24 Aug 2026 the server closed the
                # connection at carriage 545 of 1,377 and the script stopped
                # there -- while still exiting 0, so it reported success having
                # done 40% of the work. `pool_pre_ping` does not save you here:
                # it fires on CHECKOUT, and a session that already holds a
                # connection never checks out again.
                msg = str(e)
                if isinstance(e, (OperationalError, DBAPIError)) or "server closed the connection" in msg:
                    log(f"   -> CONNECTION LOST: {msg[:70]} -- reconnecting")
                    try:
                        db.close()
                    except Exception:
                        pass
                    db = SessionLocal()
                    reconnects += 1
                    errors += 1
                    continue
                log(f"   -> ERROR: {msg[:80]}")
                errors += 1
                try:
                    db.rollback()
                except Exception:
                    db.close(); db = SessionLocal(); reconnects += 1

        log("\n" + "=" * 60)
        log("Summary:")
        log(f"  Total checked: {len(targets)}")
        log(f"  Reconnects after a dropped connection: {reconnects}")
        log(f"  Rows with any field changed: {rows_changed}")
        log(f"  Key events updated: {updated_key_events}")
        log(f"  Status changes: {updated_count}")
        log(f"  Errors: {errors}")
        checked = len(targets) - len(not_on_oeil)
        if checked >= 10 and len(no_events) > checked / 2:
            # Most pages with no events is a parser or page-layout regression,
            # not a batch of quiet files.
            errors += 1
            failed_refs.append(f"{len(no_events)} of {checked} pages parsed to no key events: parser regression?")
        log(f"  Pages with no key events on OEIL (not an error): {len(no_events)}"
            + (f" -> {', '.join(no_events[:12])}" if no_events else ""))
        log(f"  Not on OEIL yet (404, not an error): {len(not_on_oeil)}"
            + (f" -> {', '.join(not_on_oeil)}" if not_on_oeil else ""))
        log(f"  Fetch routes: {dict(scraper.fetch_stats)}")
        if failed_refs:
            log("\nFailed refs (fetch/parse):")
            for fr in failed_refs:
                log(f"  [ERROR] {fr}")

        if status_changes:
            log("\nAll status changes:")
            for change in status_changes:
                log(f"  {change}")

        # Final stats
        log("\n" + "=" * 60)
        log("Current status distribution:")
        for status in CarriageStatusEnum:
            count = db.query(LegislativeCarriage).filter(
                LegislativeCarriage.current_status == status
            ).count()
            log(f"  {status.value}: {count}")

        log("=" * 60)

        # Freshness of the whole Train, not just this run (25 Sep 2026). The job
        # read 80 files a run, twice a day, over 1,663 live files: a 10-day cycle,
        # so 1,123 files had an OEIL page older than 7 days while every run
        # reported success. Say so in the ledger when the Train falls behind.
        if not REFS:
            stale = db.execute(text(
                "SELECT count(*) FROM legislative_carriages "
                "WHERE oeil_procedure_ref IS NOT NULL AND oeil_procedure_ref <> '' "
                "AND current_status NOT IN ('ADOPTED', 'WITHDRAWN') "
                "AND (oeil_body_fetched_at IS NULL OR oeil_body_fetched_at < now() - interval '7 days')"
            )).scalar() or 0
            log(f"  Live files with an OEIL page older than 7 days: {stale}")
            if stale and not errors:
                print(f"[SYNC_STATUS] degraded: {stale} live Legislative Train file(s) have an "
                      f"OEIL page older than 7 days", flush=True)

        return 1 if errors else 0

    finally:
        await scraper.close()
        try:
            db.close()
        except Exception:
            pass


if __name__ == "__main__":
    # Exit non-zero when anything failed. Exiting 0 on a half-finished run is how
    # a 40%-complete sweep reported success on 24 Aug 2026.
    _rc = asyncio.run(update_statuses())
    sys.exit(_rc or 0)

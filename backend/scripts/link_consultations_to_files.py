"""Link Commission consultations to legislative files, and bring in who answered them.

Why (25 Sep 2026): the Stakeholder Map showed only organisations that met MEPs.
Organisations that answered the Commission's Have Your Say consultation on a file
were invisible, because nothing linked a consultation to the file it produced:
`public_consultations.com_references` was empty on all 4,124 rows, and responses
were stored for 27 consultations only. EU Inc. (2,518 responses, 41 from trade
unions) was fixed by hand first; this job does it for every file.

Each run, inside a time budget:
  1. REFS: for consultations that have reached the proposal stage and name no
     Commission document yet, read the portal's initiative record and store the
     COM/JOIN references its publications state (verbatim, never derived);
  2. RESPONSES: for every live legislative file, find the consultations whose
     references match the file's proposal (canon_commission_ref, at query time)
     and that have no stored responses, and sync their organisational responses.

Verdict: exit 1 when the portal answers nothing at all; `[SYNC_STATUS] degraded`
while either backlog remains; 0 when both are clear.

    python3.12 -m scripts.link_consultations_to_files              # scheduled form
    python3.12 -m scripts.link_consultations_to_files --max-seconds 1500
"""
import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from services.linking.emeeting_links import canon_commission_ref  # noqa: E402
from services.scrapers.hys_feedback_scraper import fetch_initiative  # noqa: E402
from scripts.sync_consultation_feedback import record_com_references, run as sync_feedback  # noqa: E402

LIVE_TYPES = r"\((COD|CNS|APP|NLE)\)"


def _refs_backlog(db) -> list:
    return [r[0] for r in db.execute(text("""
        SELECT initiative_id FROM public_consultations
         WHERE source = 'commission' AND initiative_id IS NOT NULL
           AND coalesce(cardinality(com_references), 0) = 0
           AND description ILIKE '%Stage: ADOPTION_WORKFLOW%'
         ORDER BY start_date DESC NULLS LAST""")).fetchall()]


def _unsynced_linked_initiatives(db) -> list:
    """Consultations linked to a live file by its proposal, with no stored responses."""
    files = db.execute(text(f"""
        SELECT c.oeil_procedure_ref, c.celex_numbers,
               array_remove(array_agg(DISTINCT d.reference), NULL) AS com_docs
          FROM legislative_carriages c
          LEFT JOIN ep_emeeting_documents d
                 ON d.procedure_ref = c.oeil_procedure_ref AND d.doc_kind = 'commission_document'
         WHERE c.current_status NOT IN ('ADOPTED', 'WITHDRAWN')
           AND c.oeil_procedure_ref ~ '{LIVE_TYPES}'
         GROUP BY 1, 2""")).fetchall()
    file_keys = {}
    for f in files:
        for ref in list(f.celex_numbers or []) + list(f.com_docs or []):
            k = canon_commission_ref(ref)
            if k:
                file_keys.setdefault(k, set()).add(f.oeil_procedure_ref)
    cons = db.execute(text("""
        SELECT p.initiative_id, p.com_references,
               EXISTS (SELECT 1 FROM consultation_feedback f WHERE f.initiative_id = p.initiative_id) AS has_fb
          FROM public_consultations p
         WHERE cardinality(p.com_references) > 0""")).fetchall()
    linked, unsynced = {}, []
    for c in cons:
        procs = set()
        for r in c.com_references:
            procs |= file_keys.get(canon_commission_ref(r), set())
        if procs:
            linked[c.initiative_id] = procs
            if not c.has_fb:
                unsynced.append(c.initiative_id)
    return linked, unsynced


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-seconds", type=int, default=780)
    ap.add_argument("--max-feedback", type=int, default=3000,
                    help="Responses read per consultation publication")
    args = ap.parse_args()
    started = time.monotonic()
    deadline = started + args.max_seconds
    refs_deadline = started + 0.6 * args.max_seconds    # keep 40% for responses

    db = SessionLocal()
    refs_queue = _refs_backlog(db)
    db.close()
    fetched = recorded = failed = 0
    for iid in refs_queue:
        if time.monotonic() > refs_deadline:
            break
        init = fetch_initiative(str(iid))
        fetched += 1
        if init is None:
            failed += 1
            continue
        recorded += 1 if record_com_references(str(iid), init) else 0
        time.sleep(0.3)
    refs_left = len(refs_queue) - fetched
    print(f"[link] refs: checked {fetched} of {len(refs_queue)} proposal-stage consultations, "
          f"{recorded} name their Commission document, {failed} fetch failures, {refs_left} left")
    if fetched and failed == fetched:
        print("[ERROR] the Have Your Say portal answered none of the initiative requests")
        return 1

    db = SessionLocal()
    linked, unsynced = _unsynced_linked_initiatives(db)
    db.close()
    files = set().union(*linked.values()) if linked else set()
    print(f"[link] {len(linked)} consultations linked to {len(files)} live files; "
          f"{len(unsynced)} have no stored responses")
    synced = 0
    # One large consultation takes minutes (EU Inc.: ~1,300 responses), so only
    # start one with real time left, or the scheduled timeout kills an unrecorded run.
    reserve = min(180, 0.4 * args.max_seconds)
    for iid in unsynced:
        if time.monotonic() > deadline - reserve and synced:
            break
        asyncio.run(sync_feedback(1, args.max_feedback, 0, False, [iid]))
        synced += 1
    responses_left = len(unsynced) - synced
    print(f"[link] responses synced for {synced} consultation(s); {responses_left} left "
          f"({time.monotonic() - started:.0f}s)")

    if refs_left or responses_left or failed:
        print(f"[SYNC_STATUS] degraded: {refs_left} consultation(s) still to read for their "
              f"Commission document, {responses_left} linked consultation(s) still without "
              f"responses, {failed} fetch failure(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

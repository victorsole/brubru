"""Sync every Commission initiative from Have Your Say into public_consultations.

Have Your Say carries ~4,100 initiatives. Brubru held 362 of them, so a user tracking
a file could ask "is there a consultation on this?" and be told no when there was one.
The gap was found on 11 August 2026 looking for initiative 16116, the ESPR delegated
act on ecodesign requirements for apparel textiles: the single most relevant pipeline
item for a textile client, absent from a table holding 1,059 rows.

Source: the portal's own JSON API, /brpapi/searchInitiatives, paged. It returns the
id, reference, short title, foreseen act type, topics (which carry the lead DG code
and the policy area label) and currentStatuses (stage, feedback status and dates).

Mapping notes, all grounded in a survey of the live vocabulary rather than guessed:

  receivingFeedbackStatus  OPEN -> open, UPCOMING -> upcoming, CLOSED -> closed.
    DISABLED means the stage has no feedback period at all; such an initiative is
    reported as `upcoming` while it is still only planned (INIT_PLANNED) and `closed`
    once it has moved past that. The raw upstream stage and status are written into
    `description` so nothing is lost in the flattening.

  frontEndStage  OPC_LAUNCHED -> public_consultation, PLANNING_WORKFLOW ->
    call_for_evidence, everything else -> initiative.

Idempotent: public_consultations is UNIQUE on initiative_id, so every write upserts.
Rows sourced from agencies are keyed on a different id space and are never touched.

Usage:
    python3.12 -m backend.scripts.sync_have_your_say --dry-run
    python3.12 -m backend.scripts.sync_have_your_say --apply
    python3.12 -m backend.scripts.sync_have_your_say --apply --initiative 16116
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

import requests
from sqlalchemy import text

from core.database import SessionLocal

API = "https://ec.europa.eu/info/law/better-regulation/brpapi/searchInitiatives"
DETAIL = "https://ec.europa.eu/info/law/better-regulation/brpapi/groupInitiatives/{id}"
PORTAL = ("https://ec.europa.eu/info/law/better-regulation/have-your-say/initiatives/"
          "{id}-{slug}_en")
HEADERS = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/151.0.0.0 Safari/537.36"),
           "Accept": "application/json"}

_STATUS = {"OPEN": "open", "UPCOMING": "upcoming", "CLOSED": "closed"}
_TYPE = {"OPC_LAUNCHED": "public_consultation", "PLANNING_WORKFLOW": "call_for_evidence"}


def slugify(s: str, limit: int = 60) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (s or "").lower()).strip("-")
    return s[:limit].rstrip("-")


def _parse_dt(v: Optional[str]) -> Optional[date]:
    if not v:
        return None
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    return None


def _pick_period(statuses: list, today: date):
    """One feedback period, and its status and BOTH its dates, taken together.

    An initiative has several feedback periods (a call for evidence, then a public
    consultation, sometimes a planned one). Until 29 Sep 2026 the status was "OPEN if
    ANY period is open" while start and end were the first non-null of each across ALL
    periods, so a row could carry an open status beside the end date of a period that
    closed weeks earlier. Initiative 18892 (Revision of the EIT Regulation) was stored
    open with end_date 23 Sep, which is the end of its CLOSED call for evidence, while
    the portal's next period is UPCOMING from 1 Oct. Four more rows were 'open' past
    their own end date, and one 'closed' row had an end date in the future.

    A record must describe ONE period. Preference: the period actually open now, else
    the one about to open, else the one that closed most recently.

    Returns (status, start, end), all three from the SAME period.
    """
    def end_of(s):
        return _parse_dt(s.get("feedbackEndDate"))

    def out(s, status):
        start, end = _parse_dt(s.get("feedbackStartDate")), end_of(s)
        # The portal itself publishes one impossible pair: initiative 14641 ("Clean
        # corporate vehicles") has a feedback period starting 18 December 2025 and
        # ending 2 April 2025. A start after its own end is not a start date, so it is
        # dropped here, where the record is read, rather than written and cleaned up
        # afterwards (which reported a repair on every run, for ever).
        if start and end and start > end:
            start = None
        return status, start, end

    live = [s for s in statuses if s.get("receivingFeedbackStatus") == "OPEN"]
    # An OPEN period whose deadline has passed is the portal being slow to flip its own
    # flag: the deadline it publishes is the fact, so it reads as closed here.
    current = [s for s in live if (end_of(s) or today) >= today]
    if current:
        return out(sorted(current, key=lambda s: (not s.get("isCurrent"),))[0], "open")
    if live:
        return out(max(live, key=lambda s: end_of(s) or date.min), "closed")

    # UPCOMING is a claim about the future and needs a window that has not already
    # passed. The portal keeps periods it planned and never ran: initiative 12131 is
    # still UPCOMING with a planned window of January to March 2020. Serving that as
    # forthcoming six years later is the same defect as serving a closed consultation
    # as open, so a planned window that has ended does not make a row upcoming.
    upcoming = [s for s in statuses if s.get("receivingFeedbackStatus") == "UPCOMING"]
    dated = [s for s in upcoming if end_of(s)]
    ahead = [s for s in dated if end_of(s) >= today]
    if ahead:
        return out(min(ahead, key=end_of), "upcoming")
    if dated:
        # Every planned window has already passed: it did not happen. Reported closed
        # with the last window published, never as still forthcoming.
        return out(max(dated, key=end_of), "closed")
    if upcoming:
        # Planned, no window published: nothing contradicts "upcoming", so say it and
        # carry no dates rather than borrowing another period's.
        return out(upcoming[0], "upcoming")

    closed = [s for s in statuses if s.get("receivingFeedbackStatus") == "CLOSED"]
    if closed:
        return out(max(closed, key=lambda s: end_of(s) or date.min), "closed")
    return None, None, None


def map_initiative(it: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw_id = it.get("id")
    if raw_id is None:
        return None
    iid = str(int(float(raw_id)))
    title = (it.get("shortTitle") or "").strip()
    if not title:
        return None

    statuses = it.get("currentStatuses") or []
    current = next((s for s in statuses if s.get("isCurrent")), statuses[0] if statuses else {})
    feedback = [s.get("receivingFeedbackStatus") for s in statuses]
    stage = current.get("frontEndStage") or ""

    # Status and the two dates come from ONE period, never assembled across several.
    status, start, end = _pick_period(statuses, date.today())
    if status is None:
        # every stage DISABLED: still only planned, or already past feedback
        status = "upcoming" if stage == "INIT_PLANNED" else "closed"

    ctype = _TYPE.get(stage, "initiative")

    topics = it.get("topics") or []
    dg = (topics[0].get("code") if topics else None) or None
    areas = [t.get("label") for t in topics if t.get("label")]

    desc = (f"Have Your Say initiative {iid}. Foreseen act type: "
            f"{it.get('foreseenActType') or 'not stated'}. Stage: {stage or 'not stated'}. "
            f"Feedback status upstream: {', '.join(x for x in feedback if x) or 'none'}. "
            f"Initiative status: {it.get('initiativeStatus') or 'not stated'}.")

    return {
        "initiative_id": iid,
        "title": title[:500],
        "short_title": title[:255],
        "description": desc,
        "consultation_type": ctype,
        "status": status,
        "dg_responsible": dg,
        "policy_areas": areas,
        "start_date": start,
        "end_date": end,
        "portal_url": PORTAL.format(id=iid, slug=slugify(title)),
        "source": "commission",
        "source_body": "European Commission",
        "relevance_score": 50,
    }


_UPSERT = text("""
    INSERT INTO public_consultations (
        initiative_id, title, short_title, description, consultation_type, status,
        dg_responsible, policy_areas, start_date, end_date, portal_url,
        source, source_body, relevance_score,
        created_at, updated_at, first_seen, last_updated, scraped_at
    ) VALUES (
        :initiative_id, :title, :short_title, :description,
        CAST(:consultation_type AS consultation_type_enum),
        CAST(:status AS consultation_status_enum),
        :dg_responsible, :policy_areas, :start_date, :end_date, :portal_url,
        :source, :source_body, :relevance_score,
        :now, :now, :now, :now, :now
    )
    ON CONFLICT (initiative_id) DO UPDATE SET
        title = EXCLUDED.title,
        short_title = EXCLUDED.short_title,
        description = EXCLUDED.description,
        consultation_type = EXCLUDED.consultation_type,
        status = EXCLUDED.status,
        dg_responsible = COALESCE(EXCLUDED.dg_responsible, public_consultations.dg_responsible),
        policy_areas = EXCLUDED.policy_areas,
        -- The two dates describe ONE feedback period, so they are written as a pair.
        -- COALESCE alone re-created the bug this job was fixing: a run whose chosen
        -- period had a start but no end kept a STALE end from an earlier period, and
        -- the row came out with a start date months after its own end date. A start
        -- that cannot belong beside the end we hold is not a start date: it is dropped
        -- rather than kept or guessed, and the invariant then holds at write time
        -- instead of being cleaned up afterwards (where it simply came back).
        -- The dates belong to the ONE feedback period the status describes, so they
        -- are replaced with it, never COALESCEd against what a previous period left.
        -- COALESCE kept re-creating the bug this job exists to fix, in both
        -- directions: initiative 12131 is UPCOMING with no window at the portal, and
        -- the stored January-to-March 2020 window survived beside it, so the row read
        -- as forthcoming with an end date six years past.
        --
        -- The one stored value worth keeping is a start date when this record
        -- describes the SAME period (its end date is unchanged) and simply does not
        -- carry a start: that is the detail endpoint, which publishes an end date and
        -- no start. Anything else is a date from another period and is dropped.
        start_date = CASE
            WHEN EXCLUDED.start_date IS NOT NULL THEN EXCLUDED.start_date
            WHEN EXCLUDED.end_date IS NOT NULL
             AND EXCLUDED.end_date = public_consultations.end_date
            THEN public_consultations.start_date
            ELSE NULL
        END,
        end_date = EXCLUDED.end_date,
        portal_url = EXCLUDED.portal_url,
        -- Fill a body another writer left empty (23 Sep 2026: open Commission
        -- consultations had NULL here, so body filters and labels missed them);
        -- never overwrite an agency code with the Commission default.
        source_body = COALESCE(public_consultations.source_body, EXCLUDED.source_body),
        -- updated_at / last_updated are NOT set here. The BEFORE UPDATE trigger
        -- update_consultation_updated_at() owns them (migration 245) and moves them
        -- only when a content field actually differs; it runs after this clause, so
        -- anything decided here would be overwritten. scraped_at is the ingestion
        -- anchor and moves every run, which is what answers "is this feed alive".
        scraped_at = EXCLUDED.scraped_at
""")


def _fetch_page(page: int, page_size: int, attempts: int = 4) -> Optional[Dict[str, Any]]:
    """One page, retried. The portal returns a transient 500 now and then."""
    for attempt in range(1, attempts + 1):
        try:
            r = requests.get(API, params={"text": "*", "size": page_size, "page": page,
                                          "language": "EN"},
                             headers=HEADERS, timeout=60)
            r.raise_for_status()
            return r.json()["initiativeResultDtoPage"]
        except Exception as exc:  # noqa: BLE001
            if attempt == attempts:
                print(f"  [WARN] page {page} failed after {attempts} attempts: "
                      f"{type(exc).__name__}: {exc}")
                return None
            time.sleep(1.5 * attempt)
    return None


SWEEP_COMPLETE = False


def fetch_all(page_size: int = 100, delay: float = 0.4) -> List[Dict[str, Any]]:
    """Page through every initiative.

    A failed page is skipped, never treated as the end of the run: the portal throws
    an intermittent 500 that succeeds on retry, and breaking out of the loop on it
    silently truncated the sweep to 700 of 4,091 records with no error.
    """
    out: List[Dict[str, Any]] = []
    failed: List[int] = []

    first = _fetch_page(0, page_size)
    if first is None:
        print("  [ERROR] could not fetch the first page; aborting")
        return []
    total_pages = first.get("totalPages") or 1
    print(f"  upstream: {first.get('totalElements')} initiatives across "
          f"{total_pages} pages of {page_size}")
    out.extend(first.get("content") or [])

    for page in range(1, total_pages):
        pg = _fetch_page(page, page_size)
        if pg is None:
            failed.append(page)
            continue
        out.extend(pg.get("content") or [])
        if (page + 1) % 10 == 0:
            print(f"    fetched {len(out)} ...")
        time.sleep(delay)

    if failed:
        print(f"  [WARN] {len(failed)} page(s) never returned: {failed}. "
              f"Coverage is incomplete; re-run to pick them up.")
    # A short sweep must not be read as "these initiatives left the portal". The
    # reconciliation below decides that a row the sweep did not return is unlisted,
    # and on a rate-limited run (29 Sep 2026) that turned 4 unlisted rows into 373.
    # Nothing was wrongly closed because the guard also requires an expired or absent
    # deadline, but the decision itself is only sound on a COMPLETE sweep.
    global SWEEP_COMPLETE
    SWEEP_COMPLETE = not failed
    return out


def fetch_one(initiative_id: str) -> List[Dict[str, Any]]:
    """Fetch a single initiative via the detail endpoint, shaped like a search hit."""
    r = requests.get(DETAIL.format(id=initiative_id), headers=HEADERS, timeout=60)
    r.raise_for_status()
    d = r.json()
    pubs = d.get("publications") or []
    # The DETAIL endpoint names these differently from the search endpoint: a
    # publication carries `endDate` (the deadline) and, for a period that has not
    # opened, `plannedStartDate` / `plannedEndDate`. It has no `feedbackStartDate`
    # or `feedbackEndDate` at all, so reading those names returned None for every
    # date and this repair path blanked both dates on any row it touched.
    # `feedbackPeriod` is a NUMBER OF WEEKS, not a date range, so no start date is
    # read for a period already open: unknown stays NULL rather than being computed.
    statuses = [{
        "frontEndStage": p.get("frontEndStage"),
        "receivingFeedbackStatus": p.get("receivingFeedbackStatus"),
        "feedbackStartDate": p.get("plannedStartDate"),
        "feedbackEndDate": p.get("endDate") or p.get("plannedEndDate"),
        "isCurrent": bool(p.get("isCurrent")),
    } for p in pubs]
    return [{
        "id": float(initiative_id),
        "shortTitle": d.get("shortTitle"),
        "reference": d.get("reference"),
        "foreseenActType": d.get("foreseenActType"),
        "initiativeStatus": d.get("initiativeStatus"),
        "currentStatuses": statuses or [{
            "frontEndStage": d.get("stage"),
            "receivingFeedbackStatus": d.get("receivingFeedbackStatus"),
            "isCurrent": True,
        }],
        "topics": d.get("topics") or [],
    }]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    ap.add_argument("--initiative", help="sync a single initiative id via the detail API")
    args = ap.parse_args()

    # Fetch BEFORE opening the database session. The full sweep spends minutes on
    # HTTP, and a session opened first is closed by the server underneath us: the
    # next statement then fails on a dead connection, which looks like a query bug
    # and rolls back the whole run before a single row is written.
    print("=== fetching Have Your Say ===")
    raw = fetch_one(args.initiative) if args.initiative else fetch_all()
    print(f"  fetched {len(raw)} initiative record(s)")

    db = SessionLocal()
    try:
        before = db.execute(
            text("SELECT count(*) FROM public_consultations WHERE source = 'commission'")
        ).scalar()
        print(f"\n=== before: {before} commission-sourced rows ===")

        rows, skipped = [], 0
        for it in raw:
            m = map_initiative(it)
            if m:
                rows.append(m)
            else:
                skipped += 1
        print(f"  mapped {len(rows)}, skipped {skipped} (no id or no title)")

        ids = [r["initiative_id"] for r in rows]
        dupes = len(ids) - len(set(ids))
        if dupes:
            print(f"  [WARN] {dupes} duplicate initiative_id in the fetch; last wins")
            dedup = {r["initiative_id"]: r for r in rows}
            rows = list(dedup.values())

        existing = set()
        if ids:
            existing = {
                r[0] for r in db.execute(
                    text("SELECT initiative_id FROM public_consultations "
                         "WHERE initiative_id = ANY(:ids)"), {"ids": ids}
                ).fetchall()
            }
        print(f"  already present: {len(existing)}   new: {len(rows) - len(existing)}")

        by_status: Dict[str, int] = {}
        for r in rows:
            by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        print(f"  status split: {by_status}")

        if args.dry_run:
            print("\n[DRY-RUN] nothing written")
            for r in rows[:3]:
                print(f"    {r['initiative_id']}: {r['title'][:60]} "
                      f"[{r['consultation_type']}/{r['status']}] dg={r['dg_responsible']}")
            return 0

        now = datetime.now(timezone.utc)
        written = 0
        for r in rows:
            db.execute(_UPSERT, {**r, "now": now})
            written += 1
            if written % 500 == 0:
                db.commit()
                print(f"    committed {written} ...")
        db.commit()
        print(f"\n[OK] upserted {written} rows")

        # ---- rows the portal no longer lists ----
        # searchInitiatives returns only the initiatives it currently indexes. An
        # initiative that drops out of it is never upserted again and keeps whatever
        # status it last had, for ever: initiative 18892 (Revision of the EIT
        # Regulation) was still served as OPEN on 29 Sep 2026, six days after its
        # feedback period closed, because it had left the search index while the
        # detail endpoint still answered correctly. Nothing in this job closed it,
        # and nothing ever would have.
        #
        # Only rows still CLAIMING to be live are worth re-reading; a closed row that
        # leaves the index is simply archived and cannot become wrong.
        if not SWEEP_COMPLETE:
            print("\n=== sweep incomplete; skipping the unlisted-row reconciliation ===")
            print("    (a row missing from a short sweep has not necessarily left the portal)")
            stale = []
        else:
            stale = [r[0] for r in db.execute(text(
                "SELECT initiative_id FROM public_consultations "
                "WHERE source = 'commission' AND status IN ('open', 'upcoming') "
                "AND initiative_id <> ALL(:ids)"), {"ids": ids}).fetchall()]
        print(f"\n=== {len(stale)} live row(s) the portal no longer lists; re-reading each ===")
        refreshed = failed = 0
        for iid in stale:
            try:
                one = fetch_one(iid)
            except Exception as exc:  # noqa: BLE001
                print(f"  [WARN] {iid}: {type(exc).__name__}: {exc}")
                failed += 1
                continue
            m = map_initiative(one[0]) if one else None
            if not m:
                failed += 1
                continue
            db.execute(_UPSERT, {**m, "now": datetime.now(timezone.utc)})
            refreshed += 1
            time.sleep(0.3)
        db.commit()
        print(f"  re-read {refreshed}, unreadable {failed}")

        # Last resort: a consultation cannot be open after its own published deadline.
        # This catches a row whose detail read failed as well as any future path that
        # writes the two fields apart.
        # A consultation cannot be open after its own published deadline; and a row the
        # portal no longer lists, whose detail endpoint 404s and which carries no
        # deadline at all, cannot be asserted open either -- nothing about it can ever
        # be checked again (initiative 18657, open since 3 July 2026, is exactly this).
        # Anything still listed is left alone: only the unreadable are closed here.
        shut = db.execute(text(
            "UPDATE public_consultations SET status = 'closed' "
            "WHERE source = 'commission' AND status = 'open' AND ("
            "  (end_date IS NOT NULL AND end_date < CURRENT_DATE)"
            "  OR (:complete AND end_date IS NULL AND initiative_id <> ALL(:ids))"
            ") RETURNING initiative_id"), {"ids": ids, "complete": SWEEP_COMPLETE}).fetchall()
        db.commit()
        print(f"  closed {len(shut)} unverifiable or expired row(s): "
              f"{[r[0] for r in shut][:8]}")

        # A start date LATER than its own end date is a leftover of the old logic,
        # which took the two from different feedback periods: the upsert keeps a
        # stored start when the current period supplies none (COALESCE), so a stale
        # one outlives the fix. It cannot belong to the period the end date describes,
        # so it is not a start date -- it is dropped rather than guessed at.
        crossed = db.execute(text(
            "UPDATE public_consultations SET start_date = NULL "
            "WHERE source = 'commission' AND start_date IS NOT NULL "
            "AND end_date IS NOT NULL AND start_date > end_date "
            "RETURNING initiative_id")).fetchall()
        db.commit()
        print(f"  dropped {len(crossed)} start date(s) later than their own end date")

        # ---- verification ----
        # On a FRESH session (25 Sep 2026): the upsert holds this one for
        # minutes, and the server dropped it right after the last commit, so
        # the verification crashed and the run exited 1 although all 4,112
        # rows were written. A verdict must not depend on a stale connection.
        db.close()
        db = SessionLocal()
        after = db.execute(
            text("SELECT count(*) FROM public_consultations WHERE source = 'commission'")
        ).scalar()
        total = db.execute(text("SELECT count(*) FROM public_consultations")).scalar()
        print("\n=== verification ===")
        print(f"  commission rows: {before} -> {after}   (+{after - before})")
        print(f"  table total    : {total}")
        # The set comprehension used to sit INSIDE the list comprehension, so this
        # query ran once per fetched id: 4,114 identical round trips, each returning
        # 4,114 rows, after every sync. Read the stored ids ONCE.
        stored = {r[0] for r in db.execute(
            text("SELECT initiative_id FROM public_consultations "
                 "WHERE initiative_id = ANY(:ids)"), {"ids": ids}).fetchall()}
        missing = [i for i in ids if i not in stored]
        print(f"  fetched ids not stored: {len(missing)}   "
              f"{'OK' if not missing else 'FAIL ' + str(missing[:5])}")
        return 0 if not missing else 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3.12
"""The final plenary vote on every adopted text, read from EP Open Data.

Why
---
202 adopted resolutions had no vote count (8 Oct 2026). ep_roll_call_votes, scraped
from doceo's roll-call HTML and matched to texts by TITLE, held one or two votes per
text out of the dozens Parliament takes, and 21 of its "final" votes were a committee
vote or a vote on one amendment.

EP Open Data publishes the whole chain, structured, with no WAF:
  adopted-texts/TA-10-2026-0191   adopts      -> eli/dl/doc/B-10-2026-0244 (the tabled text)
  meetings/MTG-PL-<date>/vote-results          -> each vote item, based_on that tabled text
  meetings/MTG-PL-<date>/decisions             -> each decision: counts, method, outcome,
                                                  time, and its label ("Motion for a
                                                  resolution (as a whole)")
The final vote is the item's ADOPTED decision whose label is a final-vote label (the
same rule the enrichment job applies to ep_roll_call_votes). A show-of-hands vote has
no count: stored with method 'show of hands' and null counts, never 0.

Writes texts_adopted.vote_results with source 'ep_open_data'. Every vote it finds is
compared with ep_roll_call_votes where both hold one, and disagreements are printed.
A text whose EP Open Data call fails is counted as not reachable and skipped (this job only
ADDS validated votes, it never clears one, so a partial run cannot read an outage as an
absence). Five failures in a row are treated as an outage and stop the run. Either way what
was found is written and the run exits 1, so sync_runs records the failure.

    python3.12 scripts/sync_texts_adopted_final_votes.py            # dry-run
    python3.12 scripts/sync_texts_adopted_final_votes.py --apply
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from sqlalchemy import create_engine, text

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from scripts.backfill_texts_adopted_procedures import _get  # noqa: E402
from scripts.sync_eu_law_eurovoc import _database_url  # noqa: E402
from scripts.enrich_ep_texts_and_resolutions import _FINAL_VOTE  # noqa: E402

_TA = re.compile(r"^P(\d+)_TA\((\d{4})\)(\d{4})$")
_FINAL = re.compile(_FINAL_VOTE, re.IGNORECASE)
_METHOD = {
    "VOTE_ELECTRONIC_ROLLCALL": "roll-call",
    "VOTE_ELECTRONIC": "electronic",
    "VOTE_HAND": "show of hands",
}

PICK = text("""
    SELECT id, ta_reference, vote_results FROM texts_adopted
    WHERE ta_reference ~ '^P[0-9]+_TA'
      AND (vote_results IS NULL OR vote_results->>'source' IS DISTINCT FROM 'ep_open_data'
           -- a counted vote stored with a missing count (zero omitted by the source)
           OR (vote_results->>'method' IN ('roll-call', 'electronic')
               AND (vote_results->'for' = 'null'::jsonb OR vote_results->'against' = 'null'::jsonb
                    OR vote_results->'abstention' = 'null'::jsonb)))
    ORDER BY ta_reference
""")
RCV = text("""
    SELECT votes_for, votes_against, votes_abstention FROM ep_roll_call_votes
    WHERE ta_reference = :ta AND level = 'plenary' AND votes_for IS NOT NULL AND subject ~* :fv
""")
STORE = text("UPDATE texts_adopted SET vote_results = CAST(:v AS jsonb) WHERE id = :id")

# Resolution procedures Parliament DECIDED on (OEIL) but for which no adopted text exists:
# either the text has not reached us yet, or the final vote was lost. Only the second is
# written here (8 Oct 2026: 2025/2138(INI), the Ombudsman report, read "adopted" while EP
# Open Data records its final vote REJECTED 233-250-76).
UNADOPTED = text("""
    SELECT r.id, r.procedure_ref, r.status, c.oeil_key_events::text AS events
    FROM ep_resolutions r
    JOIN legislative_carriages c ON c.oeil_procedure_ref = r.procedure_ref
    WHERE NOT EXISTS (SELECT 1 FROM texts_adopted t WHERE t.procedure_ref = r.procedure_ref
                        AND t.ta_reference ~ '^P[0-9]+_TA')
      AND c.oeil_key_events::text ~ '(Decision by Parliament|Results of vote in Parliament)'
""")
REJECT = text("""
    UPDATE ep_resolutions SET status = 'rejected', adoption_date = NULL, vote_date = :d,
           vote_for = :f, vote_against = :a, vote_abstention = :b,
           vote_total = :f + :a + :b
    WHERE id = :id
""")
_TABLED = re.compile(r"^(RC-)?([AB])(\d+)-(\d{4})/(\d{4})$")


def _tabled_eli(events: list) -> tuple[set, str | None]:
    """The tabled document(s) OEIL names, as EP Open Data ids, and the vote date."""
    docs, day = set(), None
    for e in events or []:
        m = _TABLED.match((e.get("description") or "").strip())
        if m:
            rc, kind, term, num, year = m.groups()
            docs.add(f"eli/dl/doc/{rc or ''}{kind}-{term}-{year}-{num}")
        if e.get("event_type") in ("Results of vote in Parliament", "Decision by Parliament") and e.get("date"):
            day = max(day or "", str(e["date"])[:10])
    return docs, day


def _final_any_outcome(meeting: "Meeting", adopts: set) -> dict | None:
    """The single final-vote decision on these documents, ADOPTED or REJECTED."""
    finals = {}
    for it in meeting.items:
        if adopts & set(it.get("based_on_a_realization_of") or []):
            for did in it.get("consists_of") or []:
                d = meeting.decisions.get(did)
                label = ((d or {}).get("referenceText") or {}).get("en") or ""
                first = label.strip().splitlines()[0].strip() if label.strip() else ""
                if d and _FINAL.match(first):
                    finals[did] = d
    return next(iter(finals.values())) if len(finals) == 1 else None


def _ta_id(ref: str) -> str | None:
    m = _TA.match(ref)
    return f"TA-{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def _items(body: dict | None) -> list[dict]:
    return (body or {}).get("data") or []


class Meeting:
    """One plenary sitting's vote items and decisions, fetched once."""

    def __init__(self, day: str):
        mid = f"MTG-PL-{day}"
        self.items = _items(_get(f"meetings/{mid}/vote-results?language=en&limit=5000"))
        self.decisions = {d["id"]: d for d in
                          _items(_get(f"meetings/{mid}/decisions?language=en&limit=5000"))}

    def final_vote(self, adopts: set[str]) -> tuple[dict | None, str]:
        items = [i for i in self.items if adopts & set(i.get("based_on_a_realization_of") or [])]
        if not items:
            return None, "no vote item for the adopted document"
        finals = {}
        for it in items:
            for did in it.get("consists_of") or []:
                d = self.decisions.get(did)
                if not d or not str(d.get("decision_outcome", "")).endswith("ADOPTED"):
                    continue
                label = (d.get("referenceText") or {}).get("en") or ""
                # First line only: a label can carry a second line naming the committee,
                # "Motion for a resolution (as a whole)\n(EMPL Committee)" (P10_TA(2026)0049).
                first = label.strip().splitlines()[0].strip() if label.strip() else ""
                if _FINAL.match(first):
                    # Keyed by decision: one vote can sit in two vote items (a split
                    # and the main item), which read as two finals (P10_TA(2026)0049).
                    finals[did] = d
        if len(finals) != 1:
            return None, f"{len(finals)} final-vote decisions"
        return next(iter(finals.values())), "ok"


def _counts(d: dict) -> tuple:
    """(for, against, abstention). EP Open Data OMITS a count that is zero: RC-B10-0066/2026
    reads 582 for, no 'against', 35 abstentions, 617 attendees. A missing count is 0 only
    when the attendees equal the counts present; otherwise it stays unknown (None)."""
    f, a, b = (d.get("number_of_votes_favor"), d.get("number_of_votes_against"),
               d.get("number_of_votes_abstention"))
    present = [x for x in (f, a, b) if x is not None]
    if present and len(present) < 3 and d.get("number_of_attendees") == sum(present):
        f, a, b = (0 if x is None else x for x in (f, a, b))
    return f, a, b


def _record(d: dict) -> dict:
    method = _METHOD.get(str(d.get("decision_method", "")).rsplit("/", 1)[-1], "other")
    counted = method != "show of hands"
    f, a, b = _counts(d) if counted else (None, None, None)
    return {
        "for": f,
        "against": a,
        "abstention": b,
        "result": "adopted",
        "method": method,
        "vote_date": d.get("activity_start_date"),
        "decision": d.get("activity_id"),
        "source": "ep_open_data",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="Persist (default dry-run)")
    ap.add_argument("--limit", type=int, default=0, help="At most N texts (0 = all)")
    ap.add_argument("--deadline-seconds", type=int, default=0,
                    help="Stop reading after this long and store what was found (0 = no limit). "
                         "The run is resumable: the next one starts where this stopped.")
    args = ap.parse_args()

    engine = create_engine(_database_url(), pool_pre_ping=True)
    with engine.connect() as conn:
        rows = list(conn.execute(PICK))
    if args.limit:
        rows = rows[:args.limit]
    print(f"[INFO] adopted texts without an EP Open Data final vote: {len(rows)}")

    meetings: dict[str, Meeting] = {}
    plan, reasons, methods = [], {}, {}
    examples: dict[str, list[str]] = {}
    agree = disagree = 0
    started = time.monotonic()
    stopped_early = 0
    fetch_failed = consecutive = 0
    for n, r in enumerate(rows, 1):
        if consecutive >= 5:
            stopped_early = len(rows) - n + 1
            print(f"[ERROR] 5 EP Open Data failures in a row: treating it as an outage")
            break
        try:
            if args.deadline_seconds and time.monotonic() - started > args.deadline_seconds:
                stopped_early = len(rows) - n + 1
                break
            if n % 25 == 0:
                print(f"   ...{n}/{len(rows)} read, {len(plan)} final votes, "
                      f"{time.monotonic() - started:.0f}s", flush=True)
            tid = _ta_id(r.ta_reference)
            doc = (_items(_get(f"adopted-texts/{tid}?language=en")) or [None])[0] if tid else None
            if not doc or not doc.get("adopts") or not doc.get("document_date"):
                why = "not on EP Open Data / no adopted document"
                reasons[why] = reasons.get(why, 0) + 1
                examples.setdefault(why, []).append(r.ta_reference)
                continue
            consecutive = 0
            day = doc["document_date"][:10]
            if day not in meetings:
                meetings[day] = Meeting(day)
            d, why = meetings[day].final_vote(set(doc["adopts"]))
            if not d:
                reasons[why] = reasons.get(why, 0) + 1
                examples.setdefault(why, []).append(r.ta_reference)
                continue
            rec = _record(d)
            methods[rec["method"]] = methods.get(rec["method"], 0) + 1
            # Cross-check against the doceo-scraped table where it holds the final vote.
            with engine.connect() as conn:
                old = conn.execute(RCV, {"ta": r.ta_reference, "fv": _FINAL_VOTE}).fetchall()
            if old and rec["for"] is not None:
                same = any((o[0], o[1], o[2]) == (rec["for"], rec["against"], rec["abstention"]) for o in old)
                agree += same
                disagree += not same
                if not same:
                    print(f"   [DISAGREE] {r.ta_reference}: open data {rec['for']}/{rec['against']}/"
                          f"{rec['abstention']} vs scraped {[tuple(o) for o in old]}")
            plan.append((r.id, r.ta_reference, rec))
            consecutive = 0
        except RuntimeError as exc:  # _get exhausted its retries: not reachable, never "absent"
            fetch_failed += 1
            consecutive += 1
            examples.setdefault("EP Open Data not reachable", []).append(r.ta_reference)
            print(f"   [UNREACHABLE] {r.ta_reference}: {exc}", flush=True)

    if stopped_early:
        print(f"[INFO] stopped early: {stopped_early} text(s) left for the next run")
    if fetch_failed:
        reasons["EP Open Data not reachable"] = fetch_failed
    print(f"[INFO] final vote found: {len(plan)}  by method: {methods}")
    print(f"[INFO] not found: {reasons}")
    for why, refs in examples.items():
        print(f"   [{why}] e.g. {', '.join(refs[:4])}")
    print(f"[INFO] cross-check with ep_roll_call_votes: agree={agree} disagree={disagree}")
    for _, ref, rec in plan[:5]:
        print(f"   {ref:20} {rec['method']:14} {rec['for']}/{rec['against']}/{rec['abstention']}  {rec['vote_date']}")
    if not args.apply:
        print(f"[DRY-RUN] {len(plan)} row(s) would be written")
        return 0
    with engine.begin() as conn:
        for row_id, _, rec in plan:
            conn.execute(STORE, {"id": row_id, "v": json.dumps(rec)})
    print(f"[APPLIED] {len(plan)} row(s) written")

    # Phase 2: resolutions decided without an adopted text. Rejected -> recorded as such.
    with engine.connect() as conn:
        pending = list(conn.execute(UNADOPTED))
    rejected = 0
    for r in pending:
        try:
            docs, day = _tabled_eli(json.loads(r.events or "[]"))
            if not docs or not day:
                continue
            meetings.setdefault(day, None)
            if meetings[day] is None:
                meetings[day] = Meeting(day)
            d = _final_any_outcome(meetings[day], docs)
        except RuntimeError as exc:
            fetch_failed += 1
            print(f"   [UNREACHABLE] {r.procedure_ref}: {exc}")
            continue
        if d and str(d.get("decision_outcome", "")).endswith("REJECTED"):
            f, a, b = _counts(d)
            print(f"   [REJECTED] {r.procedure_ref}: final vote {f}/{a}/{b} on {day}")
            if f is not None and a is not None and b is not None:
                rejected += 1
                with engine.begin() as conn:
                    conn.execute(REJECT, {"id": r.id, "d": day, "f": f, "a": a, "b": b})
    print(f"[INFO] resolutions decided without an adopted text: {len(pending)}; recorded rejected: {rejected}")
    if fetch_failed:
        print(f"[ERROR] {fetch_failed} text(s) not reachable on EP Open Data this run")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

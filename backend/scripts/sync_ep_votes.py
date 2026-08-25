"""
Populate ep_votes / ep_vote_records from doceo (committee + plenary roll-calls).

Strategy (keyed on what is reliably available):
  * Anchor set  = texts_adopted rows (every adopted text HAD a plenary vote).
                  adoption_date::date == the plenary sitting -> the PV-...-RCV URL.
  * Plenary     = fetch the sitting's RCV page ONCE, match the texts_adopted
                  title to a roll-call item, take the decisive sub-item.
  * Committee   = the matched sub-item carries the A-report code -> fetch that
                  committee report, parse "Result of final vote" + roll-call.
  * Both rows are keyed by the OEIL procedure ref + carriage_id so a vote links
                  to the same dossier MEUB already aligns on. The committee +
                  plenary rows together give the committee->plenary delta.

WAF: all doceo docs are JS-challenge-walled -> WafBrowserFetcher (Playwright).
NO LLM / NO Anthropic.

Usage:
    # dry-run (default), PI committees, recent sittings
    python3.12 -m scripts.sync_ep_votes --committees AGRI,PECH,ENVI,SANT --since 2026-01-01
    python3.12 -m scripts.sync_ep_votes --committees AGRI,PECH,ENVI,SANT --since 2026-01-01 --apply
    python3.12 -m scripts.sync_ep_votes --ta "P10_TA(2026)0188" --apply
"""

import argparse
import time
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path

from sqlalchemy import text as sqla_text

from core.database import SessionLocal
from models.ep_vote import EpVote, EpVoteRecord
from services.scrapers.ep_votes_scraper import (
    parse_committee_report, parse_plenary_rcv, pick_final_subitem,
    committee_report_url, rcv_url,
)
from services.scrapers.waf_browser_fetcher import WafBrowserFetcher


# ---- title matching -------------------------------------------------------

_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]")


def _norm(s: str) -> str:
    s = (s or "").lower().replace("***", " ")
    s = _PUNCT.sub(" ", s)
    return _WS.sub(" ", s).strip()


def _title_matches(ta_title: str, item_title: str) -> bool:
    a, b = _norm(ta_title), _norm(item_title)
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    aw, bw = set(a.split()), set(b.split())
    if not aw or not bw:
        return False
    jac = len(aw & bw) / len(aw | bw)
    return jac >= 0.6


_ADOPTED_DATE_RE = re.compile(r"Date adopted\s*\n\s*(\d{1,2})\.(\d{1,2})\.(\d{4})")


def _committee_adopted_date(text: str):
    m = _ADOPTED_DATE_RE.search(text or "")
    if not m:
        return None
    d, mo, y = (int(x) for x in m.groups())
    try:
        return date(y, mo, d)
    except ValueError:
        return None


# ---- target selection -----------------------------------------------------

def _select_targets(db, committees, since, ta, limit):
    sql = ["SELECT ta_reference, title, procedure_ref, adoption_date, committees",
           "FROM texts_adopted WHERE adoption_date IS NOT NULL"]
    params = {}
    if ta:
        sql.append("AND ta_reference = :ta")
        params["ta"] = ta
    if committees:
        sql.append("AND committees && CAST(:coms AS varchar[])")
        params["coms"] = committees
    if since:
        sql.append("AND adoption_date >= :since")
        params["since"] = since
    sql.append("ORDER BY adoption_date DESC")
    if limit:
        sql.append("LIMIT :lim")
        params["lim"] = limit
    rows = db.execute(sqla_text(" ".join(sql)), params).mappings().all()
    return [dict(r) for r in rows]


def _carriage_id(db, procedure_ref):
    if not procedure_ref:
        return None
    row = db.execute(
        sqla_text("SELECT id FROM legislative_carriages WHERE oeil_procedure_ref = :r LIMIT 1"),
        {"r": procedure_ref},
    ).first()
    return row[0] if row else None


# ---- upsert ---------------------------------------------------------------

def _upsert_vote(db, *, vote_key, level, pv, apply, **fields):
    """Insert/replace an ep_votes row + its records. Returns 'added'|'updated'|'skipped'."""
    existing = db.query(EpVote).filter(EpVote.vote_key == vote_key).first()
    if existing and not apply:
        return "skipped"

    if not apply:
        return "added"

    if existing:
        db.query(EpVoteRecord).filter(EpVoteRecord.vote_id == existing.id).delete()
        vote = existing
        status = "updated"
    else:
        vote = EpVote(vote_key=vote_key)
        db.add(vote)
        status = "added"

    vote.level = level
    vote.result = pv.result
    vote.votes_for = pv.votes_for
    vote.votes_against = pv.votes_against
    vote.votes_abstention = pv.votes_abstention
    vote.vote_type = pv.vote_type
    vote.group_breakdown = pv.group_breakdown()
    vote.total_records = pv.total_records
    for k, v in fields.items():
        setattr(vote, k, v)
    db.flush()

    for r in pv.records:
        db.add(EpVoteRecord(
            vote_id=vote.id, mep_name=r.name,
            political_group=r.group, vote_choice=r.choice,
        ))
    return status


# ---- main -----------------------------------------------------------------

def run(committees, since, ta, limit, apply, max_sittings, deadline_seconds=None):
    """Sync EP votes.

    `deadline_seconds` bounds the run in wall-clock time. Without it this job was
    SIGKILLed by the cron's 1200s timeout on every run from 16 June 2026 onward,
    which lost the ENTIRE run: no rows, no partial progress, just `timeout_1200s`
    in sync_runs 49 times in a row.

    Capping `--max-sittings` alone could not fix that, because the sitting cap
    bounds only the RCV pages. Each target inside those sittings can trigger a
    SECOND browser fetch for its committee report, and that loop was uncapped:
    6 sittings held 80 targets, so the real worst case was ~98 fetches, not 18.

    On expiry the run stops cleanly, commits what it has, and prints exactly what
    it skipped. Sittings are processed newest-first, so the tail catches up on
    later runs instead of never being reached at all.
    """
    db = SessionLocal()
    counts = {"plenary_added": 0, "plenary_updated": 0, "committee_added": 0,
              "committee_updated": 0, "no_match": 0, "no_rcv": 0, "no_committee": 0}
    rcv_cache: dict = {}
    committee_cache: dict = {}
    started = time.monotonic()
    skipped_sittings: list = []
    skipped_reports: set = set()

    def out_of_time() -> bool:
        return deadline_seconds is not None and (time.monotonic() - started) >= deadline_seconds

    try:
        targets = _select_targets(db, committees, since, ta, limit)
        print(f"[INFO] {len(targets)} adopted-text targets selected")

        # Group by sitting date so we fetch each RCV page once.
        by_sitting: dict = {}
        for t in targets:
            d = t["adoption_date"].date()
            by_sitting.setdefault(d, []).append(t)

        sittings = sorted(by_sitting.keys(), reverse=True)
        if max_sittings:
            sittings = sittings[:max_sittings]
        print(f"[INFO] {len(sittings)} sitting days to fetch"
              + (f" (capped from {len(by_sitting)})" if max_sittings and len(by_sitting) > max_sittings else ""))

        # settle_ms measured, not guessed (25 Aug 2026): 9000 / 3000 / 1500 ms
        # returned BYTE-IDENTICAL html and an identical parse (15 items, 144
        # subitems) on two RCV dates and a committee report, while costing
        # 12.9s / 6.3s / 4.3s per fetch. 3000 keeps a 2x margin over the lowest
        # value proven sufficient, and roughly halves the run.
        with WafBrowserFetcher(settle_ms=3000, networkidle_ms=20000) as fetcher:
            for sitting in sittings:
                if out_of_time():
                    skipped_sittings = [str(x) for x in sittings[sittings.index(sitting):]]
                    break
                # RCV page (try the sitting date, then +/-1 day for tz edge).
                items = None
                for cand in (sitting, sitting + timedelta(days=1), sitting - timedelta(days=1)):
                    if cand in rcv_cache:
                        items = rcv_cache[cand]
                        if items:
                            sitting_used = cand
                            break
                        continue
                    url = rcv_url(cand)
                    res = fetcher.fetch(url, expand_accordions=True, strip_chrome=False)
                    parsed = parse_plenary_rcv(res.html) if res.html else {}
                    rcv_cache[cand] = parsed
                    if parsed:
                        items = parsed
                        sitting_used = cand
                        break
                if not items:
                    counts["no_rcv"] += len(by_sitting[sitting])
                    print(f"  [{sitting}] no RCV page / no items")
                    continue

                for t in by_sitting[sitting]:
                    # Match this adopted text to a roll-call item by title.
                    match = None
                    for itno, it in items.items():
                        if _title_matches(t["title"], it["title"]):
                            match = it
                            break
                    if not match:
                        counts["no_match"] += 1
                        continue
                    fin = pick_final_subitem(match["subitems"])
                    if not fin:
                        counts["no_match"] += 1
                        continue

                    cid = _carriage_id(db, t["procedure_ref"])
                    lead = (t["committees"] or [None])[0]
                    pv = fin["vote"]

                    # ---- plenary row
                    st = _upsert_vote(
                        db, vote_key=f"plenary|{sitting_used.isoformat()}|{fin['subitem_number']}",
                        level="plenary", pv=pv, apply=apply,
                        procedure_ref=t["procedure_ref"], carriage_id=cid,
                        report_ref=fin["report_ref"], ta_reference=t["ta_reference"],
                        title=t["title"], subject=fin["subject"], committee_code=lead,
                        vote_date=sitting_used, sitting_date=sitting_used,
                        item_number=fin["subitem_number"], source_url=rcv_url(sitting_used),
                    )
                    counts[f"plenary_{st}"] = counts.get(f"plenary_{st}", 0) + 1

                    # ---- committee row (from the A-report code on the sub-item)
                    rep = fin.get("report_ref")
                    if not rep:
                        counts["no_committee"] += 1
                    else:
                        if rep in committee_cache:
                            cpv, ctext = committee_cache[rep]
                        elif out_of_time():
                            # The uncapped loop. Skip the fetch and keep the plenary
                            # row already written above.
                            #
                            # `continue`, NOT a fall-through: reaching the `if cpv`
                            # test below would land in `no_committee`, recording a
                            # report we never LOOKED at as a report that does not
                            # EXIST. Those are different facts and only one of them
                            # is about the upstream site.
                            skipped_reports.add(rep)
                            continue
                        else:
                            curl = committee_report_url(rep)
                            ctext = fetcher.fetch(curl).text if curl else ""
                            cpv = parse_committee_report(ctext) if ctext else None
                            committee_cache[rep] = (cpv, ctext)
                        if cpv:
                            cst = _upsert_vote(
                                db, vote_key=f"committee|{rep}",
                                level="committee", pv=cpv, apply=apply,
                                procedure_ref=t["procedure_ref"], carriage_id=cid,
                                report_ref=rep, ta_reference=t["ta_reference"],
                                title=t["title"], subject="Committee final vote",
                                committee_code=lead, vote_date=_committee_adopted_date(ctext),
                                source_url=committee_report_url(rep),
                            )
                            counts[f"committee_{cst}"] = counts.get(f"committee_{cst}", 0) + 1
                        else:
                            counts["no_committee"] += 1

                    print(f"  [{sitting_used}] {t['ta_reference']} <- plenary {pv.votes_for}/{pv.votes_against}/{pv.votes_abstention}"
                          f"{' + committee ' + str(rep) if rep else ''}")

                if apply:
                    db.commit()

        if apply:
            db.commit()   # persist whatever the deadline let us finish

        print(f"\n[{'APPLIED' if apply else 'DRY-RUN'}] " + ", ".join(f"{k}={v}" for k, v in counts.items() if v))
        elapsed = time.monotonic() - started
        if skipped_sittings or skipped_reports:
            # Stating the drop is the point. A cap that says nothing is how this
            # codebase shipped `all_items[:20]` and lost 41 of 61 news items.
            print(f"[WARN] deadline {deadline_seconds}s reached after {elapsed:.0f}s: "
                  f"{len(skipped_sittings)} sitting(s) not fetched "
                  f"({', '.join(skipped_sittings) or '-'}), "
                  f"{len(skipped_reports)} committee report(s) skipped. "
                  f"Newest-first, so the next run resumes at the tail.")
        else:
            print(f"[INFO] complete in {elapsed:.0f}s, nothing skipped.")
    finally:
        db.close()


def main():
    p = argparse.ArgumentParser(description="Sync EP committee + plenary votes from doceo.")
    p.add_argument("--committees", help="Comma list, e.g. AGRI,PECH,ENVI,SANT")
    p.add_argument("--since", help="Only adopted texts on/after this date (YYYY-MM-DD)")
    p.add_argument("--ta", help="A single TA reference, e.g. 'P10_TA(2026)0188'")
    p.add_argument("--limit", type=int, help="Cap number of adopted-text targets")
    p.add_argument("--max-sittings", type=int, help="Cap number of sitting days fetched")
    p.add_argument("--apply", action="store_true", help="Persist (default dry-run)")
    p.add_argument("--deadline-seconds", type=int,
                   help="Wall-clock budget. Stop cleanly and report what was skipped "
                        "rather than being killed by the cron timeout.")
    args = p.parse_args()

    coms = [c.strip().upper() for c in args.committees.split(",")] if args.committees else None
    run(coms, args.since, args.ta, args.limit, args.apply, args.max_sittings,
        deadline_seconds=args.deadline_seconds)


if __name__ == "__main__":
    main()

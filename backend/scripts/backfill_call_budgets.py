"""Fill in the budget on calls for proposals, from the portal's own topic page.

Every one of the 58 open calls in the Tenderator showed no budget, because the
SEDIA search API the ingest reads does not carry one: its 21 metadata fields
cover identifiers, dates, titles and URLs, and nothing else. The figure does
exist, one level down, in the portal's topicDetails JSON, under
budgetOverviewJSONItem.

For a client deciding whether to bid, the budget is the second thing they look
at after the deadline. A LIFE standard action project on circular economy is
worth EUR 79,000,000; its sibling call on environmental governance is worth
EUR 6,500,000. Those are different propositions, and the Tenderator was showing
neither.

The map is keyed by an internal id and holds SEVERAL topics, so each entry must
be matched on its `action` string, which begins with the topic identifier.
Taking the first entry would have given the circular economy call the
governance call's budget: wrong by a factor of twelve, and wrong in the
direction that loses a bid decision.

Budgets are summed across budget years, because a call can span more than one.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

from sqlalchemy import text

from core.database import SessionLocal

DETAILS = ("https://ec.europa.eu/info/funding-tenders/opportunities/data/"
           "topicDetails/{topic}.json")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")


def fetch_budget(topic_id: str) -> tuple[float | None, str, list[str]]:
    """Total budget for this topic in euro, why not, and the sibling topics
    that share the same envelope.

    A budget key can cover several topics. LIFE-2026-SAP-NAT-NATURE and
    LIFE-2026-SAP-NAT-GOV both sit under key 114290 with the same
    EUR 173,500,000, which is one envelope the two of them draw on, not
    EUR 347,000,000 between them. The figure stored is the portal's own figure
    for that topic, which is what its topic page shows, but the sharing is
    reported so nobody reads it as money reserved for one call.
    """
    url = DETAILS.format(topic=topic_id.lower())
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": UA, "Accept": "application/json"})
        raw = urllib.request.urlopen(req, timeout=90).read()
    except urllib.error.HTTPError as e:
        return None, f"http {e.code}", []
    except Exception as e:  # noqa: BLE001
        return None, type(e).__name__, []

    try:
        j = json.loads(raw)
    except Exception:  # noqa: BLE001
        return None, "not json", []
    td = j.get("TopicDetails") or j
    if isinstance(td, list):
        td = td[0] if td else {}
    b = td.get("budgetOverviewJSONItem")
    if not b:
        return None, "no budget block", []
    if isinstance(b, str):
        try:
            b = json.loads(b)
        except Exception:  # noqa: BLE001
            return None, "budget block unparseable", []

    total = 0.0
    matched = 0
    shared: list[str] = []
    for key, entries in (b.get("budgetTopicActionMap") or {}).items():
        mine = [e for e in (entries or [])
                if (e.get("action") or "").upper().startswith(topic_id.upper())]
        if not mine:
            continue
        # Everything else under the same key draws on the same envelope.
        for e in entries or []:
            other = (e.get("action") or "").split(" - ")[0].strip()
            if other and other.upper() != topic_id.upper() and other not in shared:
                shared.append(other)
        for e in mine:
            matched += 1
            # The identifier that starts the action string is the match, never
            # the position in the list: taking the first entry would have given
            # the circular economy call its sibling's budget.
            for v in (e.get("budgetYearMap") or {}).values():
                try:
                    total += float(v)
                except (TypeError, ValueError):
                    pass
    if not matched:
        return None, "topic not in its own budget map", []
    if total <= 0:
        return None, "budget present but zero", shared
    return total, "ok", shared


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pattern", default="LIFE-%",
                    help="topic_id ILIKE pattern (default LIFE-%%)")
    ap.add_argument("--status", default="open",
                    help="only calls in this status, or 'any'")
    ap.add_argument("--limit", type=int, default=100)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    rc = 0
    try:
        where = "indicative_budget IS NULL AND topic_id ILIKE :p"
        params = {"p": args.pattern, "lim": args.limit}
        if args.status != "any":
            where += " AND status = :s"
            params["s"] = args.status
        rows = db.execute(text(
            f"SELECT topic_id, title FROM ft_calls_for_proposals WHERE {where} "
            f"ORDER BY deadline DESC NULLS LAST LIMIT :lim"), params).fetchall()
        print(f"=== {len(rows)} call(s) with no budget matching {args.pattern!r} ===")

        found, missing, shared_envelopes = [], [], []
        for r in rows:
            total, why, shared = fetch_budget(r.topic_id)
            if total is None:
                missing.append((r.topic_id, why))
                print(f"  [--] {r.topic_id:<34} {why}")
            else:
                found.append((r.topic_id, total))
                note = f"  shared with {', '.join(shared)}" if shared else ""
                if shared:
                    shared_envelopes.append((r.topic_id, shared))
                print(f"  [OK] {r.topic_id:<34} EUR {total:>14,.0f}{note}")
                if args.apply:
                    db.execute(text(
                        "UPDATE ft_calls_for_proposals SET indicative_budget = :b, "
                        "budget_currency = 'EUR', last_updated = now() "
                        "WHERE topic_id = :t"), {"b": total, "t": r.topic_id})
                    # funding_opportunities mirrors the same calls
                    db.execute(text(
                        "UPDATE funding_opportunities SET indicative_budget = :b, "
                        "budget_currency = 'EUR', last_updated = now() "
                        "WHERE topic_id = :t AND indicative_budget IS NULL"),
                        {"b": total, "t": r.topic_id})
            time.sleep(0.4)

        print(f"\n  resolved {len(found)}, unresolved {len(missing)}, "
              f"shared envelopes {len(shared_envelopes)}")
        for topic, sib in shared_envelopes:
            print(f"    {topic} shares its envelope with {', '.join(sib)}")
        if not args.apply:
            print("\n[DRY-RUN] nothing written")
            return 0
        db.commit()

        print("\n=== verification ===")
        for topic, total in found:
            got = db.execute(text(
                "SELECT indicative_budget, budget_currency FROM ft_calls_for_proposals "
                "WHERE topic_id = :t"), {"t": topic}).fetchone()
            ok = got and float(got.indicative_budget or 0) == total \
                and got.budget_currency == "EUR"
            print(f"  {'OK ' if ok else 'FAIL'} {topic:<34} "
                  f"{float(got.indicative_budget or 0):,.0f} {got.budget_currency}")
            if not ok:
                rc = 1
        # a budget must never be negative or absurd; catch a parse that went wrong
        bad = db.execute(text(
            "SELECT count(*) FROM ft_calls_for_proposals "
            "WHERE indicative_budget IS NOT NULL "
            "  AND (indicative_budget <= 0 OR indicative_budget > 1e11)")).scalar()
        print(f"  implausible budgets in the table: {bad} {'OK' if not bad else 'FAIL'}")
        if bad:
            rc = 1
        return rc
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

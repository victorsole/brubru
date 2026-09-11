"""Refuse to write a NEW news row nobody could date (11 September 2026).

Why
---
Victor, 11 Sep 2026: "All rows should come always dated, so we have to make sure
they do come dated." Measured that morning, 14 of the sources feeding eu_news_items
had left rows undated in the previous 60 days, and 469 rows were undated in total.
The listing parsers now read the dates their pages print (dg_news_scraper,
bespoke_news_scraper), which dates almost everything at the source. This is the
backstop for the rest: an item whose listing carries no date gets one more chance,
from its own page, before it is written -- and if that fails too, it is NOT written.

What it does, and what it deliberately does not
-----------------------------------------------
* Items that already carry a date pass straight through, with no query.
* Items that ALREADY EXIST pass through untouched, dated or not. The writers' update
  paths never null a date, and dating the stock is a separate job
  (scripts/backfill_news_document_dates.py), so refusing here would only stop a
  title fix from landing.
* A NEW undated item is resolved by services.news.item_date.resolve_item_date --
  the same chain the backfill proved -- reusing the writer's open browser if it has
  one. Dated: written. Still undated: refused, with the reason.

A refusal is recorded, never silent
-----------------------------------
Refusing a row turns a visible defect (an undated row that /api/v2/news/latest counts)
into an invisible one (a row that is simply missing). So every refusal is written to
the sync_runs ledger as status `failed`, under `<writer>_undated_refused`, naming each
item and why ([[feedback_silent_failure_reports_success]]).

Two deliberate choices in that record:
* It is NOT the writer's own exit code. The cron marks a non-zero exit `failed`, and
  services.sync.freshness treats a feed whose latest run is not `success` as stale:
  one undatable CoR story would have turned the whole "News - other bodies" chip stale
  for users and sent the staleness email every three hours.
* Its key is not a registered MEUB source and its tier is NULL, so it reaches the
  admin panel's failure count and recent-failures list without touching any feed's
  freshness or /api/sync/health tier verdicts.
"""
from __future__ import annotations

import sys
from typing import Iterable, List, Tuple

from sqlalchemy import text

from services.news.item_date import resolve_item_date
from services.sync.freshness import record_run

REFUSAL_SOURCE_SUFFIX = "_undated_refused"
_MAX_LISTED = 40


def date_new_items(db, items: Iterable[dict], *, fetcher=None) -> Tuple[List[dict], List[dict]]:
    """Split eu_news_items candidates into (to_write, refused).

    Resolved dates are written back onto the item dict as `news_date` (a date), so the
    writer's existing upsert stores them unchanged. Refused items carry
    `undated_reason`.
    """
    items = list(items or [])
    undated_keys = [i["entry_key"] for i in items if not i.get("news_date") and i.get("entry_key")]
    if not undated_keys:
        return items, []
    existing = {r[0] for r in db.execute(
        text("SELECT entry_key FROM eu_news_items WHERE entry_key = ANY(:k)"),
        {"k": undated_keys},
    )}
    keep: List[dict] = []
    refused: List[dict] = []
    for it in items:
        if it.get("news_date") or (it.get("entry_key") in existing):
            keep.append(it)
            continue
        dt, why = resolve_item_date(it.get("source_url") or "", fetcher=fetcher)
        if dt is not None:
            it["news_date"] = dt.date()
            keep.append(it)
        else:
            it["undated_reason"] = why
            refused.append(it)
    return keep, refused


def record_refusals(db, writer_key: str, refused: List[dict]) -> None:
    """Write one ledger row naming every refused item, and say it on stderr.

    Call once at the END of a run, after the writer's own commits: record_run commits,
    and calling it mid-source would commit that source's half-written transaction.
    """
    if not refused:
        return
    lines = [f"{i.get('source_key') or i.get('institution') or '?'}  "
             f"{i.get('undated_reason')}  {i.get('source_url')}"
             for i in refused[:_MAX_LISTED]]
    more = len(refused) - len(lines)
    msg = (f"{len(refused)} new news item(s) NOT written: no publication date on the "
           "listing or on the item's own page.\n" + "\n".join(lines)
           + (f"\n...and {more} more" if more > 0 else ""))
    print(f"[{writer_key}] REFUSED undated items:\n{msg}", file=sys.stderr)
    record_run(db, source_key=f"{writer_key}{REFUSAL_SOURCE_SUFFIX}", tier=None,
               status="failed", items_added=0, error=msg)

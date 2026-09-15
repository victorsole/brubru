#!/usr/bin/env python3.12
"""Replace placeholder news dates (the 1st of a month or 1 January, read off a URL) with
the date the item's own source prints.

Why (measured 15 September 2026)
--------------------------------
Older writers dated items from the year or month in their URL, so the day was invented:
FRA `/en/news/2026/<slug>` became 1 January 2026 (57 of 67 rows), EDPS `/2025/` became
1 January 2025 (8), CJEU `.../pdf/2026-04/cp260052en.pdf` became 1 April (50), ECA
`NEWS2026_05_NEWSLETTER_01` became 1 May (8). Such a date counts as "dated", so no
undated-row check sees it (feedback_placeholder_dates_hide_in_dated_counts). The same
shape also matches rows whose 1st-of-month date may be REAL (Commission, Council,
several agencies), so a match is only a candidate.

What it does
------------
Candidates, in both stores: a date on day 1 whose year and month (or, for 1 January,
whose year) appear in the item's URL. For each, the item's own source is read:
  services/news/item_date.resolve_item_date, the resolver the news writers use, with
  ONE browser: site rules for EDPS and ECA and the PDF dateline carrier for the CJEU
  were added to it on 15 Sep 2026, so new rows get the same answer.
A found date replaces the placeholder only if it is CONSISTENT with the URL: the same
year for a year folder; within the URL month or the month before it for a month folder
(ECA dates a month's newsletter in the last days of the previous month). A composed
body repeats the date ("Published by FRA on 2026-01-01"), so it is recomposed.

Outcomes: `redated`, `confirmed` (the page says day 1 too: left alone), `inconsistent`
(left alone, reported), `no_carrier` (left alone, reported). Nothing is guessed and
nothing is nulled here; what to do with a row no source can date is a separate call.

Every changed row is written to a JSON backup first. Idempotent: a redated row is no
longer a candidate.

Usage
-----
    python3.12 scripts/redate_placeholder_news_dates.py                # dry run
    python3.12 scripts/redate_placeholder_news_dates.py --apply
    python3.12 scripts/redate_placeholder_news_dates.py --institution FRA --limit 5
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_BACKEND = pathlib.Path(__file__).resolve().parents[1]
for _p in (str(_REPO_ROOT), str(_BACKEND)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_URL_MONTH = re.compile(r"(?<!\d)(20\d\d)[-_/](0[1-9]|1[0-2])(?!\d)")
_URL_YEAR = re.compile(r"/(20\d\d)(?:/|$)")


def placeholder_kind(d: date | None, url: str) -> str | None:
    """'url_month' or 'url_year' when the date is the 1st that the URL would give."""
    if d is None or d.day != 1:
        return None
    u = url or ""
    # A URL that names the DAY (Council /2026/09/01/, a DG slug ending -2026-07-01_en)
    # states the date; its 1st is real, not a placeholder.
    if re.search(rf"(?<!\d){d.year}[-_/]{d.month:02d}[-_/]01(?!\d)", u):
        return None
    for m in _URL_MONTH.finditer(u):
        if int(m.group(1)) == d.year and int(m.group(2)) == d.month:
            return "url_month"
    if d.month == 1:
        for m in _URL_YEAR.finditer(u):
            if int(m.group(1)) == d.year:
                return "url_year"
    return None


def consistent(kind: str, placeholder: date, found: date) -> bool:
    if kind == "url_year":
        return found.year == placeholder.year
    start = (placeholder.replace(day=1) - timedelta(days=1)).replace(day=1)  # month before
    nxt = (placeholder.replace(day=28) + timedelta(days=4)).replace(day=1)   # month after
    return start <= found < nxt


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--institution", action="append", help="eu_news_items institution or economy body_code")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    from sqlalchemy import text
    from core.database import SessionLocal
    from services.news.body_composer import compose_news_body
    from services.news.item_date import LazyBrowser, resolve_item_date

    only = {i.upper() for i in (args.institution or [])}
    db = SessionLocal()
    cands = []
    for r in db.execute(text(
            "SELECT 'eu_news_items' AS store, id::text AS id, institution AS body, news_date AS d, "
            "source_url AS url, title, summary, body_source AS kind FROM eu_news_items "
            "WHERE news_date IS NOT NULL AND extract(day FROM news_date) = 1")).mappings():
        cands.append(dict(r))
    for r in db.execute(text(
            "SELECT 'economy_items' AS store, id::text AS id, body_code AS body, document_date::date AS d, "
            "public_url AS url, title, summary, source_kind AS kind FROM economy_items "
            "WHERE item_type IN ('news', 'press_release') AND document_date IS NOT NULL "
            "AND extract(day FROM document_date) = 1")).mappings():
        cands.append(dict(r))
    db.close()  # page work below takes minutes; never hold a session across it
    cands = [c for c in cands if placeholder_kind(c["d"], c["url"])
             and (not only or c["body"].upper() in only)]
    if args.limit:
        cands = cands[: args.limit]
    print(f"[INFO] candidates: {len(cands)}")

    outcomes = collections.Counter()
    per_body = collections.defaultdict(collections.Counter)
    changes, reports = [], []
    browser = LazyBrowser()
    try:
        for c in cands:
            kind = placeholder_kind(c["d"], c["url"])
            dt, how = resolve_item_date(c["url"], fetcher=browser, render=True)
            found = dt.date() if dt else None
            time.sleep(0.3)
            if found is None:
                outcome = "no_carrier"
            elif found == c["d"]:
                outcome = "confirmed"
            elif not consistent(kind, c["d"], found):
                outcome = "inconsistent"
            else:
                outcome = "redated"
                changes.append({**c, "new": found, "how": how})
            outcomes[outcome] += 1
            per_body[(c["store"], c["body"])][outcome] += 1
            if outcome in ("no_carrier", "inconsistent"):
                reports.append((outcome, c["body"], str(c["d"]), str(found), how, c["url"].strip()))
    finally:
        browser.close()

    for (store, body), cnt in sorted(per_body.items()):
        print(f"[INFO]   {store:13s} {body:11s} {dict(cnt)}")
    print(f"[INFO] outcomes: {dict(outcomes)}")
    for ch in changes:
        print(f"[CHANGE] {ch['body']:11s} {ch['d']} -> {ch['new']} ({ch['how']}) {ch['url'].strip()}")
    for rep in reports:
        print(f"[WARN]   {rep[0]}: {rep[1]} stored {rep[2]} found {rep[3]} ({rep[4]}) {rep[5]}")
    if not args.apply:
        print("[INFO] dry run: nothing written. Re-run with --apply.")
        return 0
    if not changes:
        print("[OK] nothing to change")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    backup = _REPO_ROOT / "docs" / "backups" / f"news_placeholder_dates_{stamp}.json"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text(json.dumps([{k: str(v) for k, v in ch.items()} for ch in changes], indent=1))
    print(f"[OK] backup written: {backup}")

    db = SessionLocal()
    try:
        done = 0
        for ch in changes:
            composed = (ch["kind"] or "").startswith("composed")
            if ch["store"] == "eu_news_items":
                params = {"id": ch["id"], "d": ch["new"], "old": ch["d"]}
                sets = "news_date = :d"
                if composed:
                    params["t"], params["h"], params["s"] = compose_news_body(
                        ch["title"], ch["summary"], ch["body"], ch["new"], ch["url"])
                    sets += ", body_txt = :t, body_html = :h, body_source = :s"
                done += db.execute(text(f"UPDATE eu_news_items SET {sets} "
                                        "WHERE id = CAST(:id AS uuid) AND news_date = :old"), params).rowcount
            else:
                new_dt = datetime(ch["new"].year, ch["new"].month, ch["new"].day, tzinfo=timezone.utc)
                params = {"id": ch["id"], "d": new_dt, "old": ch["d"]}
                sets = "document_date = :d"
                if composed:
                    params["t"], params["h"], _ = compose_news_body(
                        ch["title"], ch["summary"], ch["body"], new_dt, ch["url"])
                    sets += ", body_txt = :t, body_html = :h"
                done += db.execute(text(f"UPDATE economy_items SET {sets} "
                                        "WHERE id = CAST(:id AS bigint) AND document_date::date = :old"),
                                   params).rowcount
        db.commit()
        print(f"[OK] redated {done} of {len(changes)}")
        return 0 if done == len(changes) else 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

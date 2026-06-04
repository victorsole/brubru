"""
Populate oj_entries from the EUR-Lex OJ daily views (MEUB "My OJ").

WAF-walled -> WafBrowserFetcher (Playwright). NO LLM / NO Anthropic.

Flow:
  * Discover the recent OJ publication dates from the direct-access hub (it lists
    the latest daily-view links — automatically skips weekends/holidays), OR take
    an explicit --date.
  * For each date x series (L, C): fetch the daily view, parse the acts, derive
    the CELEX (L-series), match it to a tracked legislative carriage / adopted
    text by CELEX, and upsert one oj_entries row per act.

Usage:
    python3.12 -m scripts.sync_oj --days 5 --apply        # latest 5 OJ days
    python3.12 -m scripts.sync_oj --date 2026-05-29 --apply
    python3.12 -m scripts.sync_oj --date 2026-05-29 --series L --apply
"""

import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text as sqla_text

from core.database import SessionLocal
from models.oj_entry import OjEntry
from services.scrapers.oj_scraper import daily_view_url, parse_daily_view
from services.scrapers.waf_browser_fetcher import WafBrowserFetcher

DIRECT_ACCESS = "https://eur-lex.europa.eu/oj/direct-access.html"
_DATE_RE = re.compile(r"ojDate=(\d{2})(\d{2})(\d{4})")


def discover_recent_dates(fetcher) -> list:
    """Latest OJ publication dates, newest first, from the direct-access hub."""
    res = fetcher.fetch(DIRECT_ACCESS, expand_accordions=False, strip_chrome=False)
    found = set()
    for d, m, y in _DATE_RE.findall(res.html or ""):
        try:
            found.add(date(int(y), int(m), int(d)))
        except ValueError:
            pass
    return sorted(found, reverse=True)


def _match_carriage(db, celex):
    if not celex:
        return None, None, None
    row = db.execute(sqla_text(
        "SELECT id, oeil_procedure_ref FROM legislative_carriages "
        "WHERE :c = ANY(celex_numbers) LIMIT 1"), {"c": celex}).first()
    cid = row[0] if row else None
    proc = row[1] if row else None
    ta = db.execute(sqla_text(
        "SELECT ta_reference FROM texts_adopted WHERE celex_number = :c LIMIT 1"),
        {"c": celex}).scalar()
    return cid, proc, ta


def _upsert(db, act, oj_date, apply):
    key = act.oj_id or f"{act.series}|{act.oj_number}"
    existing = db.query(OjEntry).filter(OjEntry.entry_key == key).first()
    if existing and not apply:
        return "skipped"
    cid, proc, ta = _match_carriage(db, act.celex)
    if not apply:
        return "matched" if cid else "added"
    e = existing or OjEntry(entry_key=key)
    if not existing:
        db.add(e)
    e.oj_date = oj_date
    e.series = act.series
    e.oj_number = act.oj_number
    e.oj_id = act.oj_id
    e.celex = act.celex
    e.title = act.title
    e.act_type = act.act_type
    e.category = act.category
    e.institution = act.institution
    e.eurlex_url = act.url
    e.change_kind = act.change_kind
    e.theme = act.theme
    e.carriage_id = cid
    e.matched_procedure_ref = proc
    e.matched_ta_reference = ta
    return ("updated" if existing else "added") + ("+linked" if cid else "")


async def _explain_pending(db, apply, only_dates=None):
    """Generate cached plain-language explanations (Mistral-only, no Anthropic)."""
    import asyncio
    from services.scrapers.oj_explainer import explain_batch
    q = db.query(OjEntry).filter(OjEntry.plain_explanation.is_(None))
    if only_dates:
        q = q.filter(OjEntry.oj_date.in_(only_dates))
    pending = q.all()
    if not pending:
        print("[EXPLAIN] nothing pending")
        return 0
    items = [{"key": e.entry_key, "title": e.title} for e in pending]
    result = await explain_batch(items)
    if not result:
        print(f"[EXPLAIN] 0 generated (Mistral unavailable?) — {len(pending)} still pending, no Anthropic used")
        return 0
    by_key = {e.entry_key: e for e in pending}
    n = 0
    for key, text in result.items():
        if key in by_key and text:
            by_key[key].plain_explanation = text
            n += 1
    if apply:
        db.commit()
    print(f"[EXPLAIN] generated {n}/{len(pending)} explanations via Mistral (cached)")
    return n


def run(dates, series_list, days, apply, explain=False):
    import asyncio
    db = SessionLocal()
    counts = {}
    linked = 0
    try:
        with WafBrowserFetcher(settle_ms=8000, networkidle_ms=20000) as fetcher:
            if not dates:
                dates = discover_recent_dates(fetcher)[:days]
                print(f"[INFO] discovered recent OJ dates: {[d.isoformat() for d in dates]}")
            for d in dates:
                for series in series_list:
                    url = daily_view_url(d, series)
                    res = fetcher.fetch(url, expand_accordions=True, strip_chrome=False)
                    acts = parse_daily_view(res.html or "", series)
                    for a in acts:
                        st = _upsert(db, a, d, apply)
                        counts[st] = counts.get(st, 0) + 1
                        if "linked" in st:
                            linked += 1
                    if apply:
                        db.commit()
                    print(f"  [{d} {series}] {len(acts)} acts")
        print(f"\n[{'APPLIED' if apply else 'DRY-RUN'}] "
              + ", ".join(f"{k}={v}" for k, v in counts.items()) + f", linked_to_MTF={linked}")

        if explain and apply:
            asyncio.run(_explain_pending(db, apply, only_dates=dates or None))
    finally:
        db.close()


def main():
    p = argparse.ArgumentParser(description="Sync the Official Journal daily views.")
    p.add_argument("--date", help="A single OJ date (YYYY-MM-DD).")
    p.add_argument("--days", type=int, default=5, help="How many recent OJ days (when --date omitted).")
    p.add_argument("--series", default="L,C", help="Comma list of series: L,C")
    p.add_argument("--apply", action="store_true", help="Persist (default dry-run).")
    p.add_argument("--explain", action="store_true",
                   help="Also generate cached plain-language explanations (Mistral only, no Anthropic).")
    args = p.parse_args()

    dates = []
    if args.date:
        dates = [datetime.strptime(args.date, "%Y-%m-%d").date()]
    series_list = [s.strip().upper() for s in args.series.split(",") if s.strip() in ("L", "C", "l", "c")]
    run(dates, series_list, args.days, args.apply, explain=args.explain)


if __name__ == "__main__":
    main()

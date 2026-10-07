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
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text as sqla_text

from core.database import SessionLocal
from models.oj_entry import OjEntry
from services.scrapers.oj_scraper import (
    OjAct, category_for, derive_act_type, derive_change_kind, derive_institution, derive_theme,
)

_TYPE_BY_DESCRIPTOR = {"R": "Regulation", "L": "Directive", "D": "Decision"}


def acts_from_cellar(d: date, series: str) -> list:
    """Every act the OJ published on `d` in `series`, as OjAct rows."""
    import asyncio
    import re as _re
    from services.api_clients.cellar_sparql_client import CellarSPARQLClient, group_oj_acts

    async def _rows():
        async with CellarSPARQLClient() as c:
            return await c.oj_acts_published_on(d, series)

    out = []
    for a in group_oj_acts(asyncio.run(_rows()), series):
        title, celex, en = a["title"] or "", a["celex"], a["language"] == "en"
        corrigendum = bool(celex and _re.search(r"R\(\d+\)$", celex))
        if en:
            act_type, kind = derive_act_type(title), derive_change_kind(title)
        else:
            # The English keyword rules cannot read another language: take the act type
            # from the CELEX descriptor Cellar gave, and nothing else.
            act_type = _TYPE_BY_DESCRIPTOR.get(celex[5] if celex and len(celex) > 5 else "", "Other")
            kind = "corrects" if corrigendum else "new"
        out.append(OjAct(
            oj_number=a["oj_reference"] or f"{series}/{a['year']}/{a['number']}",
            oj_id=a["oj_id"], title=title, url=a["url"], act_type=act_type,
            category=category_for(act_type, series),
            institution=derive_institution(title) if en else "Other EU body",
            celex=celex, series=series, change_kind=kind,
            theme=derive_theme(title) if en else "Other", language=a["language"],
        ))
    return out


def recent_oj_dates(days: int) -> list:
    """The latest `days` OJ publication dates, newest first (weekends and holidays skipped)."""
    import asyncio
    from datetime import timedelta
    from services.api_clients.cellar_sparql_client import CellarSPARQLClient

    async def _dates():
        async with CellarSPARQLClient() as c:
            today = date.today()
            return await c.oj_publication_dates(today - timedelta(days=max(14, days * 3)), today)

    return asyncio.run(_dates())[:days]


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
    e.language = act.language
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
    print(f"[EXPLAIN] generated {n}/{len(pending)} explanations via the cheap provider chain (see [OJ-EXPLAIN] log)")
    return n


def run(dates, series_list, days, apply, explain=False):
    import asyncio
    db = SessionLocal()
    counts = {}
    linked = 0
    try:
        if not dates:
            dates = recent_oj_dates(days)
            print(f"[INFO] recent OJ dates: {[d.isoformat() for d in dates]}")
        for d in dates:
            for series in series_list:
                acts = acts_from_cellar(d, series)
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

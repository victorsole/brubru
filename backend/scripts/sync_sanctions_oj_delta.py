"""Daily: read sanctions listings from the OJ for the gap the Commission list leaves.

The Commission's consolidated financial sanctions list (eu_sanctions) can lag the Official
Journal by weeks: on 1 October 2026 it was last published on 22 September and carried no
act newer than 23 July. This job:

  1. reads the newest legal act the Commission list carries (eu_sanctions);
  2. lists every restrictive-measures REGULATION in the OJ after that date (Cellar SPARQL);
  3. parses each act's annex into entries (services/scrapers/oj_sanctions_delta.py) and
     upserts them into eu_sanctions_oj_delta;
  4. records the gap in sync_runs as `sanctions_oj_delta`: degraded while the Commission
     list is behind the OJ, naming the gap, so the health endpoint shows it.

Three states, never two: an act we fetched and parsed, an act we could not fetch, and an
untitled act we could not classify yet (Cellar titles lag 1-2 working days) are reported
separately.

Run:
    cd backend && python3.12 scripts/sync_sanctions_oj_delta.py            # dry run
    cd backend && python3.12 scripts/sync_sanctions_oj_delta.py --apply --record
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402
from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from services.api_clients.cellar_sparql_client import CellarSPARQLClient  # noqa: E402
from services.scrapers.oj_sanctions_delta import parse_act  # noqa: E402

_RM = re.compile(r"restrictive measures", re.I)
_REG = re.compile(r"^3\d{4}R\d{4}$")          # regulations only; corrigenda excluded


def _commission_cutoff(db) -> date | None:
    return db.execute(text(
        "SELECT max(legal_basis_publication_date) FROM eu_sanctions")).scalar()


async def _acts_since(cutoff: date) -> list[dict]:
    async with CellarSPARQLClient() as client:
        return await client.discover_by_date_range(
            cutoff, date.today(), sectors=["3"], limit=3000)


def _fetch(celex: str) -> str | None:
    r = requests.get(f"https://publications.europa.eu/resource/celex/{celex}",
                     headers={"Accept": "application/xhtml+xml", "Accept-Language": "en"},
                     timeout=60)
    if r.status_code != 200 or b"<html" not in r.content[:2000].lower():
        return None
    return r.text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="write rows (default: dry run)")
    ap.add_argument("--record", action="store_true", help="write one sync_runs row")
    a = ap.parse_args()

    db = SessionLocal()
    try:
        cutoff = _commission_cutoff(db)
        if not cutoff:
            print("[ERROR] eu_sanctions is empty: no Commission cutoff to measure the gap from")
            return 1
        rows = asyncio.run(_acts_since(cutoff))
        untitled = [r for r in rows if _REG.match(r.get("celex") or "") and not r.get("title")]
        acts = [r for r in rows if _REG.match(r.get("celex") or "")
                and _RM.search(r.get("title") or "") and (r.get("date") or "") > cutoff.isoformat()]
        acts.sort(key=lambda r: (r.get("date") or "", r["celex"]))
        print(f"Commission list newest act: {cutoff}. Restrictive-measures regulations after it: "
              f"{len(acts)}; untitled regulations not yet classifiable: {len(untitled)}")

        fetched = failed = 0
        new_rows = touched = 0
        listing_acts = 0
        for act in acts:
            celex = act["celex"]
            html = _fetch(celex)
            if html is None:
                failed += 1
                print(f"  [FETCH-FAIL] {celex}")
                continue
            fetched += 1
            parsed = parse_act(celex, html, act.get("title") or "")
            if parsed.entries:
                listing_acts += 1
            print(f"  {act.get('date')} {celex}: {len(parsed.entries)} entries "
                  f"{sorted({e.action for e in parsed.entries})} {parsed.notes or ''}")
            if not a.apply:
                continue
            keys = []
            for e in parsed.entries:
                key = f"{celex}#{e.block}#{e.position}"
                keys.append(key)
                res = db.execute(text("""
                    INSERT INTO eu_sanctions_oj_delta
                      (entry_key, celex, act_title, document_date, base_regulation, annex, action,
                       heading, subject_type, entry_number, name, identifying_info, reasons,
                       date_of_listing, public_url, body_txt, body_html, body_source)
                    VALUES
                      (:k, :celex, :title, :ddate, :base, :annex, :action, :heading, :st, :no,
                       :name, :ident, :reasons, :dol, :url, :body, :bhtml, 'cellar:xhtml')
                    ON CONFLICT (entry_key) DO UPDATE SET
                      act_title = EXCLUDED.act_title, base_regulation = EXCLUDED.base_regulation,
                      annex = EXCLUDED.annex, action = EXCLUDED.action, heading = EXCLUDED.heading,
                      subject_type = EXCLUDED.subject_type, entry_number = EXCLUDED.entry_number,
                      name = EXCLUDED.name, identifying_info = EXCLUDED.identifying_info,
                      reasons = EXCLUDED.reasons, date_of_listing = EXCLUDED.date_of_listing,
                      public_url = EXCLUDED.public_url,
                      body_txt = CASE WHEN length(EXCLUDED.body_txt) >= length(eu_sanctions_oj_delta.body_txt)
                                      THEN EXCLUDED.body_txt ELSE eu_sanctions_oj_delta.body_txt END,
                      body_html = EXCLUDED.body_html, scraped_at = now()
                    RETURNING (xmax = 0) AS inserted
                """), {
                    "k": key, "celex": celex, "title": act.get("title"),
                    "ddate": act.get("date"), "base": e.base_regulation, "annex": e.annex,
                    "action": e.action, "heading": e.heading, "st": e.subject_type,
                    "no": e.entry_number, "name": e.name or None, "ident": e.identifying_info,
                    "reasons": e.reasons, "dol": e.date_of_listing,
                    "url": f"http://data.europa.eu/eli/reg/{celex[1:5]}/{int(celex[6:])}/oj"
                           if "Implementing" not in (act.get("title") or "")
                           else f"http://data.europa.eu/eli/reg_impl/{celex[1:5]}/{int(celex[6:])}/oj",
                    "body": e.body_txt, "bhtml": e.body_html,
                }).scalar()
                new_rows += 1 if res else 0
                touched += 1
            # A re-parse that yields fewer entries must not leave stale ones behind.
            if keys:
                db.execute(text("DELETE FROM eu_sanctions_oj_delta WHERE celex = :c "
                                "AND NOT (entry_key = ANY(:keys))"), {"c": celex, "keys": keys})
            db.commit()

        newest_oj = acts[-1]["date"] if acts else None
        gap = bool(acts) and (date.fromisoformat(newest_oj) - cutoff).days > 7
        msg = (f"Commission consolidated list newest act {cutoff}; OJ newest restrictive-measures "
               f"regulation {newest_oj or 'none'}; {len(acts)} regulations after the cutoff, "
               f"{fetched} fetched, {failed} fetch failures, {listing_acts} with listing changes, "
               f"{touched} entries held from the OJ ({new_rows} new); "
               f"{len(untitled)} untitled regulations not yet classifiable")
        print(("[GAP] " if gap else "[OK] ") + msg)
        if a.record:
            from services.sync.freshness import record_run
            status = "failed" if (acts and fetched == 0) else ("degraded" if (gap or failed) else "success")
            record_run(db, source_key="sanctions_oj_delta", tier="daily", status=status,
                       items_added=new_rows, error=msg if status != "success" else None)
        return 1 if (acts and fetched == 0) else 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

"""
Backfill ``eu_solidarity_fund`` from the DG REGIO Cohesion Open Data Platform
(Socrata 7a49-av34, "EU Solidarity Fund (cases 2002 to 2021)"). One row per
disaster case. Amounts in the source are EUR million, comma-formatted. Backs
/api/v2/funding/eusf.

Upsert on case_key (CCI number + disaster name, migration 284), so a case keeps its id
and created_at across refreshes and updated_at moves only when its content changes.
Until 9 Oct 2026 this deleted the table and re-inserted every case, so the "stable" id
the endpoint documents changed every week. Cases the source no longer lists are
removed, but never on an empty fetch and never more than 10% of the table at once.

Run:
    python3.12 backend/scripts/backfill_eusf.py            # dry-run
    python3.12 backend/scripts/backfill_eusf.py --apply
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from urllib import request as ureq

from psycopg2.extras import Json

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _specialised_helpers import ChunkedDb  # noqa: E402

DATASET = "7a49-av34"
RESOURCE_URL = f"https://cohesiondata.ec.europa.eu/resource/{DATASET}.json"
PUBLIC_URL = "https://ec.europa.eu/regional_policy/funding/solidarity-fund_en"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")


def _num(v):
    """Parse '9,100.00' / '18.70%' / '444' -> float; None on blanks."""
    if v is None:
        return None
    s = str(v).replace(",", "").replace("%", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _int(v):
    n = _num(v)
    return int(n) if n is not None else None


def _date(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "")).date()
    except ValueError:
        return None


def _meur(n):
    return f"EUR {n:,.0f} million" if n else "n/a"


def compose_body(r: dict, vals: dict) -> tuple[str, str]:
    name = (r.get("name_of_disaster") or "").strip()
    cc = r.get("applicant_country") or "?"
    yr = r.get("year_of_occurance") or ""
    dtype = r.get("disaster_type") or ""
    status = r.get("status") or ""
    cat = r.get("major_regional_neighbouring") or ""
    txt = (
        f"EU Solidarity Fund — {name} ({cc}, {yr}). "
        f"Disaster type: {dtype}. Category: {cat}. Status: {status}. "
        f"Accepted total direct damage: {_meur(vals['damage'])}. "
        f"EUSF grant paid: {_meur(vals['paid'])}."
    )
    html = (
        f"<article><h3>EU Solidarity Fund &mdash; {name} ({cc}, {yr})</h3>"
        f"<p>Disaster type: {dtype}. Category: {cat}. Status: {status}.</p>"
        f"<p>Accepted total direct damage: <strong>{_meur(vals['damage'])}</strong>. "
        f"EUSF grant paid: <strong>{_meur(vals['paid'])}</strong>.</p></article>"
    )
    return txt, html


def fetch() -> list[dict]:
    rows: list[dict] = []
    offset, page = 0, 1000
    while True:
        url = f"{RESOURCE_URL}?$limit={page}&$offset={offset}&$order=year_of_occurance"
        req = ureq.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with ureq.urlopen(req, timeout=120) as r:
            payload = json.loads(r.read())
        if not payload:
            break
        rows.extend(payload)
        if len(payload) < page:
            break
        offset += page
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    rows = fetch()
    total_paid = sum((_num(r.get("paid")) or 0) for r in rows)
    print(f"[EUSF] fetched {len(rows)} disaster cases | total EUSF paid EUR {total_paid:,.0f}m")
    if not args.apply:
        print("[EUSF] [DRY-RUN] use --apply"); return
    if not rows:
        print("[EUSF] [ERROR] the source returned no cases: a failed fetch, not an empty fund")
        sys.exit(1)
    db = ChunkedDb()
    inserted = updated = unchanged = 0
    keys = set()
    try:
        for r in rows:
            vals = {
                "damage": _num(r.get("total_direct_damage_accepted")),
                "emerg": _num(r.get("cost_of_eligible_emergency")),
                "pct": _num(r.get("eligible_cost_total_damage")),
                "paid": _num(r.get("paid")),
            }
            body_txt, body_html = compose_body(r, vals)
            db.execute(
                """
                INSERT INTO eu_solidarity_fund
                  (year_of_occurrence, cci_number, applicant_country, name_of_disaster,
                   disaster_type, status, category, first_damage_date, date_of_initial_application,
                   total_direct_damage_meur, eligible_emergency_cost_meur, damage_pct, eusf_grant_paid_meur,
                   public_url, body_txt, body_html, body_source, document_date, raw)
                VALUES
                  (%(yr)s,%(cci)s,%(cc)s,%(name)s,%(dtype)s,%(status)s,%(cat)s,%(fdd)s,%(doia)s,
                   %(damage)s,%(emerg)s,%(pct)s,%(paid)s,
                   %(url)s,%(bt)s,%(bh)s,'composed',%(docdate)s,%(raw)s)
                ON CONFLICT (case_key) DO UPDATE SET
                  year_of_occurrence = EXCLUDED.year_of_occurrence, applicant_country = EXCLUDED.applicant_country,
                  disaster_type = EXCLUDED.disaster_type, status = EXCLUDED.status, category = EXCLUDED.category,
                  first_damage_date = EXCLUDED.first_damage_date,
                  date_of_initial_application = EXCLUDED.date_of_initial_application,
                  total_direct_damage_meur = EXCLUDED.total_direct_damage_meur,
                  eligible_emergency_cost_meur = EXCLUDED.eligible_emergency_cost_meur,
                  damage_pct = EXCLUDED.damage_pct, eusf_grant_paid_meur = EXCLUDED.eusf_grant_paid_meur,
                  public_url = EXCLUDED.public_url, body_txt = EXCLUDED.body_txt, body_html = EXCLUDED.body_html,
                  document_date = EXCLUDED.document_date, raw = EXCLUDED.raw,
                  updated_at = now(), fetched_at = now()
                WHERE (eu_solidarity_fund.raw, eu_solidarity_fund.body_txt, eu_solidarity_fund.public_url)
                      IS DISTINCT FROM (EXCLUDED.raw, EXCLUDED.body_txt, EXCLUDED.public_url)
                RETURNING (xmax = 0) AS inserted
                """,
                {
                    "yr": _int(r.get("year_of_occurance")), "cci": r.get("cci_number"),
                    "cc": r.get("applicant_country"), "name": r.get("name_of_disaster"),
                    "dtype": r.get("disaster_type"), "status": r.get("status"),
                    "cat": r.get("major_regional_neighbouring"),
                    "fdd": _date(r.get("first_damage_date")),
                    "doia": r.get("date_of_initial_application"),
                    "damage": vals["damage"], "emerg": vals["emerg"], "pct": vals["pct"], "paid": vals["paid"],
                    "url": PUBLIC_URL, "bt": body_txt, "bh": body_html,
                    "docdate": _date(r.get("first_damage_date")), "raw": Json(r),
                },
            )
            got = db.cur.fetchone()
            if got is None:
                unchanged += 1          # held, and nothing in it changed: id, dates untouched
            elif got[0]:
                inserted += 1
            else:
                updated += 1
            keys.add(f"{r.get('cci_number') or ''}|{r.get('name_of_disaster') or ''}")
        db.execute("SELECT case_key FROM eu_solidarity_fund")
        gone = [k for (k,) in db.cur.fetchall() if k not in keys]
        db.execute("SELECT count(*) FROM eu_solidarity_fund")
        held = db.cur.fetchone()[0]
        if gone and len(gone) > 0.1 * held:
            db.conn.rollback()
            print(f"[EUSF] [ERROR] {len(gone)} of {held} cases missing from the source; refusing to delete")
            sys.exit(1)
        for k in gone:
            db.execute("DELETE FROM eu_solidarity_fund WHERE case_key = %(k)s", {"k": k})
        db.commit()
        print(f"[EUSF] [OK] {len(rows)} cases: inserted={inserted} updated={updated} "
              f"unchanged={unchanged} removed={len(gone)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

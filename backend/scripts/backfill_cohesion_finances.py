"""
Backfill ``eu_cohesion_finances`` from the DG REGIO Cohesion Open Data Platform
(Socrata at cohesiondata.ec.europa.eu), dataset 9qee-iv7c
"2021-2027 Financial Plan details by year (All CPR funds)".

One row per programme (cci) x financial-allocation-category x fund. Full
refresh per fund: DELETE WHERE fund = X, then insert. Backs /api/v2/funding/<fund>.

Run:
    python3.12 backend/scripts/backfill_cohesion_finances.py --fund ERDF            # dry-run
    python3.12 backend/scripts/backfill_cohesion_finances.py --fund ERDF --apply
    python3.12 backend/scripts/backfill_cohesion_finances.py --all --apply          # every fund in the dataset
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from urllib import parse as uparse
from urllib import request as ureq

from psycopg2.extras import Json

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _specialised_helpers import ChunkedDb  # noqa: E402

DATASET = "9qee-iv7c"
RESOURCE_URL = f"https://cohesiondata.ec.europa.eu/resource/{DATASET}.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# Socrata `fund` codes present in the dataset (verified 14 June 2026).
FUND_CODES = ["ERDF", "ESF", "CF", "JTF", "INTERREG", "EMFAF", "AMIF", "BMVI", "ISF"]
# Funds that actually have a live /api/v2/funding/<fund> endpoint (BMVI skipped).
BUILT_FUNDS = ["ERDF", "ESF", "CF", "JTF", "INTERREG", "EMFAF", "AMIF", "ISF"]

# Human names + Cohesion Open Data Platform page slug (verified 200) per fund code.
FUND_NAMES = {
    "ERDF": "European Regional Development Fund", "ESF": "European Social Fund Plus",
    "CF": "Cohesion Fund", "JTF": "Just Transition Fund", "INTERREG": "Interreg",
    "EMFAF": "European Maritime, Fisheries and Aquaculture Fund",
    "AMIF": "Asylum, Migration and Integration Fund",
    "BMVI": "Border Management and Visa Instrument", "ISF": "Internal Security Fund",
}
FUND_PAGE = {
    "ERDF": "erdf", "ESF": "esf_plus", "CF": "cohesion_fund", "JTF": "jtf",
    "INTERREG": "interreg", "EMFAF": "emfaf", "AMIF": "amif", "BMVI": "bmvi", "ISF": "isf",
}


def _eur(v):
    n = _num(v)
    return f"EUR {n:,.0f}" if n else "n/a"


def _public_url(fund: str) -> str:
    slug = FUND_PAGE.get(fund)
    return (f"https://cohesiondata.ec.europa.eu/funds/{slug}/21-27" if slug
            else f"https://cohesiondata.ec.europa.eu/d/{DATASET}")


def compose_body(fund: str, row: dict) -> tuple[str, str]:
    """Human-readable body for one financial-plan row (plain text + HTML)."""
    name = FUND_NAMES.get(fund, fund)
    cci_title = (row.get("cci_title") or "").strip()
    ms = row.get("ms") or "?"
    cat = row.get("financial_allocation_category") or ""
    years = " · ".join(f"{y[1:]}: {_eur(row.get(y))}" for y in
                       ("y2021", "y2022", "y2023", "y2024", "y2025", "y2026", "y2027"))
    txt = (
        f"{name} ({fund}) — {cci_title} [{ms}]. "
        f"{cat + ' region. ' if cat else ''}"
        f"Total EU allocation 2021-2027: {_eur(row.get('total'))}. "
        f"Annual profile — {years}. "
        f"Programme {row.get('cci')} (version {row.get('ver')}), "
        f"status: {row.get('status')}"
        f"{' on ' + str(row.get('status_date'))[:10] if row.get('status_date') else ''}. "
        f"Lead DG {row.get('dg')}."
    )
    html = (
        f"<article><h3>{name} ({fund}) &mdash; {cci_title} [{ms}]</h3>"
        f"<p>{cat + ' region. ' if cat else ''}"
        f"Total EU allocation 2021-2027: <strong>{_eur(row.get('total'))}</strong>.</p>"
        f"<p>Annual profile: {years}.</p>"
        f"<p>Programme {row.get('cci')} (version {row.get('ver')}), status: "
        f"{row.get('status')}"
        f"{' on ' + str(row.get('status_date'))[:10] if row.get('status_date') else ''}. "
        f"Lead DG {row.get('dg')}.</p></article>"
    )
    return txt, html

NUMERIC_COLS = [
    "y2021", "y2022", "y2023", "y2024", "y2025", "y2026", "y2027",
    "total_non_flexible_amount", "total_flexible_amount", "total",
    "share_of_fa_in_total",
]


def _num(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _date(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "")).date()
    except ValueError:
        return None


# Interreg is barely present in the national-plan dataset (9qee-iv7c). Its proper
# source is the dedicated programme-level dataset njgb-mwca (programme x strand x
# year x eu_allocation), which we aggregate into the standard row shape.
INTERREG_DATASET = "njgb-mwca"
INTERREG_URL = f"https://cohesiondata.ec.europa.eu/resource/{INTERREG_DATASET}.json"


def fetch_fund(fund: str) -> list[dict]:
    """Page through every row for one fund (9qee-iv7c)."""
    rows: list[dict] = []
    offset = 0
    page_size = 1000
    while True:
        params = {
            "$where": f"fund='{fund}'",
            "$limit": page_size,
            "$offset": offset,
            "$order": "cci",
        }
        url = f"{RESOURCE_URL}?{uparse.urlencode(params)}"
        req = ureq.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with ureq.urlopen(req, timeout=120) as r:
            payload = json.loads(r.read())
        if not payload:
            break
        rows.extend(payload)
        if len(payload) < page_size:
            break
        offset += page_size
    return rows


def fetch_interreg() -> list[dict]:
    """Fetch njgb-mwca and aggregate to programme x strand, pivoting year ->
    y20xx and summing eu_allocation into total. Returns rows shaped like
    9qee-iv7c so the standard upsert + body composition work unchanged."""
    raw: list[dict] = []
    offset, page_size = 0, 1000
    while True:
        params = {"$limit": page_size, "$offset": offset, "$order": "cci"}
        url = f"{INTERREG_URL}?{uparse.urlencode(params)}"
        req = ureq.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with ureq.urlopen(req, timeout=120) as r:
            payload = json.loads(r.read())
        if not payload:
            break
        raw.extend(payload)
        if len(payload) < page_size:
            break
        offset += page_size

    agg: dict[tuple, dict] = {}
    for r in raw:
        cci = r.get("cci")
        strand = r.get("strand")
        key = (cci, strand)
        rec = agg.setdefault(key, {
            "ms": None, "cci": cci, "cci_title": r.get("programme_name") or r.get("programme_short_name"),
            "dg": "REGIO", "status": None, "status_date": None, "ver": None,
            "financial_allocation_category": strand,
            "y2021": 0.0, "y2022": 0.0, "y2023": 0.0, "y2024": 0.0,
            "y2025": 0.0, "y2026": 0.0, "y2027": 0.0,
            "total_non_flexible_amount": None, "total_flexible_amount": None,
            "total": 0.0, "share_of_fa_in_total": None,
        })
        amt = _num(r.get("eu_allocation")) or 0.0
        yr = str(r.get("year") or "").strip()
        col = f"y{yr}"
        if col in rec:
            rec[col] += amt
        rec["total"] += amt
    return list(agg.values())


def upsert_fund(db: ChunkedDb, fund: str, rows: list[dict], source_dataset: str = DATASET) -> None:
    # One fund's finances come from exactly one dataset, so delete by fund.
    db.execute("DELETE FROM eu_cohesion_finances WHERE fund = %s", (fund,))
    public_url = _public_url(fund)
    for row in rows:
        vals = {c: _num(row.get(c)) for c in NUMERIC_COLS}
        body_txt, body_html = compose_body(fund, row)
        db.execute(
            """
            INSERT INTO eu_cohesion_finances
              (fund, ms, cci, cci_title, dg, status, status_date, ver,
               financial_allocation_category,
               y2021, y2022, y2023, y2024, y2025, y2026, y2027,
               total_non_flexible_amount, total_flexible_amount, total,
               share_of_fa_in_total, source_dataset, raw,
               public_url, body_txt, body_html, body_source, document_date)
            VALUES
              (%(fund)s, %(ms)s, %(cci)s, %(cci_title)s, %(dg)s, %(status)s,
               %(status_date)s, %(ver)s, %(fac)s,
               %(y2021)s, %(y2022)s, %(y2023)s, %(y2024)s, %(y2025)s, %(y2026)s, %(y2027)s,
               %(tnf)s, %(tf)s, %(total)s, %(share)s, %(ds)s, %(raw)s,
               %(public_url)s, %(body_txt)s, %(body_html)s, 'composed', %(status_date)s)
            """,
            {
                "fund": fund,
                "ms": row.get("ms"),
                "cci": row.get("cci"),
                "cci_title": row.get("cci_title"),
                "dg": row.get("dg"),
                "status": row.get("status"),
                "status_date": _date(row.get("status_date")),
                "ver": row.get("ver"),
                "fac": row.get("financial_allocation_category"),
                "y2021": vals["y2021"], "y2022": vals["y2022"], "y2023": vals["y2023"],
                "y2024": vals["y2024"], "y2025": vals["y2025"], "y2026": vals["y2026"],
                "y2027": vals["y2027"],
                "tnf": vals["total_non_flexible_amount"], "tf": vals["total_flexible_amount"],
                "total": vals["total"], "share": vals["share_of_fa_in_total"],
                "ds": source_dataset, "raw": Json(row),
                "public_url": public_url, "body_txt": body_txt, "body_html": body_html,
            },
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fund", default="ERDF", help="Socrata fund code (ERDF, ESF, CF, JTF, INTERREG, EMFAF, AMIF, BMVI, ISF)")
    ap.add_argument("--all", action="store_true", help="backfill every fund in the dataset")
    ap.add_argument("--apply", action="store_true", help="write to DB (default: dry-run)")
    args = ap.parse_args()

    funds = BUILT_FUNDS if args.all else [args.fund.upper()]
    db = ChunkedDb() if args.apply else None
    try:
        for fund in funds:
            if fund == "INTERREG":
                rows, source = fetch_interreg(), INTERREG_DATASET
            else:
                rows, source = fetch_fund(fund), DATASET
            total_eur = sum((_num(r.get("total")) or 0) for r in rows)
            print(f"[{fund}] fetched {len(rows)} rows from {source} | total EUR {total_eur/1e9:.1f}bn")
            if args.apply:
                upsert_fund(db, fund, rows, source)
                db.commit()
                print(f"[{fund}] [OK] wrote {len(rows)} rows")
            else:
                print(f"[{fund}] [DRY-RUN] would write {len(rows)} rows (use --apply)")
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    main()

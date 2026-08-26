"""
Backfill ``eu_cohesion_outcomes`` from the DG REGIO Cohesion Open Data Platform
(Socrata at cohesiondata.ec.europa.eu), dataset xi3a-zddk
"2021-2027 Achievement Details (multi-funds) timeseries".

One row per programme (cci) x indicator x category-of-region. Only the latest
TOD cycle (is_latest_tod_cycle=true) is ingested. Full refresh per fund. Bulk
insert (execute_values) — the per-fund volume is large (ESF+ ~89k rows).
Backs /api/v2/funding/<fund>/outcomes.

Run:
    python3.12 backend/scripts/backfill_cohesion_outcomes.py --fund "ESF+"            # dry-run
    python3.12 backend/scripts/backfill_cohesion_outcomes.py --fund "ESF+" --apply
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib import parse as uparse
from urllib import request as ureq

from psycopg2.extras import Json, execute_values

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _specialised_helpers import ChunkedDb  # noqa: E402

DATASET = "xi3a-zddk"
RESOURCE_URL = f"https://cohesiondata.ec.europa.eu/resource/{DATASET}.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")

NUMERIC_COLS = [
    "baseline_value", "milestone_value_2024", "target_value_2029",
    "decided_value", "implemented_value",
]

FUND_NAMES = {
    "ESF+": "European Social Fund Plus", "ERDF": "European Regional Development Fund",
    "CF": "Cohesion Fund", "JTF": "Just Transition Fund", "Interreg Funds": "Interreg",
    "EMFAF": "European Maritime, Fisheries and Aquaculture Fund",
    "AMIF": "Asylum, Migration and Integration Fund",
    "BMVI": "Border Management and Visa Instrument", "ISF": "Internal Security Fund",
}
FUND_PAGE = {
    "ESF+": "esf_plus", "ERDF": "erdf", "CF": "cohesion_fund", "JTF": "jtf",
    "Interreg Funds": "interreg", "EMFAF": "emfaf", "AMIF": "amif", "BMVI": "bmvi", "ISF": "isf",
}


def _date(v):
    if not v:
        return None
    try:
        from datetime import datetime as _dt
        return _dt.fromisoformat(str(v).replace("Z", "")).date()
    except ValueError:
        return None


def _fmt(v):
    n = _num(v)
    if n is None:
        return "n/a"
    return f"{n:,.0f}" if n == int(n) else f"{n:,.2f}"


def _public_url(fund: str) -> str:
    slug = FUND_PAGE.get(fund)
    return (f"https://cohesiondata.ec.europa.eu/funds/{slug}/21-27" if slug
            else f"https://cohesiondata.ec.europa.eu/d/{DATASET}")


def compose_body(fund: str, row: dict) -> tuple[str, str]:
    """Human-readable body for one achievement-indicator row (text + HTML)."""
    name = FUND_NAMES.get(fund, fund)
    ind = (row.get("indicator_long_name") or row.get("indicator_short_name") or "").strip()
    unit = row.get("measurement_unit") or ""
    ms = row.get("ms") or "?"
    prog = (row.get("programme_short_title") or "").strip()
    cat = row.get("category_of_region") or ""
    po = row.get("policy_objective_name") or ""
    itype = row.get("indicator_type_output_result") or ""
    txt = (
        f"{name} ({fund}) — {ind}{f' ({unit})' if unit else ''}. "
        f"Programme {prog} [{ms}]{f', {cat}' if cat else ''}. "
        f"{f'Policy objective: {po}. ' if po else ''}"
        f"Indicator type {itype}, code {row.get('ind_code')}. "
        f"Baseline {_fmt(row.get('baseline_value'))}, "
        f"2024 milestone {_fmt(row.get('milestone_value_2024'))}, "
        f"2029 target {_fmt(row.get('target_value_2029'))}. "
        f"Decided {_fmt(row.get('decided_value'))}, "
        f"implemented {_fmt(row.get('implemented_value'))}."
    )
    html = (
        f"<article><h3>{name} ({fund}) &mdash; {ind}</h3>"
        f"<p>Programme {prog} [{ms}]{f', {cat}' if cat else ''}. "
        f"{f'Policy objective: {po}. ' if po else ''}"
        f"Indicator type {itype}, unit {unit or 'n/a'}.</p>"
        f"<p>Baseline <strong>{_fmt(row.get('baseline_value'))}</strong>, "
        f"2024 milestone <strong>{_fmt(row.get('milestone_value_2024'))}</strong>, "
        f"2029 target <strong>{_fmt(row.get('target_value_2029'))}</strong>. "
        f"Decided {_fmt(row.get('decided_value'))}, "
        f"implemented <strong>{_fmt(row.get('implemented_value'))}</strong>.</p></article>"
    )
    return txt, html

INSERT_COLS = [
    "fund", "fund_family", "ms", "ms_name", "cci", "programme_short_title",
    "programme_status", "policy_objective_code", "policy_objective_name",
    "specific_objective_code", "specific_objective_name", "category_of_region",
    "indicator_type_output_result", "common_indicators_y_n", "ind_code",
    "indicator_short_name", "indicator_long_name", "measurement_unit",
    "baseline_value", "milestone_value_2024", "target_value_2029",
    "decided_value", "implemented_value", "tod_cycle", "source_dataset", "raw",
    "public_url", "body_txt", "body_html", "body_source", "document_date",
]


def _num(v):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _bool(v):
    if isinstance(v, bool):
        return v
    if v in (None, ""):
        return None
    return str(v).strip().lower() in ("y", "yes", "true", "1")


def fetch_fund(fund: str) -> list[dict]:
    rows: list[dict] = []
    offset, page_size = 0, 5000
    where = f"fund='{fund}' AND is_latest_tod_cycle=true"
    while True:
        params = {"$where": where, "$limit": page_size, "$offset": offset, "$order": ":id"}
        url = f"{RESOURCE_URL}?{uparse.urlencode(params)}"
        req = ureq.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with ureq.urlopen(req, timeout=180) as r:
            payload = json.loads(r.read())
        if not payload:
            break
        rows.extend(payload)
        sys.stderr.write(f"\r  fetched {len(rows)} rows...")
        sys.stderr.flush()
        if len(payload) < page_size:
            break
        offset += page_size
    sys.stderr.write("\n")
    return rows


def _row_tuple(fund: str, row: dict, public_url: str) -> tuple:
    body_txt, body_html = compose_body(fund, row)
    return (
        fund, row.get("fund_family"), row.get("ms"), row.get("ms_name"),
        row.get("cci"), row.get("programme_short_title"), row.get("programme_status"),
        row.get("policy_objective_code"), row.get("policy_objective_name"),
        row.get("specific_objective_code"), row.get("specific_objective_name"),
        row.get("category_of_region"), row.get("indicator_type_output_result"),
        _bool(row.get("common_indicators_y_n")), row.get("ind_code"),
        row.get("indicator_short_name"), row.get("indicator_long_name"),
        row.get("measurement_unit"),
        _num(row.get("baseline_value")), _num(row.get("milestone_value_2024")),
        _num(row.get("target_value_2029")), _num(row.get("decided_value")),
        _num(row.get("implemented_value")), row.get("tod_cycle"), DATASET, Json(row),
        public_url, body_txt, body_html, "composed", _date(row.get("programme_adoption_date")),
    )


def upsert_fund(db: ChunkedDb, fund: str, rows: list[dict]) -> None:
    db.execute("DELETE FROM eu_cohesion_outcomes WHERE fund = %s AND source_dataset = %s",
               (fund, DATASET))
    cols_sql = ", ".join(INSERT_COLS)
    public_url = _public_url(fund)
    tuples = [_row_tuple(fund, r, public_url) for r in rows]
    execute_values(
        db.cur,
        f"INSERT INTO eu_cohesion_outcomes ({cols_sql}) VALUES %s",
        tuples, page_size=1000,
    )


# Fund codes with a live /api/v2/funding/<fund>/outcomes endpoint (BMVI skipped).
BUILT_FUNDS = ["ERDF", "ESF+", "CF", "JTF", "Interreg Funds", "EMFAF", "AMIF", "ISF"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fund", default="ESF+", help="Socrata fund code (ESF+, ERDF, CF, JTF, 'Interreg Funds', EMFAF, AMIF, ISF)")
    ap.add_argument("--all", action="store_true", help="backfill every built fund's outcomes")
    ap.add_argument("--apply", action="store_true", help="write to DB (default: dry-run)")
    args = ap.parse_args()

    funds = BUILT_FUNDS if args.all else [args.fund]
    db = ChunkedDb() if args.apply else None
    try:
        for fund in funds:
            rows = fetch_fund(fund)
            n_result = sum(1 for r in rows if r.get("indicator_type_output_result") == "RESF")
            print(f"[{fund}] fetched {len(rows)} indicator rows (latest cycle) | {n_result} result indicators")
            if args.apply:
                upsert_fund(db, fund, rows)
                db.commit()
                print(f"[{fund}] [OK] wrote {len(rows)} rows")
            else:
                print(f"[{fund}] [DRY-RUN] would write {len(rows)} rows (use --apply)")
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    main()

"""
Backfill ``eu_cap_payments`` from the DG REGIO Cohesion Open Data Platform
(Socrata): EAGF (qgpc-e9qr) and EAFRD (7wr2-9vpr). One row per fund x Member
State. Amounts in EUR. Full refresh per fund. Backs /api/v2/funding/eagf and
/api/v2/funding/eafrd.

Run:
    python3.12 backend/scripts/backfill_cap_payments.py --fund EAGF            # dry-run
    python3.12 backend/scripts/backfill_cap_payments.py --fund EAGF --apply
    python3.12 backend/scripts/backfill_cap_payments.py --all --apply
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib import request as ureq

from psycopg2.extras import Json

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _specialised_helpers import ChunkedDb  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")

# fund -> (socrata dataset id, name, cohesiondata page slug)
FUNDS = {
    "EAGF":  ("qgpc-e9qr", "European Agricultural Guarantee Fund", "eagf"),
    "EAFRD": ("7wr2-9vpr", "European Agricultural Fund for Rural Development", "eafrd"),
}


def _num(v):
    if v in (None, ""):
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def _eur(n):
    if n is None:
        return "n/a"
    if n >= 1e9:
        return f"EUR {n/1e9:,.2f} billion"
    if n >= 1e6:
        return f"EUR {n/1e6:,.0f} million"
    return f"EUR {n:,.0f}"


def fetch(dataset: str) -> list[dict]:
    url = f"https://cohesiondata.ec.europa.eu/resource/{dataset}.json?$limit=1000"
    req = ureq.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with ureq.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def _map_eagf(row: dict) -> dict:
    return {
        "ms": row.get("ms"),
        "planned_eu_amount": None, "net_pre_financing": None, "net_interim_payments": None,
        "total_eur": _num(row.get("total")), "payment_rate": None,
        "fy_2023": _num(row.get("fy_2023")), "fy_2024": _num(row.get("fy_2024")),
        "fy_2025": _num(row.get("fy_2025")), "fy_2026": _num(row.get("fy_2026")),
        "fy_2027": _num(row.get("fy_2027")),
    }


def _map_eafrd(row: dict) -> dict:
    # NB: in 7wr2-9vpr the column literally named "fund" holds the Member State code.
    return {
        "ms": row.get("fund"),
        "planned_eu_amount": _num(row.get("actual_plan_eu_amt_latest_adop")),
        "net_pre_financing": _num(row.get("net_pre_financing")),
        "net_interim_payments": _num(row.get("net_interim_payments")),
        "total_eur": _num(row.get("total_net_payments")),
        "payment_rate": _num(row.get("eu_payment_rate_actual_plan_eu_amt")),
        "fy_2023": None, "fy_2024": None, "fy_2025": None, "fy_2026": None, "fy_2027": None,
    }


def compose_body(fund: str, name: str, m: dict) -> tuple[str, str]:
    ms = m.get("ms") or "?"
    if fund == "EAGF":
        years = " · ".join(f"FY{y}: {_eur(m.get('fy_'+str(y)))}" for y in range(2023, 2028) if m.get("fy_"+str(y)) is not None)
        txt = (f"{name} (EAGF) — {ms}. Total EU payments 2023-2027: {_eur(m['total_eur'])}. "
               f"Annual: {years}.")
        html = (f"<article><h3>{name} (EAGF) &mdash; {ms}</h3>"
                f"<p>Total EU payments 2023-2027: <strong>{_eur(m['total_eur'])}</strong>.</p>"
                f"<p>Annual: {years}.</p></article>")
    else:  # EAFRD
        rate = m.get("payment_rate")
        rate_txt = f" (payment rate {rate*100:.0f}%)" if rate is not None else ""
        txt = (f"{name} (EAFRD) — {ms}. Planned EU amount: {_eur(m['planned_eu_amount'])}. "
               f"Net payments to date: {_eur(m['total_eur'])}{rate_txt}.")
        html = (f"<article><h3>{name} (EAFRD) &mdash; {ms}</h3>"
                f"<p>Planned EU amount: <strong>{_eur(m['planned_eu_amount'])}</strong>.</p>"
                f"<p>Net payments to date: <strong>{_eur(m['total_eur'])}</strong>{rate_txt}.</p></article>")
    return txt, html


def upsert(db: ChunkedDb, fund: str) -> int:
    dataset, name, slug = FUNDS[fund]
    public_url = f"https://cohesiondata.ec.europa.eu/funds/{slug}/21-27"
    rows = fetch(dataset)
    db.execute("DELETE FROM eu_cap_payments WHERE fund = %s", (fund,))
    for row in rows:
        m = _map_eagf(row) if fund == "EAGF" else _map_eafrd(row)
        bt, bh = compose_body(fund, name, m)
        db.execute(
            """
            INSERT INTO eu_cap_payments
              (fund, ms, planned_eu_amount, net_pre_financing, net_interim_payments,
               total_eur, payment_rate, fy_2023, fy_2024, fy_2025, fy_2026, fy_2027,
               public_url, body_txt, body_html, body_source, source_dataset, raw)
            VALUES
              (%(fund)s,%(ms)s,%(plan)s,%(npf)s,%(nip)s,%(total)s,%(rate)s,
               %(y23)s,%(y24)s,%(y25)s,%(y26)s,%(y27)s,
               %(url)s,%(bt)s,%(bh)s,'composed',%(ds)s,%(raw)s)
            """,
            {"fund": fund, "ms": m["ms"], "plan": m["planned_eu_amount"],
             "npf": m["net_pre_financing"], "nip": m["net_interim_payments"],
             "total": m["total_eur"], "rate": m["payment_rate"],
             "y23": m["fy_2023"], "y24": m["fy_2024"], "y25": m["fy_2025"],
             "y26": m["fy_2026"], "y27": m["fy_2027"],
             "url": public_url, "bt": bt, "bh": bh, "ds": dataset, "raw": Json(row)},
        )
    return len(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fund", default="EAGF", choices=list(FUNDS))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    funds = list(FUNDS) if args.all else [args.fund]
    db = ChunkedDb() if args.apply else None
    try:
        for fund in funds:
            if args.apply:
                n = upsert(db, fund); db.commit()
                print(f"[{fund}] [OK] wrote {n} rows")
            else:
                rows = fetch(FUNDS[fund][0])
                print(f"[{fund}] [DRY-RUN] would write {len(rows)} rows (use --apply)")
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    main()

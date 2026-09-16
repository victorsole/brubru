#!/usr/bin/env python3.12
"""Mirror the European Commission's register of infringement decisions.

Source
------
ec.europa.eu/implementing-eu-law/search-infringement-decisions/ is an app over a JSON
API: `POST api/decisions` (filters + page/size) and `GET api/referencedata/loadAll`
(the code lists). Plain HTTP, no browser, no key. Measured 16 Sep 2026: 62,610
decisions (1987-2026), 25,658 cases, 1,909 of them active.

How the whole register is read
------------------------------
The API accepts a `sortColumns` field but does not honour it, so paging through the
full result could skip or repeat rows between pages. Instead the register is read in
DATE WINDOWS that each fit in one page (size 5,000): everything before 1990 in one
window, then one window per year, split into months if a year ever exceeds 5,000.
The windows are then RECONCILED against the register's own unfiltered `totalRows`:
if the counts differ, nothing is deleted and the run fails loudly.

What it writes
--------------
* infringement_decisions: upsert on (infringement_number, decision_date,
  decision_type), the register's own key, unique on every row; a composed body and
  the five datapoints. After a reconciled sweep, a decision the register no longer
  lists is deleted (counted and printed).
* infringement_cases: rebuilt from the decisions (latest decision, counts, links).
* a sync_runs ledger row (source_key infringement_register).

public_url: the register has no page per case or decision; its app ignores URL
parameters (tested 16 Sep 2026). A decision links to its own press release, memo or
Court case when it has one, else to the register search page; public_url_kind says
which.

Usage
-----
    python3.12 scripts/sync_infringement_register.py --dry-run
    python3.12 scripts/sync_infringement_register.py --apply
"""
from __future__ import annotations

import argparse
import calendar
import html
import pathlib
import re
import sys
import time
from datetime import date, datetime, timezone

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_BACKEND = pathlib.Path(__file__).resolve().parents[1]
for _p in (str(_REPO_ROOT), str(_BACKEND)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REGISTER_API = "https://ec.europa.eu/implementing-eu-law/search-infringement-decisions/api"
REGISTER_SEARCH_URL = ("https://ec.europa.eu/implementing-eu-law/search-infringement-decisions/"
                       "?typeOfSearch=byDecision&langCode=EN")
PAGE_SIZE = 5000
PACE_SECONDS = 0.7
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/140.0 Safari/537.36",
    "Accept": "application/json",
    "Content-Type": "application/json",
}
_QUERY = {
    "refId": None, "relatedPetition": None, "petition": None, "decisionDateFrom": None,
    "decisionDateTo": None, "langCode": "EN", "memberState": None, "decisionCategory": None,
    "infringementType": None, "activeCase": None, "pressRelease": None, "page": 0,
    "size": PAGE_SIZE, "title": None, "legalBasis": None, "dg": None, "policyArea": None,
    "courtFinancialSanctions": None, "order": "asc", "sortColumns": "leadDg",
}


class RegisterError(RuntimeError):
    pass


# --------------------------------------------------------------------------- fetch
def _client():
    import httpx
    return httpx.Client(headers=_HEADERS, timeout=240)


def fetch_window(client, date_from: str | None, date_to: str | None) -> dict:
    body = {**_QUERY, "decisionDateFrom": date_from, "decisionDateTo": date_to}
    for attempt in range(3):
        r = client.post(f"{REGISTER_API}/decisions", json=body)
        if r.status_code == 200:
            time.sleep(PACE_SECONDS)
            return r.json()
        time.sleep(5 * (attempt + 1))
    raise RegisterError(f"register answered {r.status_code} for window {date_from}..{date_to}")


def fetch_register(client, *, today: date | None = None) -> tuple[list[dict], int]:
    """(every decision record, the register's own total)."""
    today = today or date.today()
    total = int(fetch_window(client, None, None)["totalRows"])  # size=5000, reads the total
    records: list[dict] = []

    def take(j: dict, label: str) -> None:
        if int(j["totalRows"]) > PAGE_SIZE:
            raise RegisterError(f"window {label} holds {j['totalRows']} > {PAGE_SIZE}")
        records.extend(j["records"])

    take(fetch_window(client, "01/01/1900", "31/12/1989"), "pre-1990")
    for year in range(1990, today.year + 1):
        j = fetch_window(client, f"01/01/{year}", f"31/12/{year}")
        if int(j["totalRows"]) <= PAGE_SIZE:
            records.extend(j["records"])
            continue
        for month in range(1, 13):
            last = calendar.monthrange(year, month)[1]
            take(fetch_window(client, f"01/{month:02d}/{year}", f"{last}/{month:02d}/{year}"),
                 f"{year}-{month:02d}")
    # A decision dated after today (a data-entry error) would sit outside every window.
    take(fetch_window(client, f"01/01/{today.year + 1}", "31/12/2100"), "future")
    return records, total


def fetch_reference(client) -> dict:
    r = client.get(f"{REGISTER_API}/referencedata/loadAll")
    r.raise_for_status()
    data = r.json()
    ref = {}
    for key in ("memberState", "dg", "decisionType"):
        ref[key] = {_norm(e["title"]): e["key"] for e in data.get(key, []) if e.get("language") == "EN"}
    # Two lead departments appear on decisions but not in the reference list (16 Sep 2026).
    for title, code in (("European Anti-Fraud Office", "OLAF"), ("Service for Foreign Policy Instruments", "FPI")):
        ref["dg"].setdefault(title, code)
    m = client.get(f"{REGISTER_API}/referencedata/decision-type/mapping")
    m.raise_for_status()
    ref["decisionCategory"] = m.json()
    return ref


# --------------------------------------------------------------------------- transform
def _norm(s) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(s or ""))).strip()


def _flag(v) -> bool | None:
    return {"yes": True, "no": False}.get(str(v or "").strip().lower())


def _date(v) -> date:
    d, m, y = (int(x) for x in str(v).strip().split("/"))
    return date(y, m, d)


def _https(url):
    url = (url or "").strip() or None
    if url and url.startswith("http://curia.europa.eu"):
        url = "https://" + url[len("http://"):]
    return url


def public_url_for(rec: dict) -> tuple[str, str]:
    for url, kind in ((rec.get("press_release_url"), "press_release"), (rec.get("memo_url"), "memo"),
                      (rec.get("court_case_url"), "court_case")):
        if url:
            return url, kind
    return REGISTER_SEARCH_URL, "register_search"


def compose_decision_body(rec: dict) -> tuple[str, str]:
    lines = [
        f"{rec['decision_type']} on {rec['decision_date'].isoformat()} in infringement case "
        f"{rec['infringement_number']} against {rec['member_state_name'] or rec['member_state'] or 'a Member State'}.",
        f"Subject: {rec['title']}" if rec["title"] else None,
        f"Type of infringement: {rec['case_type']}." if rec["case_type"] else None,
        f"Lead Commission department: {rec['lead_dg']}." if rec["lead_dg"] else None,
        f"Policy areas: {', '.join(rec['policy_areas'])}." if rec["policy_areas"] else None,
        ("The case is active." if rec["active_case"] else "The case is closed.") if rec["active_case"] is not None else None,
        f"Press release: {rec['press_release']} ({rec['press_release_url']})." if rec["press_release_url"] else None,
        f"Memo: {rec['memo']} ({rec['memo_url']})." if rec["memo_url"] else None,
        f"Court of Justice case: {rec['court_case']} ({rec['court_case_url']})." if rec["court_case_url"] else None,
        "Source: European Commission register of infringement decisions.",
    ]
    lines = [x for x in lines if x]
    e = html.escape
    parts = [f"<h1>{e(rec['decision_type'])}: {e(rec['infringement_number'])}</h1>"]
    parts += [f"<p>{e(x)}</p>" for x in lines]
    return "\n\n".join(lines), "<article>" + "".join(parts) + "</article>"


def transform(raw: dict, ref: dict) -> dict:
    ms_name = _norm(raw.get("memberState")) or None
    dg = _norm(raw.get("leadDg")) or None
    dtype = _norm(raw.get("decisionType"))
    dcode = ref["decisionType"].get(dtype)
    rec = {
        "infringement_number": _norm(raw["infringementNumber"]),
        "member_state": ref["memberState"].get(ms_name) if ms_name else None,
        "member_state_name": ms_name,
        "lead_dg": dg,
        "lead_dg_code": ref["dg"].get(dg) if dg else None,
        "case_type": _norm(raw.get("caseType")) or None,
        "title": _norm(raw.get("title")) or None,
        "active_case": _flag(raw.get("activeInfringementCase")),
        "non_communication": _flag(raw.get("nonCommunicationCase")),
        "decision_date": _date(raw["decisionDate"]),
        "decision_type": dtype,
        "decision_type_code": dcode,
        "decision_category": ref["decisionCategory"].get(dcode) if dcode else None,
        "press_release": _norm(raw.get("pressRelease")) or None,
        "press_release_url": _https(raw.get("pressReleaseURL")),
        "memo": _norm(raw.get("memo")) or None,
        "memo_url": _https(raw.get("memoURL")),
        "court_case": _norm(raw.get("normalCuriaReference")) or None,
        "court_case_url": _https(raw.get("normalCuriaReferenceURL")),
        "policy_areas": sorted({_norm(p) for p in (raw.get("policyAreas") or []) if _norm(p)}),
    }
    rec["public_url"], rec["public_url_kind"] = public_url_for(rec)
    rec["body_txt"], rec["body_html"] = compose_decision_body(rec)
    rec["body_source"] = "composed:register"
    return rec


def build_cases(decisions: list[dict]) -> list[dict]:
    by_case: dict[str, list[dict]] = {}
    for d in decisions:
        by_case.setdefault(d["infringement_number"], []).append(d)
    cases = []
    for number, ds in by_case.items():
        ds = sorted(ds, key=lambda d: (d["decision_date"], d["decision_type"]))
        latest = ds[-1]
        press = sorted({d["press_release_url"] for d in ds if d["press_release_url"]})
        courts = sorted({d["court_case"] for d in ds if d["court_case"]})
        c = {
            "infringement_number": number,
            "member_state": latest["member_state"], "member_state_name": latest["member_state_name"],
            "lead_dg": latest["lead_dg"], "lead_dg_code": latest["lead_dg_code"],
            "case_type": latest["case_type"], "title": latest["title"],
            "active_case": latest["active_case"], "non_communication": latest["non_communication"],
            "first_decision_date": ds[0]["decision_date"], "latest_decision_date": latest["decision_date"],
            "latest_decision_type": latest["decision_type"], "latest_decision_category": latest["decision_category"],
            "decision_count": len(ds),
            "policy_areas": sorted({p for d in ds for p in d["policy_areas"]}),
            "court_cases": courts, "press_release_urls": press,
        }
        # The newest decision that has its own page, else the register search page.
        c["public_url"], c["public_url_kind"] = REGISTER_SEARCH_URL, "register_search"
        for d in reversed(ds):
            if d["public_url_kind"] != "register_search":
                c["public_url"], c["public_url_kind"] = d["public_url"], d["public_url_kind"]
                break
        steps = "; ".join(f"{d['decision_date'].isoformat()}: {d['decision_type']}" for d in ds)
        lines = [
            f"Infringement case {number} against {c['member_state_name'] or c['member_state'] or 'a Member State'}"
            f" ({'active' if c['active_case'] else 'closed'}).",
            f"Subject: {c['title']}" if c["title"] else None,
            f"Type of infringement: {c['case_type']}." if c["case_type"] else None,
            f"Lead Commission department: {c['lead_dg']}." if c["lead_dg"] else None,
            f"Policy areas: {', '.join(c['policy_areas'])}." if c["policy_areas"] else None,
            f"Decisions ({len(ds)}): {steps}.",
            f"Court of Justice cases: {', '.join(courts)}." if courts else None,
            f"Press releases: {', '.join(press)}." if press else None,
            "Source: European Commission register of infringement decisions.",
        ]
        lines = [x for x in lines if x]
        e = html.escape
        c["body_txt"] = "\n\n".join(lines)
        c["body_html"] = (f"<article><h1>{e(number)}</h1>" + "".join(f"<p>{e(x)}</p>" for x in lines)
                          + "</article>")
        c["body_source"] = "composed:register"
        cases.append(c)
    return cases


# --------------------------------------------------------------------------- write
_DECISION_COLS = ["infringement_number", "member_state", "member_state_name", "lead_dg", "lead_dg_code",
                  "case_type", "title", "active_case", "non_communication", "decision_date", "decision_type",
                  "decision_type_code", "decision_category", "press_release", "press_release_url", "memo",
                  "memo_url", "court_case", "court_case_url", "policy_areas", "public_url", "public_url_kind",
                  "body_txt", "body_html", "body_source"]
_CASE_COLS = ["infringement_number", "member_state", "member_state_name", "lead_dg", "lead_dg_code",
              "case_type", "title", "active_case", "non_communication", "first_decision_date",
              "latest_decision_date", "latest_decision_type", "latest_decision_category", "decision_count",
              "policy_areas", "court_cases", "press_release_urls", "public_url", "public_url_kind",
              "body_txt", "body_html", "body_source"]


def _upsert_sql(table: str, cols: list[str], conflict: str) -> str:
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in conflict.split(", "))
    return (f"INSERT INTO public.{table} ({', '.join(cols)}, last_seen_at) VALUES %s "
            f"ON CONFLICT ({conflict}) DO UPDATE SET {updates}, last_seen_at = EXCLUDED.last_seen_at")


def write(decisions: list[dict], cases: list[dict], started: datetime) -> dict:
    from psycopg2.extras import execute_values
    from scripts._specialised_helpers import ChunkedDb

    db = ChunkedDb()
    out = {}
    for table, cols, conflict, rows in (
        ("infringement_decisions", _DECISION_COLS, "infringement_number, decision_date, decision_type", decisions),
        ("infringement_cases", _CASE_COLS, "infringement_number", cases),
    ):
        sql = _upsert_sql(table, cols, conflict)
        tuples = [tuple(r[c] for c in cols) + (started,) for r in rows]
        for i in range(0, len(tuples), 1000):
            execute_values(db.cur, sql, tuples[i:i + 1000], page_size=1000)
            db.commit()
        # Rows the register no longer lists: only after a reconciled sweep (the caller
        # guarantees it), and never more than a sanity share of the table.
        db.execute(f"SELECT count(*) FROM public.{table} WHERE last_seen_at < %s", (started,))
        stale = db.cur.fetchone()[0]
        db.execute(f"SELECT count(*) FROM public.{table}")
        held = db.cur.fetchone()[0]
        if stale and stale > 0.02 * held:
            raise RegisterError(f"{table}: {stale} of {held} rows unseen in a reconciled sweep; refusing to delete")
        if stale:
            db.execute(f"DELETE FROM public.{table} WHERE last_seen_at < %s", (started,))
            db.commit()
        out[table] = {"upserted": len(tuples), "deleted_unseen": stale}
    db.execute("SELECT count(*) FROM public.infringement_decisions")
    out["decisions_held"] = db.cur.fetchone()[0]
    db.execute("SELECT count(*) FROM public.infringement_cases")
    out["cases_held"] = db.cur.fetchone()[0]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    started = datetime.now(timezone.utc)
    error = None
    summary = {}
    try:
        with _client() as client:
            ref = fetch_reference(client)
            raw, total = fetch_register(client)
        print(f"[INFO] register total {total}; fetched {len(raw)} decisions in date windows")
        if len(raw) != total:
            raise RegisterError(f"reconciliation failed: windows returned {len(raw)} of {total}")
        decisions = [transform(r, ref) for r in raw]
        keys = {(d["infringement_number"], d["decision_date"], d["decision_type"]) for d in decisions}
        if len(keys) != len(decisions):
            raise RegisterError(f"natural key not unique: {len(decisions) - len(keys)} duplicate decisions")
        cases = build_cases(decisions)
        unmapped = {
            "member_state": sorted({d["member_state_name"] for d in decisions if d["member_state_name"] and not d["member_state"]}),
            "lead_dg": sorted({d["lead_dg"] for d in decisions if d["lead_dg"] and not d["lead_dg_code"]}),
            "decision_type": sorted({d["decision_type"] for d in decisions if not d["decision_category"]}),
        }
        print(f"[INFO] decisions {len(decisions)}, cases {len(cases)}, "
              f"active cases {sum(1 for c in cases if c['active_case'])}")
        for k, v in unmapped.items():
            if v:
                print(f"[WARN] no code for {len(v)} {k} value(s): {v[:6]}")
        kinds = {}
        for d in decisions:
            kinds[d["public_url_kind"]] = kinds.get(d["public_url_kind"], 0) + 1
        print(f"[INFO] decision public_url kinds: {kinds}")
        if args.dry_run:
            print("[DRY-RUN] nothing written")
            return 0
        summary = write(decisions, cases, started)
        print(f"[OK] {summary}")
        return 0
    except Exception as e:  # recorded, then re-raised as a failing exit
        error = f"{type(e).__name__}: {e}"
        print(f"[ERROR] {error}")
        return 1
    finally:
        if args.apply:
            try:
                from core.database import SessionLocal
                from services.sync.freshness import record_run
                s = SessionLocal()
                record_run(s, source_key="infringement_register", tier="daily",
                           status="failed" if error else "success",
                           items_added=(summary.get("infringement_decisions") or {}).get("upserted"),
                           error=error, started_at=started, finished_at=datetime.now(timezone.utc))
                s.close()
            except Exception as e:  # noqa: BLE001
                print(f"[WARN] could not record the run: {type(e).__name__}: {e}")


if __name__ == "__main__":
    sys.exit(main())

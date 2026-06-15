"""
Ingest EU F&T Portal NON-H2020 funded projects (SEDIA_NONH2020_PROD).

The F&T projects-results page (.../opportunities/projects-results) is backed by
a dedicated index, apiKey=SEDIA_NONH2020_PROD, holding funded projects from the
NON-research programmes (CEF, LIFE, Digital, AMIF/ISF, external action, etc.) —
data our CORDIS ingest (H2020/FP7/Horizon) does NOT have.

That index reliably returns HTTP 500 "Send timeout" (code 101504) to raw scripted
access; ONLY a real browser session gets through (with retries). So this crawler
drives a headless Chromium, establishes a portal session, then issues the search
via an in-page `fetch()` (same CORS allowance + session the SPA uses). It paginates
SLOWLY with backoff — the CDN soft-blocks rapid looping.

Stored in ft_funded_projects (framework_programme = the programme abbreviation,
e.g. CEF / LIFE / NDICI) so /api/v2/funding/ft-funded-projects?framework_programme=
returns them alongside the CORDIS rows. Upsert on project_id.

Run:
    python3.12 backend/scripts/ingest_ft_projects_nonh2020.py --probe
    python3.12 backend/scripts/ingest_ft_projects_nonh2020.py --apply --max-pages 50
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from typing import Any, Dict, List, Optional

import psycopg2
from playwright.sync_api import sync_playwright

from ingest_funding_sedia import get_env

PORTAL = ("https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/"
          "opportunities/projects-results?order=DESC&pageNumber=1&pageSize=50&sortBy=es_SortDate")
PROJECT_URL = ("https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/"
               "opportunities/projects-details/{pid}")
APIKEY = "SEDIA_NONH2020_PROD"

# Executed inside the page context — has the portal session + CORS allowance.
# Research programmes we already hold (CORDIS): excluded so we ingest only the
# genuinely-new non-research projects (Erasmus, Creative Europe, CEF, LIFE,
# AMIF/ISF, external action, ...).
RESEARCH = ["H2020", "FP7", "HORIZON", "HORIZON2027", "EURATOM", "FP6", "FP5"]

# Executed inside the page context — has the portal session + CORS allowance.
# `query` is passed in so we can year-slice (the API caps pagination at offset
# 10,000, so each slice must stay under 10k results).
FETCH_JS = """
async ({pageNum, size, query}) => {
  const blob = (o) => new Blob([JSON.stringify(o)], {type:'application/json'});
  const fd = new FormData();
  fd.append('sort', blob({order:'DESC', field:'startDate'}), 'blob');
  fd.append('query', blob(query), 'blob');
  fd.append('languages', blob(['en']), 'blob');
  fd.append('displayFields', blob(['title','projectId','acronym','participants',
     'programAbbreviation','programmes','status','objective','startDate','endDate',
     'ecMaxContribution','totalCost','frameworkProgramme']), 'blob');
  const url = `https://api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey=__KEY__&text=***&pageSize=${size}&pageNumber=${pageNum}`;
  try {
    const r = await fetch(url, {method:'POST', body:fd});
    return {status: r.status, body: await r.text()};
  } catch (e) { return {status: -1, body: String(e)}; }
}
""".replace("__KEY__", APIKEY)


def _year_query(year: Optional[int]):
    """Non-research projects, optionally bounded to one startDate year.

    startDate (the real project start) partitions the corpus evenly — every year
    is well under the API's 10k pagination cap (es_SortDate clusters everything
    in 2024-26 and overflows the cap, so it is NOT used for slicing).
    """
    must = [{"terms": {"language": ["en"]}}]
    if year is not None:
        gte = int(dt.datetime(year, 1, 1).timestamp() * 1000)
        lte = int(dt.datetime(year, 12, 31, 23, 59, 59).timestamp() * 1000)
        must.append({"range": {"startDate": {"gte": gte, "lte": lte}}})
    return {"bool": {"must": must, "must_not": [{"terms": {"programAbbreviation": RESEARCH}}]}}


def _first(v):
    if isinstance(v, list):
        return v[0] if v else None
    return v


def _num(v) -> Optional[float]:
    v = _first(v)
    if v in (None, ""):
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def _date(v) -> Optional[dt.datetime]:
    v = _first(v)
    if not v:
        return None
    try:
        return dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


def normalise(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    md = result.get("metadata") or {}
    pid = _first(md.get("projectId")) or _first(md.get("identifier")) or result.get("reference")
    title = _first(md.get("title")) or result.get("title")
    if not pid or not title:
        return None
    programme = (_first(md.get("programAbbreviation")) or _first(md.get("programmes"))
                 or _first(md.get("frameworkProgramme")))
    participants = md.get("participants") or []
    if not isinstance(participants, list):
        participants = [participants]
    coordinator = participants[0] if participants else None
    return {
        "project_id": str(pid),
        "project_acronym": _first(md.get("acronym")),
        "title": title,
        "objective": _first(md.get("objective")),
        "framework_programme": str(programme) if programme else "NON-H2020",
        "coordinator_name": str(coordinator)[:300] if coordinator else None,
        "status": _first(md.get("status")),
        "start_date": _date(md.get("startDate")),
        "end_date": _date(md.get("endDate")),
        "eu_contribution": _num(md.get("ecMaxContribution")),
        "total_cost": _num(md.get("totalCost")),
        "source_url": PROJECT_URL.format(pid=pid),
        "published_at": _date(md.get("startDate")) or _date(md.get("es_SortDate")),
    }


UPSERT = """
INSERT INTO ft_funded_projects
    (project_id, project_acronym, title, objective, framework_programme,
     coordinator_name, status, start_date, end_date, eu_contribution, total_cost,
     cost_currency, source_url, is_test, published_at, scraped_at, last_updated)
VALUES (%(project_id)s, %(project_acronym)s, %(title)s, %(objective)s,
        %(framework_programme)s, %(coordinator_name)s, %(status)s, %(start_date)s,
        %(end_date)s, %(eu_contribution)s, %(total_cost)s, 'EUR', %(source_url)s,
        false, %(published_at)s, NOW(), NOW())
ON CONFLICT (project_id) DO UPDATE SET
    title=EXCLUDED.title, objective=EXCLUDED.objective,
    framework_programme=EXCLUDED.framework_programme, status=EXCLUDED.status,
    eu_contribution=EXCLUDED.eu_contribution, total_cost=EXCLUDED.total_cost,
    last_updated=NOW()
"""


def _fetch(page, pnum, size, query):
    res = None
    for attempt in range(4):
        try:
            res = page.evaluate(FETCH_JS, {"pageNum": pnum, "size": size, "query": query})
        except Exception as e:  # noqa: BLE001
            res = {"status": -1, "body": str(e)[:80]}
        if res and res.get("status") == 200:
            return res
        time.sleep(2 + attempt * 3)  # backoff: 2,5,8,11s
    return res


def crawl(*, apply: bool, max_pages: int, size: int, probe: bool,
          year_from: int, year_to: int):
    conn = psycopg2.connect(get_env("DATABASE_URL")) if apply else None
    cur = conn.cursor() if conn else None
    written = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36")
        page = ctx.new_page()

        def _session():
            try:
                page.goto(PORTAL, wait_until="domcontentloaded", timeout=40000)
            except Exception as e:  # noqa: BLE001
                print(f"[warn] portal load: {str(e)[:60]}")
            page.wait_for_timeout(3000)

        _session()

        if probe:
            res = _fetch(page, 1, size, _year_query(None))
            data = json.loads(res["body"]) if res and res.get("status") == 200 else {}
            print(f"[PROBE] non-research total={data.get('totalResults')}")
            import collections
            prog = collections.Counter()
            for r in (data.get("results") or []):
                row = normalise(r)
                if row:
                    prog[row["framework_programme"]] += 1
            print("  programmes (page1):", dict(prog.most_common(15)))
            browser.close()
            return

        # Year-slice so each query stays under the 10k pagination cap.
        years = list(range(year_to, year_from - 1, -1))
        for yi, year in enumerate(years):
            query = _year_query(year)
            pnum = 1
            year_written = 0
            while pnum <= max_pages:
                if pnum % 25 == 0:        # refresh the session periodically
                    _session()
                res = _fetch(page, pnum, size, query)
                if not res or res.get("status") != 200:
                    print(f"  [{year} p{pnum}] gave up (status={res.get('status') if res else '?'})")
                    break
                try:
                    data = json.loads(res["body"])
                except Exception:  # noqa: BLE001
                    print(f"  [{year} p{pnum}] unparseable"); break
                total = data.get("totalResults", 0)
                results = data.get("results") or []
                if not results:
                    break
                for r in results:
                    row = normalise(r)
                    if row and cur:
                        try:
                            cur.execute(UPSERT, row); written += 1; year_written += 1
                        except Exception as exc:  # noqa: BLE001
                            conn.rollback(); print(f"    [DB ERR] {row['project_id']}: {str(exc)[:50]}")
                if conn:
                    conn.commit()
                if len(results) < size or pnum * size >= total or pnum * size >= 10000:
                    break
                pnum += 1
                time.sleep(2.5)  # be gentle — the CDN soft-blocks rapid looping
            print(f"[{year}] +{year_written}  (running total {written})")
        browser.close()
    print(f"\n[DONE] written={written} apply={apply}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true", help="Fetch page 1 only, print, no DB write.")
    ap.add_argument("--apply", action="store_true", help="Write to DB.")
    ap.add_argument("--max-pages", type=int, default=100)
    ap.add_argument("--page-size", type=int, default=100)
    ap.add_argument("--year-from", type=int, default=2014)
    ap.add_argument("--year-to", type=int, default=2027)
    args = ap.parse_args()
    crawl(apply=args.apply, max_pages=args.max_pages, size=args.page_size, probe=args.probe,
          year_from=args.year_from, year_to=args.year_to)


if __name__ == "__main__":
    main()

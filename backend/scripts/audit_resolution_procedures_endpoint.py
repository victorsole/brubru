#!/usr/bin/env python3.12
"""Test /resolution-procedures end to end, on the real route, against the database.

Why (12 Oct 2026): the endpoint was audited field by field on 8-9 Oct, and on 12 Oct the
query GovClipping uses answered `total: 0` with nothing in the response to say why. Every
check here is one a client would trip over: each filter's total against an independent SQL
count, both paging orders walked to the end, every item's fields, the item route, the
deprecated alias and v1.

Two transports, the same checks:
    python3.12 scripts/audit_resolution_procedures_endpoint.py --in-process   # this checkout's code
    python3.12 scripts/audit_resolution_procedures_endpoint.py                # production
`--in-process` mounts the real v1 + v2 routers (and the self-link and export middleware) in
an app WITHOUT main.py's lifespan, so no scheduler starts against the shared database.

Exit 0 only when every check passes. Read-only: it calls GET routes and SELECTs.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR.parent / ".env")

import os  # noqa: E402

from sqlalchemy import create_engine, text  # noqa: E402

PROD = "https://brubru-production.up.railway.app"
V2 = "/api/v2/parliament/resolution-procedures"
V2_OLD = "/api/v2/parliament/resolutions"
V1 = "/api/v1/resolutions"
STATUSES = ("adopted", "pending", "closed_without_resolution", "rejected")
TYPES = ("INL", "INI", "RSP", "OTHER")
REF_RE = re.compile(r"^\d{4}/\d{4}[A-Z]?\((INI|RSP|INL)\)$")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
THIN_BODY = 300  # characters: under this a body is a label, not a document


class Api:
    """GET with the partner key; paced under the 60-per-minute limit, retried on 429."""

    def __init__(self, in_process: bool, pace: float):
        self.key = os.environ.get("BRUBRU_API_KEY") or ""
        if not self.key:
            sys.exit("[ERROR] BRUBRU_API_KEY not set")
        self.pace, self._last, self.calls, self.slowest = pace, 0.0, 0, (0.0, "")
        self.client = None
        if in_process:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient

            from api.export_middleware import TabularExportMiddleware
            from api.self_link_middleware import SelfLinkMiddleware
            from api.v1 import router as v1_router
            from api.v2 import router as v2_router
            from core.self_links import build_route_map

            app = FastAPI()
            app.include_router(v1_router)
            app.include_router(v2_router)
            app.add_middleware(SelfLinkMiddleware, route_map_factory=lambda: build_route_map(app))
            app.add_middleware(TabularExportMiddleware)
            self.client = TestClient(app)

    def get(self, path: str, params: Optional[dict] = None, *, key: bool = True) -> tuple[int, dict, Any]:
        wait = self.pace - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        qs = urllib.parse.urlencode(params or {})
        url = path + (("?" + qs) if qs else "")
        headers = {"X-Brubru-Probe": "audit-resolution-procedures"}
        if key:
            headers["X-API-Key"] = self.key
        for attempt in range(4):
            t0 = time.monotonic()
            if self.client is not None:
                r = self.client.get(url, headers=headers)
                status, hdrs, raw = r.status_code, {k.lower(): v for k, v in r.headers.items()}, r.content
            else:
                req = urllib.request.Request(PROD + url, headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        status, hdrs, raw = resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read()
                except urllib.error.HTTPError as e:
                    status, hdrs, raw = e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()
            took = time.monotonic() - t0
            self._last = time.monotonic()
            self.calls += 1
            if status == 429 and attempt < 3:
                time.sleep(float(hdrs.get("retry-after", "20")) + 1)
                continue
            if took > self.slowest[0]:
                self.slowest = (took, url)
            try:
                body = json.loads(raw) if "json" in hdrs.get("content-type", "") else raw
            except ValueError:
                body = raw
            return status, hdrs, body
        return status, hdrs, body  # pragma: no cover


class Report:
    def __init__(self):
        self.rows: list[tuple[bool, str, str]] = []

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.rows.append((bool(ok), name, detail))
        return bool(ok)

    def failed(self) -> list[tuple[bool, str, str]]:
        return [r for r in self.rows if not r[0]]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--in-process", action="store_true", help="test this checkout's code, not production")
    ap.add_argument("--pace", type=float, default=1.05, help="seconds between requests (60 a minute allowed)")
    ap.add_argument("--verbose", action="store_true", help="print passing checks too")
    args = ap.parse_args()

    api, rep = Api(args.in_process, args.pace), Report()
    url = os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1)
    engine = create_engine(url, pool_pre_ping=True)

    def sql(q: str, **p):
        with engine.connect() as c:
            return c.execute(text(q), p).scalar()

    def total(params: dict, path: str = V2) -> tuple[int, Any, dict]:
        st, _, body = api.get(path, {"limit": 1, **params})
        return st, (body.get("total") if isinstance(body, dict) else None), (body if isinstance(body, dict) else {})

    def same_total(name: str, params: dict, where: str, **p):
        st, got, _ = total(params)
        want = sql(f"SELECT count(*) FROM ep_resolutions WHERE {where}", **p)
        rep.check(name, st == 200 and got == want, f"api {got} (HTTP {st}) vs database {want}")

    def expect_422(name: str, params: dict):
        st, _, body = total(params)
        rep.check(name, st == 422, f"HTTP {st} {str(body)[:90]}")

    # ---- A. totals and filters ------------------------------------------------------
    n_all = sql("SELECT count(*) FROM ep_resolutions")
    same_total("no filter returns every procedure", {}, "true")
    for s in STATUSES:
        same_total(f"status={s}", {"status": s}, "status = :s", s=s)
    expect_422("status=bogus is refused", {"status": "bogus"})
    for t in TYPES:
        same_total(f"resolution_type={t}", {"resolution_type": t}, "resolution_type::text = :t", t=t)
    same_total("resolution_type is case-insensitive (ini)", {"resolution_type": "ini"}, "resolution_type::text = 'INI'")
    expect_422("resolution_type=bogus is refused, not a 500", {"resolution_type": "bogus"})
    committee = sql("SELECT lead_committee FROM ep_resolutions WHERE lead_committee IS NOT NULL "
                    "GROUP BY 1 ORDER BY count(*) DESC, 1 LIMIT 1")
    same_total(f"lead_committee={committee}", {"lead_committee": committee}, "lead_committee = :c", c=committee)
    same_total("lead_committee is case-insensitive", {"lead_committee": committee.lower()}, "lead_committee = :c", c=committee)
    rapp = sql("SELECT split_part(rapporteur, ' ', 1) FROM ep_resolutions WHERE length(split_part(rapporteur, ' ', 1)) > 4 "
               "GROUP BY 1 ORDER BY count(*) DESC, 1 LIMIT 1")
    same_total(f"rapporteur={rapp}", {"rapporteur": rapp}, "rapporteur ILIKE :r", r=f"%{rapp}%")
    for word in ("Ukraine", "artificial intelligence", "zzzz-no-such-word"):
        same_total(f"q={word!r}", {"q": word}, "(title ILIKE :w OR summary ILIKE :w)", w=f"%{word}%")
    same_total("procedure_ref finds exactly that procedure", {"procedure_ref": "2026/2561(RSP)"},
               "procedure_ref = '2026/2561(RSP)'")
    for flag in ("true", "false"):
        same_total(f"has_commission_followup={flag}", {"has_commission_followup": flag},
                   f"has_commission_followup IS {flag.upper()}")
    same_total("published window Q1 2026", {"published_from": "2026-01-01", "published_to": "2026-03-31"},
               "adoption_date BETWEEN '2026-01-01' AND '2026-03-31'")
    same_total("published_end is an alias of published_to", {"published_from": "2026-01-01", "published_end": "2026-03-31"},
               "adoption_date BETWEEN '2026-01-01' AND '2026-03-31'")
    expect_422("published_to and published_end that disagree are refused",
               {"published_to": "2026-03-31", "published_end": "2026-04-30"})
    same_total("combined filters", {"status": "adopted", "resolution_type": "RSP", "published_from": "2026-01-01"},
               "status = 'adopted' AND resolution_type::text = 'RSP' AND adoption_date >= '2026-01-01'")

    # ---- B. date windows (the query that answered 0 on 12 Oct 2026) ------------------
    gc = {"updated_from": "2024-07-15T19:00:00Z", "updated_to": "2026-09-28T11:05:00Z"}
    st, got, body = total(gc)
    want = sql("SELECT count(*) FROM ep_resolutions WHERE updated_at >= '2024-07-15 19:00' AND updated_at <= '2026-09-28 11:05'")
    rep.check("GovClipping's backfill window matches the database", st == 200 and got == want, f"api {got} vs database {want}")
    if want == 0:
        rep.check("an empty window says where the dates lie", "EMPTY WINDOW" in (body.get("coverage_note") or ""),
                  (body.get("coverage_note") or "")[-160:])
    same_total("updated_from alone returns everything changed since", {"updated_from": "2026-09-28T11:05:00Z"},
               "updated_at >= '2026-09-28 11:05'")
    same_total("a bare date as updated_to covers the whole day", {"updated_to": "2026-10-08"},
               "updated_at < '2026-10-09'")
    same_total("updated_end is an alias of updated_to", {"updated_end": "2026-10-08"}, "updated_at < '2026-10-09'")
    expect_422("updated_to and updated_end that disagree are refused",
               {"updated_to": "2026-10-08", "updated_end": "2026-10-09"})
    expect_422("an inverted updated window is refused", {"updated_from": "2026-10-09", "updated_to": "2026-10-01"})
    same_total("created_to keeps what Brubru held by 28 Sep", {"created_to": "2026-09-28T11:05:00Z"},
               "created_at <= '2026-09-28 11:05'")
    same_total("created_from keeps what was added since 9 Oct", {"created_from": "2026-10-09"}, "created_at >= '2026-10-09'")
    same_total("a bare date as created_to covers the whole day", {"created_to": "2026-10-08"}, "created_at < '2026-10-09'")
    expect_422("an inverted created window is refused", {"created_from": "2026-10-09", "created_to": "2026-10-01"})
    _, a, _ = total({"created_to": "2026-10-08"})
    _, b, _ = total({"created_from": "2026-10-09"})
    rep.check("the two created windows add up to the whole table", (a or 0) + (b or 0) == n_all, f"{a} + {b} vs {n_all}")
    expect_422("order=bogus is refused", {"order": "bogus"})
    for order, field, desc in (("updated_asc", "updated_date", False), ("updated_desc", "updated_date", True),
                               ("created_asc", "creation_date", False), ("created_desc", "creation_date", True)):
        st, _, body = api.get(V2, {"order": order, "limit": 100})
        vals = [i.get(field) for i in (body.get("data") or [])] if isinstance(body, dict) else []
        rep.check(f"order={order} sorts the page", st == 200 and len(vals) > 1 and vals == sorted(vals, reverse=desc),
                  f"HTTP {st}, {len(vals)} items")

    # ---- C. paging: walk everything twice -------------------------------------------
    for label, extra in (("default order", {}), ("order=updated_asc", {"order": "updated_asc"})):
        items, page, shape_ok, why = [], 1, True, ""
        while True:
            st, _, body = api.get(V2, {"limit": 100, "page": page, **extra})
            if st != 200 or not isinstance(body, dict):
                shape_ok, why = False, f"page {page}: HTTP {st}"
                break
            data = body.get("data") or []
            items += data
            pages = -(-body["total"] // 100)
            want_more = page < pages
            if not (body["returned"] == len(data) and body["page"] == page and body["pages"] == pages
                    and body["has_more"] is want_more and body["next_page"] == (page + 1 if want_more else None)
                    and body["remaining_pages"] == pages - page):
                shape_ok, why = False, f"page {page}: paging fields disagree with the data"
            if not want_more or page > 30:
                break
            page += 1
        ids = [i["id"] for i in items]
        rep.check(f"walk ({label}): paging fields are consistent on every page", shape_ok, why or f"{page} pages")
        rep.check(f"walk ({label}): every procedure exactly once", len(ids) == n_all == len(set(ids)),
                  f"{len(ids)} served, {len(set(ids))} distinct, {n_all} in the database")
        if extra:
            ups = [i["updated_date"] for i in items]
            rep.check("walk (order=updated_asc): updated_date never goes back across pages", ups == sorted(ups), "")
        else:
            everything = items
    st, _, body = api.get(V2, {"limit": 100, "page": 999})
    rep.check("a page past the end is empty, not an error",
              st == 200 and body.get("data") == [] and body.get("has_more") is False, f"HTTP {st}")
    for bad in ({"limit": 101}, {"limit": 0}, {"page": 0}):
        st, _, _ = api.get(V2, bad)
        rep.check(f"{bad} is refused", st == 422, f"HTTP {st}")

    # ---- D. every item ---------------------------------------------------------------
    def bad_items(pred) -> list[str]:
        return [i.get("procedure_ref") or "?" for i in everything if pred(i)]

    def none(name: str, pred):
        bad = bad_items(pred)
        rep.check(name, not bad, f"{len(bad)} item(s): {', '.join(bad[:6])}" if bad else f"all {len(everything)}")

    none("id is a UUID", lambda i: not UUID_RE.match(str(i.get("id") or "")))
    none("procedure_ref is an INI/RSP/INL reference", lambda i: not REF_RE.match(i.get("procedure_ref") or ""))
    refs = [i.get("procedure_ref") for i in everything]
    rep.check("no procedure appears twice", len(refs) == len(set(refs)), f"{len(refs) - len(set(refs))} duplicate(s)")
    none("title is not empty", lambda i: not (i.get("title") or "").strip())
    none("resolution_type is INL / INI / RSP / OTHER", lambda i: i.get("resolution_type") not in TYPES)
    none("resolution_type agrees with the reference", lambda i: f"({i.get('resolution_type')})" not in (i.get("procedure_ref") or ""))
    none("status is one of the four", lambda i: i.get("status") not in STATUSES)
    none("adopted has an adoption date and a document date",
         lambda i: i.get("status") == "adopted" and not (i.get("adoption_date") and i.get("document_date")))
    none("not adopted has no adoption date", lambda i: i.get("status") != "adopted" and i.get("adoption_date"))
    none("oeil_url points at the procedure file", lambda i: "oeil" not in (i.get("oeil_url") or ""))
    none("public_url is a real URL", lambda i: not str(i.get("public_url") or "").startswith("https://"))
    none("creation_date and updated_date are set", lambda i: not (i.get("creation_date") and i.get("updated_date")))
    none("updated_date is not before creation_date", lambda i: (i.get("updated_date") or "") < (i.get("creation_date") or ""))
    none(f"body_txt is a document, not a label (>= {THIN_BODY} characters)", lambda i: len(i.get("body_txt") or "") < THIN_BODY)
    none("body_html is present", lambda i: len(i.get("body_html") or "") < THIN_BODY)
    none("a vote total equals for + against + abstention",
         lambda i: None not in (i.get("vote_for"), i.get("vote_against"), i.get("vote_abstention"), i.get("vote_total"))
         and i["vote_for"] + i["vote_against"] + i["vote_abstention"] != i["vote_total"])
    none("a counted vote is never three zeros", lambda i: i.get("vote_total") == 0)
    none("a procedure not adopted or rejected carries no vote",
         lambda i: i.get("status") in ("pending", "closed_without_resolution") and i.get("vote_total"))
    none("key_events is a list of dated, named events",
         lambda i: not isinstance(i.get("key_events"), list)
         or any(not (DAY_RE.match(str(e.get("date") or "")) and e.get("event_type")) for e in i["key_events"]))
    # No event is right only when OEIL's own page lists none (two objections under Rule 115
    # are like that): compare with the source rather than demand an event.
    with engine.connect() as c:
        oeil_has_events = {r[0] for r in c.execute(text(
            "SELECT o.procedure_ref FROM oeil_procedures o WHERE jsonb_array_length(o.key_events) > 0 "
            "UNION SELECT c.oeil_procedure_ref FROM legislative_carriages c "
            "WHERE json_array_length(COALESCE(c.oeil_key_events, '[]'::json)) > 0"))}
    none("no item is without events when OEIL lists some",
         lambda i: not i.get("key_events") and i.get("procedure_ref") in oeil_has_events)
    none("body_txt is not page navigation", lambda i: (i.get("body_txt") or "").lstrip().lower().startswith("select a document"))
    # Asked of OEIL, not of the procedure the text is stored under: four adopted texts were
    # filed under a procedure they only cite, so their resolutions were served as adopted
    # with the OEIL page for a body and no link to the text Brubru held (12 Oct 2026).
    with engine.connect() as c:
        text_held = {r[0] for r in c.execute(text(
            r"SELECT DISTINCT o.procedure_ref FROM oeil_procedures o "
            r"CROSS JOIN LATERAL unnest(o.text_refs) AS t "
            r"JOIN texts_adopted ta ON ta.ta_reference = "
            r"regexp_replace(t, '^T(\d+)-(\d{4})/(\d{4})$', 'P\1_TA(\3)\2') "
            r"WHERE ta.full_text IS NOT NULL"))}
    none("an adopted resolution whose adopted text Brubru holds links it and serves it",
         lambda i: i.get("status") == "adopted" and i.get("procedure_ref") in text_held
         and not (str(i.get("text_url") or "").startswith("https://")
                  and "/doceo/" in str(i.get("public_url") or "")))
    none("has_commission_followup is true, false or null", lambda i: i.get("has_commission_followup") not in (True, False, None))
    none("every item carries its own `self` link", lambda i: V2 + "/" not in str(i.get("self") or ""))
    by_status = {s: sum(1 for i in everything if i.get("status") == s) for s in STATUSES}
    db_status = {s: sql("SELECT count(*) FROM ep_resolutions WHERE status = :s", s=s) for s in STATUSES}
    rep.check("statuses served equal statuses stored", by_status == db_status, f"{by_status} vs {db_status}")

    # ---- E. the item route ------------------------------------------------------------
    sample = []
    for s in STATUSES:
        sample += [i for i in everything if i.get("status") == s][:2]
    for it in sample:
        ref = it["procedure_ref"]
        st, _, one = api.get(f"{V2}/{ref}")
        drop = ("updated_date",)  # may move between the two reads when a job runs
        same = st == 200 and all(one.get(k) == v for k, v in it.items() if k not in drop)
        diff = [k for k, v in it.items() if k not in drop and isinstance(one, dict) and one.get(k) != v]
        rep.check(f"item route equals the list for {ref} ({it['status']})", same, f"HTTP {st}; differing: {diff[:5]}")
    it = sample[0]
    st, _, one = api.get(f"{V2}/{it['id']}")
    rep.check("the item route accepts the id", st == 200 and one.get("procedure_ref") == it["procedure_ref"], f"HTTP {st}")
    st, _, one = api.get(f"{V2}/{urllib.parse.quote(it['procedure_ref'], safe='')}")
    rep.check("the item route accepts a percent-encoded reference", st == 200 and one.get("id") == it["id"], f"HTTP {st}")
    st, _, one = api.get(f"{V2}/2099/9999(INI)")
    rep.check("an unknown reference answers 404", st == 404, f"HTTP {st}")
    self_url = urllib.parse.urlparse(str(it.get("self") or "")).path
    st, _, one = api.get(self_url) if self_url else (0, {}, {})
    rep.check("an item's `self` link opens that item", st == 200 and one.get("id") == it["id"], f"HTTP {st} {self_url}")

    # ---- F. other doors to the same data ----------------------------------------------
    st, hdrs, body = api.get(V2_OLD, {"limit": 1})
    rep.check("the old path answers the same total", st == 200 and body.get("total") == n_all, f"HTTP {st}, {body.get('total')}")
    rep.check("the old path says it is deprecated and names its successor",
              "deprecation" in hdrs and "sunset" in hdrs and V2 in hdrs.get("link", ""), hdrs.get("link", ""))
    st, _, b1 = api.get(V1, {"limit": 1})
    rep.check("v1 answers the same total", st == 200 and b1.get("total") == n_all, f"HTTP {st}, {b1.get('total')}")
    _, _, b2 = total({})
    rep.check("the v2 coverage note names the v2 adopted-texts path",
              "/api/v2/parliament/plenary-adopted-texts" in (b2.get("coverage_note") or "")
              and "/api/v1/" not in (b2.get("coverage_note") or ""), (b2.get("coverage_note") or "")[-110:])
    rep.check("the v1 coverage note names the v1 path", "/api/v1/texts-adopted" in (b1.get("coverage_note") or ""), "")
    note = b2.get("coverage_note") or ""
    counts = {s: db_status[s] for s in ("pending", "closed_without_resolution", "rejected")}
    rep.check("the coverage note's counts equal the database",
              all(f"{n} are `{s}`" in note for s, n in counts.items()), str(counts))
    st, _, _ = api.get(V2, {"limit": 1}, key=False)
    rep.check("no key is refused", st in (401, 403), f"HTTP {st}")
    st, hdrs, raw = api.get(V2, {"limit": 5, "format": "csv"})
    lines = raw.decode("utf-8-sig", "replace").splitlines() if isinstance(raw, (bytes, bytearray)) else []
    rep.check("format=csv returns a CSV with a header and rows",
              st == 200 and "csv" in hdrs.get("content-type", "") and len(lines) >= 2 and "procedure_ref" in lines[0],
              f"HTTP {st} {hdrs.get('content-type')}, {len(lines)} line(s)")

    # ---- report ------------------------------------------------------------------------
    failed = rep.failed()
    for ok, name, detail in rep.rows:
        if args.verbose or not ok:
            print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    where = "this checkout, in process" if args.in_process else "production"
    print(f"[{'OK' if not failed else 'ERROR'}] {len(rep.rows) - len(failed)} of {len(rep.rows)} checks pass on {where}; "
          f"{api.calls} calls, slowest {api.slowest[0]:.1f}s ({api.slowest[1][:70]})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

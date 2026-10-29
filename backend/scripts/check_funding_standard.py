"""
Live conformance check of the funding standard (Phase 2 step 7, 29 Oct 2026; proposal of 23 Oct 2026, §5-§6).

Reads the deployed route table (/api/v2/openapi.json), then calls every funding list on the API with
small pages and checks what the payload says, item by item:

  defaults     no limit gives at most 50 items and `limit` 50; limit=200 is accepted, one above the
               list's maximum is refused; bodies are on by default and off with include_body=false
  datapoints   every item: id, self (on this host), public_url (http), updated_date; creation_date
               never after updated_date
  shared       every item carries item_type, title, summary, status, body_code, body_name, amount_eur
               (null where it has no such thing); status in its item type's vocabulary; amount_eur a number
  self         the first item's self opens it (same id)
  parameters   an unknown parameter is listed in ignored_parameters; a bad order is refused;
               min_amount_eur admits only items at least that large; updated_from admits only items
               changed since
  every list   the standard's parameters (q, page, limit, include_body, the three windows, order),
               except where a rule says otherwise (EXEMPT)

No LLM, read only. Bodies are read on 2 items per list; the document lists (/documents) are left out
(their bodies are whole files). Prints one line per list and exits 1 if any rule fails that no
open register item (KNOWN) covers.

Run: BRUBRU_API_KEY=... python3.12 scripts/check_funding_standard.py [--base URL] [--only erdf,tenders]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

BASE = "https://brubru-production.up.railway.app"
PREFIX = "/api/v2/funding/"
SHARED = ("item_type", "title", "summary", "status", "body_code", "body_name", "amount_eur")
EVERY_LIST = ("q", "page", "limit", "include_body", "updated_from", "updated_to", "published_from", "published_to",
              "created_from", "created_to", "order")
# Lists a rule exempts from parameters of EVERY_LIST: why, and which.
EXEMPT = {
    "programmes": ({"updated_from", "updated_to", "published_from", "published_to", "created_from", "created_to", "order"},
                   "Victor 28 Oct: the EC's static programme taxonomy has no date, status, deadline or country per item"),
}
# The standard's status words per item type (§6); null is allowed where an item has no status.
STATUSES = {
    "tender": {"forthcoming", "open", "closed", "cancelled", "unknown"},
    "tender_award": {"closed"},
    "grant": {"forthcoming", "open", "closed", "cancelled", "unknown"},
    "eoi_call": {"forthcoming", "open", "closed", "cancelled", "unknown"},
    "startup_funding": {"forthcoming", "open", "closed", "cancelled", "unknown"},
    "cascade_call": {"forthcoming", "open", "closed", "cancelled", "unknown"},
    "call": {"forthcoming", "open", "closed", "cancelled", "unknown"},
    "funded_project": {"planned", "ongoing", "ended", "terminated", "suspended"},
    "cohesion_allocation": {"adopted", "proposed"},
    "solidarity_case": {"accepted", "rejected", "withdrawn", "under_assessment"},
}
# Open register items (docs/data_quality/problem_register.md): their failures print as KNOWN, not FAIL,
# until Victor decides. list slug -> (register id, the rules it covers).
KNOWN = {"partners": ("O103", {"every list"})}
# The figure a list's amount range compares, where it is not the item's amount_eur (as its description says).
AMOUNT_OF = {
    # the organisation's EU contribution plus its payments over the matches (O103: amount_eur is the payments alone)
    "partners": lambda i: (None if i.get("eu_contribution") is None and i.get("amount_eur") is None
                           else (i.get("eu_contribution") or 0) + (i.get("amount_eur") or 0)),
}
# Lists that need a parameter to answer at all: every call to them carries it.
REQUIRED = {"partners": {"q": "hydrogen"}}   # a partner search over every organisation is not served
# Lists that keep a larger maximum page until the legacy date (GovClipping's endpoints, §8).
MAX_LIMIT = {"ft-calls-for-proposals": 500, "ft-calls-for-tenders": 500}


class Api:
    def __init__(self, base: str, key: str):
        self.base, self.key, self.calls = base.rstrip("/"), key, 0

    def get(self, path: str, **params):
        if path.startswith(PREFIX) and path[len(PREFIX):] in REQUIRED:
            params = {**REQUIRED[path[len(PREFIX):]], **params}
        url = path if path.startswith("http") else self.base + path
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"X-API-Key": self.key, "X-Brubru-Probe": "funding-conformance"})
        self.calls += 1
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    return r.status, json.load(r)
            except urllib.error.HTTPError as e:
                if e.code in (502, 503, 504) and attempt < 2:
                    time.sleep(5)
                    continue
                try:
                    return e.code, json.load(e)
                except Exception:
                    return e.code, None
        return None, None


def _day(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def check_list(api: Api, path: str, op: dict) -> list:
    """The rules for one list: a list of (rule, what failed)."""
    slug = path[len(PREFIX):]
    names = {p["name"] for p in op.get("parameters", [])}
    out = []
    exempt, _why = EXEMPT.get(slug, (set(), ""))
    for n in EVERY_LIST:
        if n not in names and n not in exempt:
            out.append(("every list", f"no `{n}` parameter"))

    status, d = api.get(path, include_body="false")
    if status != 200 or not isinstance(d, dict):
        return out + [("defaults", f"HTTP {status} without parameters")]
    items = d.get("data") or []
    if d.get("limit") != 50 or len(items) > 50:
        out.append(("defaults", f"default limit {d.get('limit')}, {len(items)} items"))
    for i in items:
        for f in ("id", "self", "public_url", "updated_date"):
            if i.get(f) in (None, ""):
                out.append(("datapoints", f"{f} null on {i.get('id')}"))
        if i.get("self") and not str(i["self"]).startswith(api.base):
            out.append(("datapoints", f"self off this host: {i['self'][:80]}"))
        if i.get("public_url") and not str(i["public_url"]).startswith("http"):
            out.append(("datapoints", f"public_url not a URL on {i.get('id')}"))
        c, u = _day(i.get("creation_date")), _day(i.get("updated_date"))
        if c and u and c > u:
            out.append(("datapoints", f"creation_date after updated_date on {i.get('id')}"))
        for f in SHARED:
            if f not in i:
                out.append(("shared", f"no `{f}` on {i.get('id')}"))
        words = STATUSES.get(i.get("item_type"))
        if i.get("status") is not None and words is not None and i["status"] not in words:
            out.append(("shared", f"status {i['status']!r} outside {i.get('item_type')}'s words on {i.get('id')}"))
        if i.get("amount_eur") is not None and not isinstance(i["amount_eur"], (int, float)):
            out.append(("shared", f"amount_eur not a number on {i.get('id')}"))
    if items and items[0].get("self"):
        s, one = api.get(items[0]["self"], include_body="false")
        got = (one or {}).get("data", one) if isinstance(one, dict) else None
        if s != 200 or not isinstance(got, dict) or str(got.get("id")) != str(items[0].get("id")):
            out.append(("self", f"{items[0]['self'][:90]} -> HTTP {s}"))

    s, d2 = api.get(path, limit=2)
    if s == 200 and (d2 or {}).get("data") and not any((i.get("body_txt") or i.get("body_html")) for i in d2["data"]):
        out.append(("defaults", "bodies off by default (no body on the first 2 items)"))
    if any(i.get("body_txt") or i.get("body_html") for i in items):
        out.append(("defaults", "include_body=false left a body on"))
    s, _ = api.get(path, limit=200, include_body="false")
    if s != 200:
        out.append(("defaults", f"limit=200 -> HTTP {s}"))
    top = MAX_LIMIT.get(slug, 200)
    s, _ = api.get(path, limit=top + 1, include_body="false")
    if s not in (400, 422):
        out.append(("defaults", f"limit={top + 1} -> HTTP {s}, not refused"))

    s, d3 = api.get(path, limit=1, include_body="false", zz_unknown_parameter="1")
    if s != 200 or "zz_unknown_parameter" not in ((d3 or {}).get("ignored_parameters") or []):
        out.append(("parameters", f"unknown parameter not reported (HTTP {s})"))
    if "order" in names:
        s, _ = api.get(path, limit=1, include_body="false", order="zz_not_an_order")
        if s not in (400, 422):
            out.append(("parameters", f"a bad order -> HTTP {s}, not refused"))
    if "min_amount_eur" in names:
        figure = AMOUNT_OF.get(slug, lambda i: i.get("amount_eur"))
        amounts = [figure(i) for i in items if isinstance(figure(i), (int, float))]
        if amounts:
            floor = sorted(amounts)[len(amounts) // 2]
            s, d4 = api.get(path, limit=50, include_body="false", min_amount_eur=floor)
            bad = [i.get("id") for i in (d4 or {}).get("data", []) if not isinstance(figure(i), (int, float)) or figure(i) < floor]
            if s != 200 or bad:
                out.append(("parameters", f"min_amount_eur={floor} admitted {bad[:3]} (HTTP {s})"))
    if "updated_from" in names and items:
        days = sorted(filter(None, (_day(i.get("updated_date")) for i in items)))
        if days:
            since = days[len(days) // 2]
            s, d5 = api.get(path, limit=50, include_body="false", updated_from=since.isoformat())
            bad = [i.get("id") for i in (d5 or {}).get("data", []) if (_day(i.get("updated_date")) or since) < since]
            if s != 200 or bad:
                out.append(("parameters", f"updated_from={since.isoformat()} admitted {bad[:3]} (HTTP {s})"))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default=BASE)
    ap.add_argument("--only", default="", help="comma list of list slugs (erdf,tenders); default every list")
    args = ap.parse_args(argv)
    key = os.environ.get("BRUBRU_API_KEY", "").strip()
    if not key:
        print("[FATAL] BRUBRU_API_KEY missing")
        return 1
    api = Api(args.base, key)
    s, spec = api.get("/api/v2/openapi.json")
    if s != 200 or not isinstance(spec, dict):
        print(f"[FATAL] route table: HTTP {s}")
        return 1
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    lists = sorted(p for p, ops in spec["paths"].items()
                   if p.startswith(PREFIX) and "get" in ops and not p.endswith("}") and not p.endswith("/documents")
                   and (not only or p[len(PREFIX):] in only))
    failed = known = 0
    for path in lists:
        slug = path[len(PREFIX):]
        problems = check_list(api, path, spec["paths"][path]["get"])
        ref, rules = KNOWN.get(slug, (None, set()))
        open_ = [p for p in problems if p[0] not in rules]
        failed += bool(open_)
        known += bool(problems) and not open_
        print(f"[{'FAIL' if open_ else 'KNOWN' if problems else 'OK'}] {slug}" + (f" ({ref})" if problems and not open_ else ""))
        for rule, what in problems[:8]:
            print(f"       {rule}: {what}" + (f"  [known: {ref}]" if rule in rules else ""))
        if len(problems) > 8:
            print(f"       ... {len(problems) - 8} more")
    print(f"[DONE] lists={len(lists)} failing={failed} known={known} calls={api.calls}"
          + "".join(f"\n[INFO] {k} exempt from {sorted(v[0])}: {v[1]}" for k, v in EXEMPT.items()))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

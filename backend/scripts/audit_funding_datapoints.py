"""
Audit of what the funding lists SERVE, value by value (Victor, 30 Oct 2026: "check out on the output of
the new funding/ endpoints and analyse it properly, auditing every single datapoint, especially the 5
canonical datapoints. This should be something that you have to do continuously").

scripts/check_funding_standard.py says whether each list keeps the standard's shape (parameters,
defaults, fields present). This reads the values: on a small page of every list from the deployed
route table (the default order, then the oldest items, bodies on), it judges

  public_url     present, an absolute http(s) address, not one address for several items (a listing),
                 not a site's home page
  body_txt/html  both present, not a stub (< 200 characters), not the title or summary again, no
                 cookie banner or "enable JavaScript" text, no mojibake, the two of a similar length
  document_date  present, not in the future, not before 1990, not one batch stamp for many items
  creation_date  present, not in the future, not after updated_date
  updated_date   present, with a time zone
  self           present, on this host; two items per list opened and compared on id and the dates
  id             present, unique on the page
  every field    how many items of the page leave it empty (a field empty on every item is listed)

No LLM, read only, small pages (egress: never a walk of the API). Prints one block per list with its
findings and exits 1 if any list has one that no open register item explains (KNOWN).

Run: BRUBRU_API_KEY=... python3.12 scripts/audit_funding_datapoints.py [--only budgets,awards] [--json out.json]
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import os
import pathlib
import re
import statistics
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.check_funding_standard import BASE, PREFIX, Api  # noqa: E402

PAGE, OLDEST = 15, 5
DATAPOINTS = ("public_url", "body_txt", "body_html", "document_date", "creation_date", "updated_date", "self", "id")
STUB = 200
BANNER = re.compile(r"(?i)accept (all )?cookies|we use cookies|enable javascript|javascript is disabled|"
                    r"this site uses cookies|cookie (policy|settings)")
MOJIBAKE = re.compile("�|Ã[\u0080-¿]|â€")
TAG = re.compile(r"<[^>]+>")
# Findings an open register item explains (they print as KNOWN, not FAIL): (list slug or "*", code) -> id.
_CALLS = ("ft-calls-for-proposals", "funding-opportunities", "opportunities", "startups")
KNOWN = {("*", "naive_datetime"): "O106", ("partners", "self"): "O103",
         **{(s, "document_date_in_future"): "O95" for s in _CALLS},
         **{("euda-tenders", c): "O99" for c in ("public_url_home_page", "body_txt_stub_under_200", "document_date_missing")}}
# Findings that are what the list says it serves (documented in its description): (slug, code) -> why.
_FUNDS = ("erdf", "esf-plus", "cohesion-fund", "jtf", "interreg", "emfaf", "amif", "isf")
_ROWS = ("eagf", "eafrd", "eusf", "budgets")
BY_DESIGN = {
    **{(s, "public_url_shared_by_3_or_more"): "a programme's rows share its programme page (no page per row at the source)"
       for s in _FUNDS + tuple(f"{f}/outcomes" for f in _FUNDS) + ("budgets",)},
    **{(s, "public_url_shared_by_3_or_more"): "the fund's page: the source publishes no page per country or case" for s in _ROWS},
    **{(s, "body_txt_stub_under_200"): "a row of figures: its body is composed from the row's own fields" for s in _ROWS},
    ("eusf", "document_date_one_stamp_for_many"): "the dataset's last refresh, the only date the source gives (documented)",
    ("interreg", "document_date_missing"): "the source states no date for Interreg programmes (O40)",
    ("ft-events", "document_date_in_future"): "an event is dated by its start (documented)",
    ("programmes", "public_url_home_page"): "a programme's own site",
}


def _ref(table: dict, slug: str, code: str):
    return table.get((slug, code)) or table.get(("*", code))


def _when(value):
    if not value:
        return None, False
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None, False
    aware = d.tzinfo is not None
    return (d if aware else d.replace(tzinfo=timezone.utc)), aware


def _text(value) -> str:
    return " ".join(str(value or "").split())


def audit_items(items: list, now: datetime, with_body: bool = True) -> tuple[Counter, dict]:
    """Findings over one page: Counter code -> items, and examples code -> first ids. Pure: unit-tested."""
    found, examples = Counter(), {}

    def flag(code, item):
        found[code] += 1
        examples.setdefault(code, [])
        if len(examples[code]) < 3:
            examples[code].append(str(item.get("id")))

    urls = Counter(i.get("public_url") for i in items if i.get("public_url"))
    ids = Counter(str(i.get("id")) for i in items if i.get("id") is not None)
    # A stamp on the hour (00:00, 01:00Z) is a day in some time zone: many items of one day share it.
    stamps = Counter(i.get("document_date") for i in items if i.get("document_date") and "T" in str(i.get("document_date"))
                     and str(i.get("document_date")).split("T")[1][2:8] not in (":00:00", ":00:00Z", ":00:00+"))
    for i in items:
        url = i.get("public_url")
        if not url:
            flag("public_url_missing", i)
        else:
            p = urlparse(str(url))
            if p.scheme not in ("http", "https") or not p.netloc:
                flag("public_url_not_absolute", i)
            elif p.path in ("", "/") and not p.query:
                flag("public_url_home_page", i)
            if urls[url] >= 3:
                flag("public_url_shared_by_3_or_more", i)
        if i.get("id") is None:
            flag("id_missing", i)
        elif ids[str(i.get("id"))] > 1:
            flag("id_repeated_on_page", i)
        if not i.get("self"):
            flag("self_missing", i)
        if with_body:
            txt, htm = i.get("body_txt"), i.get("body_html")
            if not txt:
                flag("body_txt_missing", i)
            if not htm:
                flag("body_html_missing", i)
            if txt:
                t = _text(txt)
                if len(t) < STUB:
                    flag("body_txt_stub_under_200", i)
                if t and t in {_text(i.get("title")), _text(i.get("summary")),
                               _text(f"{i.get('title') or ''} {i.get('summary') or ''}")}:
                    flag("body_is_title_or_summary", i)
                if BANNER.search(t):
                    flag("body_banner_or_javascript_text", i)
                if MOJIBAKE.search(t):
                    flag("body_mojibake", i)
                if htm:
                    h = _text(html_lib.unescape(TAG.sub(" ", str(htm))))
                    if h and not (0.5 <= len(h) / max(len(t), 1) <= 2.0):
                        flag("body_txt_and_html_differ_in_length", i)
        doc, _ = _when(i.get("document_date"))
        if i.get("document_date") in (None, ""):
            flag("document_date_missing", i)
        elif doc is None:
            flag("document_date_unreadable", i)
        else:
            if doc > now + timedelta(days=1):
                flag("document_date_in_future", i)
            if doc.year < 1990:
                flag("document_date_before_1990", i)
            if stamps[i.get("document_date")] >= max(5, len(items) * 0.3):
                flag("document_date_one_stamp_for_many", i)
        created, c_aware = _when(i.get("creation_date"))
        updated, u_aware = _when(i.get("updated_date"))
        if i.get("creation_date") in (None, ""):
            flag("creation_date_missing", i)
        elif created and created > now + timedelta(minutes=5):
            flag("creation_date_in_future", i)
        if i.get("updated_date") in (None, ""):
            flag("updated_date_missing", i)
        if created and updated and created > updated + timedelta(seconds=1):
            flag("creation_after_updated", i)
        if (i.get("creation_date") and not c_aware and "T" in str(i.get("creation_date"))) or \
           (i.get("updated_date") and not u_aware and "T" in str(i.get("updated_date"))):
            flag("naive_datetime", i)
    return found, examples


def empty_fields(items: list, with_body: bool = True) -> list:
    """Fields every item of the page leaves empty (None, '' or [])."""
    keys = {k for i in items for k in i}
    if not with_body:
        keys -= {"body_txt", "body_html"}
    return sorted(k for k in keys if all(i.get(k) in (None, "", []) for i in items))


def body_lengths(items: list) -> tuple:
    lens = [len(_text(i.get("body_txt"))) for i in items if i.get("body_txt")]
    return (min(lens), int(statistics.median(lens)), max(lens)) if lens else (0, 0, 0)


def self_check(api: Api, items: list) -> list:
    """Open the first two items' `self`: same id and the same datapoints."""
    out = []
    for i in items[:2]:
        if not i.get("self"):
            continue
        s, own = api.get(i["self"], include_body="false")
        if s != 200 or not isinstance(own, dict):
            out.append(f"self of {i.get('id')} answered HTTP {s}")
            continue
        own = own.get("data", own) if "data" in own and isinstance(own.get("data"), dict) else own
        for k in ("id", "public_url", "document_date", "creation_date", "updated_date"):
            if k in own and str(own.get(k)) != str(i.get(k)):
                out.append(f"self of {i.get('id')}: {k} differs ({str(i.get(k))[:40]} vs {str(own.get(k))[:40]})")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default=BASE)
    ap.add_argument("--only", default="", help="comma-separated list slugs (e.g. budgets,awards)")
    ap.add_argument("--json", default=None, help="write the full findings here")
    args = ap.parse_args()
    key = os.environ.get("BRUBRU_API_KEY")
    if not key:
        print("[FATAL] BRUBRU_API_KEY is not set")
        return 2
    api = Api(args.base, key)
    s, spec = api.get("/api/v2/openapi.json")
    if s != 200:
        print(f"[FATAL] route table: HTTP {s}")
        return 1
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    lists = sorted(p for p, ops in spec["paths"].items()
                   if p.startswith(PREFIX) and "get" in ops and not p.endswith("}") and not p.endswith("/documents")
                   and (not only or p[len(PREFIX):] in only))
    now = datetime.now(timezone.utc)
    report, failing, known = {}, 0, 0
    for path in lists:
        slug = path[len(PREFIX):]
        order_doc = " ".join(str(p.get("description") or "") for p in spec["paths"][path]["get"].get("parameters", [])
                             if p.get("name") == "order")
        s, d = api.get(path, limit=PAGE)
        if s != 200 or not isinstance(d, dict):
            print(f"[FAIL] {slug}: HTTP {s}")
            failing += 1
            report[slug] = {"http": s}
            continue
        items = list(d.get("data") or [])
        total = d.get("total")
        if "oldest" in order_doc:
            s2, d2 = api.get(path, limit=OLDEST, order="oldest")
            if s2 == 200 and isinstance(d2, dict):
                items += [i for i in (d2.get("data") or []) if str(i.get("id")) not in {str(x.get("id")) for x in items}]
        found, examples = audit_items(items, now)
        selfs = self_check(api, items)
        empty = empty_fields(items)
        lo, med, hi = body_lengths(items)
        open_ = {c: n for c, n in found.items() if not _ref(KNOWN, slug, c) and not _ref(BY_DESIGN, slug, c)}
        selfs_open = [x for x in selfs if not _ref(KNOWN, slug, "self")]
        tag = "FAIL" if (open_ or selfs_open) else "KNOWN" if (found or selfs) else "OK"
        failing += tag == "FAIL"
        known += tag == "KNOWN"
        print(f"[{tag}] {slug}: total {total}, read {len(items)}, body chars min/median/max {lo}/{med}/{hi}")
        for code, n in sorted(found.items(), key=lambda x: -x[1]):
            known_ref, why = _ref(KNOWN, slug, code), _ref(BY_DESIGN, slug, code)
            ref = f"  [known: {known_ref}]" if known_ref else f"  [by design: {why}]" if why else ""
            print(f"       {code}: {n} of {len(items)} (e.g. {', '.join(examples[code])}){ref}")
        for line in selfs:
            print(f"       {line}" + (f"  [known: {_ref(KNOWN, slug, 'self')}]" if _ref(KNOWN, slug, "self") else ""))
        if empty:
            print(f"       empty on every item read: {', '.join(empty)}")
        report[slug] = {"total": total, "read": len(items), "findings": dict(found), "examples": examples,
                        "self": selfs, "empty_fields": empty, "body_chars": [lo, med, hi]}
    print(f"[DONE] lists={len(lists)} failing={failing} known={known} calls={api.calls}")
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps({"at": now.isoformat(), "base": args.base, "lists": report}, indent=1))
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())

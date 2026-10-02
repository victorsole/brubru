#!/usr/bin/env python3.12
"""Walk one /api/v2 endpoint page by page, both windows, and report what a client sees.

Every page and every row, never a sample: a page-1 sample hid a real defect twice.
Reports duplicates, empty vs ABSENT datapoints (absent = missing from the payload, which
breaks the contract and is worse than null), and the body-length distribution.

    python3.12 scripts/audit_endpoint_walk.py /api/v2/commission/tris-notifications
    python3.12 scripts/audit_endpoint_walk.py /api/v2/parliament/votes --full-scan
"""
from __future__ import annotations

import argparse, collections, json, pathlib, re, sys, time, urllib.request

ENV = pathlib.Path(__file__).resolve().parents[1] / ".env"
BASE = "https://brubru-production.up.railway.app"
FIELDS = ("public_url", "body_txt", "body_html", "document_date", "creation_date", "updated_date")
WINDOWS = [("SCHEDULED", "updated_from=2026-09-27T05:05:01Z"),
           ("BACKFILL", "updated_from=2024-07-15T19:00:00Z")]


def _key() -> str:
    m = re.search(r"^BRUBRU_API_KEY=(.*)$", ENV.read_text(), re.M)
    if not m:
        raise SystemExit("[ERROR] BRUBRU_API_KEY missing from backend/.env")
    return m.group(1).strip()


def _get(path: str, key: str) -> dict:
    req = urllib.request.Request(BASE + path, headers={
        "Authorization": f"Bearer {key}", "Accept": "application/json",
        "User-Agent": "GovClipping-cron_new/2.0", "X-Brubru-Probe": "audit-walk"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--full-scan", action="store_true", help="no date params; one window")
    ap.add_argument("--save-urls", help="write the distinct public_urls to this file")
    a = ap.parse_args()
    key = _key()
    windows = [("FULL", "")] if a.full_scan else WINDOWS
    urls: set[str] = set()
    rc = 0
    print(f"=== {a.path}", flush=True)
    for name, qs in windows:
        page, n, ids, dup, total = 1, 0, set(), 0, None
        empty, absent, bodies = collections.Counter(), collections.Counter(), []
        t0 = time.time()
        while True:
            sep = "&" if qs else ""
            d = _get(f"{a.path}?{qs}{sep}page={page}&limit=100", key)
            total = d.get("total")
            items = d.get("data") or d.get("items") or []
            for it in items:
                n += 1
                i = str(it.get("id") if it.get("id") is not None else it.get("self"))
                dup += i in ids
                ids.add(i)
                for f in FIELDS:
                    if f not in it:
                        absent[f] += 1
                    elif not it[f]:
                        empty[f] += 1
                bodies.append(len(it.get("body_txt") or ""))
                if it.get("public_url"):
                    urls.add(it["public_url"])
            if not d.get("has_more") or page > 1500:
                break
            page += 1
        nz = sorted(b for b in bodies if b)
        fmt = lambda c: "  ".join(f"{k}={v}" for k, v in sorted(c.items())) or "none"
        print(f"  {name:<9} total={total} walked={n} pages={page} distinct={len(ids)} "
              f"dup={dup} ({time.time()-t0:.0f}s)")
        print(f"            EMPTY : {fmt(empty)}")
        print(f"            ABSENT: {fmt(absent)}")
        if nz:
            print(f"            body_txt n={len(nz)}/{n} min={nz[0]} median={nz[len(nz)//2]} "
                  f"max={nz[-1]} under400={sum(b < 400 for b in nz)}")
        else:
            print(f"            body_txt: none of {n} rows carry a body")
        if n == 0 and total:
            rc = 1
    if a.save_urls:
        pathlib.Path(a.save_urls).write_text(json.dumps(sorted(urls)))
        print(f"  [{len(urls)} distinct urls saved to {a.save_urls}]")
    return rc


if __name__ == "__main__":
    sys.exit(main())

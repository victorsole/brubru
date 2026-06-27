"""Estate-wide diagnostic scan of the EU web estate referenced by docs/api/api_*.md.

Fast pass: every URL fetched once via requests (concurrent), characterised, and — for
listing-type pages — run through the extraction handlers to score quality. Browser-only
pages are flagged (needs_browser) for a separate slower pass. Results stream to JSONL so
the run can be monitored and aggregated incrementally.

This is the data behind docs/api/extract_engine_issues.md and the public report.
Run:  PYTHONPATH=. python3.12 scripts/extract_estate_scan.py [--limit N] [--out PATH]
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import glob
import json
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

from services.extract import classifier, handlers

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
_URL = re.compile(r"https?://[^\s)\"'>\`\]]+")
_LISTING = re.compile(r"/(news|events?|publications?|press|consultations?|newsroom|media|"
                      r"calendar|meetings?|documents?|reports?|tenders?|funding|calls?)\b", re.I)
_CHALLENGE = ("/challenge", "/cdn-cgi", "just a moment", "enable javascript", "are you human",
              "/sorry", "anubis", "making sure you're not a bot")
_MOJI = re.compile(r"Ã©|Ã¨|â\x80|â€™|�")
_JUNK = re.compile(r"^(subscribe|register$|registration$|read more|see all|themes in focus|"
                   r"search page|home|menu|news$|events$|publications$|filter by|go to|overview)\b", re.I)


def mine_urls() -> list[str]:
    urls = set()
    for f in sorted(glob.glob("../docs/api/api_*.md")) or sorted(glob.glob("docs/api/api_*.md")):
        for m in _URL.findall(open(f, encoding="utf-8", errors="ignore").read()):
            u = m.rstrip(".,;:)]`*\"'")
            if any(k in u for k in ("europa.eu", "europarl", "consilium")):
                urls.add(u)
    return sorted(urls)


def kind(u: str) -> str:
    low = u.lower()
    if low.endswith((".pdf", ".xml", ".json", ".csv", ".zip", ".xlsx", ".doc", ".docx")):
        return "file"
    if "/api/" in low or "sparql" in low or "/rest/" in low or "webapi" in low:
        return "api"
    if _LISTING.search(u):
        return "listing"
    return "detail"


def scan_one(u: str) -> dict:
    rec = {"url": u, "domain": u.split("/")[2] if "://" in u else "?", "kind": kind(u)}
    t0 = time.time()
    try:
        r = requests.get(u, headers={"User-Agent": _UA}, timeout=25, allow_redirects=True)
    except requests.RequestException as e:
        rec.update(status="ERR", err=type(e).__name__, ms=int((time.time() - t0) * 1000))
        return rec
    ct = r.headers.get("content-type", "").split(";")[0]
    if "charset=" not in r.headers.get("content-type", "").lower():
        r.encoding = r.apparent_encoding or "utf-8"
    body = r.text if "html" in ct else ""
    challenged = any(c in (r.url + " " + body[:3000]).lower() for c in _CHALLENGE)
    rec.update(status=r.status_code, ctype=ct, final=r.url, bytes=len(r.content),
               ms=int((time.time() - t0) * 1000), challenged=challenged)
    if r.status_code != 200 or not body or challenged:
        rec["needs_browser"] = (r.status_code == 200 and (challenged or not body))
        return rec
    try:
        plat, _, _ = classifier.classify(u, body)
    except Exception:
        plat = "?"
    rec["platform"] = plat
    if rec["kind"] == "listing":
        try:
            items = handlers.parse(plat, body, u, item_type="news", limit=12)
        except Exception as e:
            rec.update(parse_err=type(e).__name__)
            return rec
        n = len(items)
        titles = [it.title or "" for it in items]
        urls_seen = [it.public_url for it in items if it.public_url]
        rec.update(
            n=n,
            date_cov=round(100 * sum(1 for it in items if it.document_date) / n) if n else 0,
            dup=len(urls_seen) - len(set(urls_seen)),
            junk=sum(1 for t in titles if _JUNK.match(t.strip())),
            moji=sum(1 for t in titles if _MOJI.search(t)),
            short=sum(1 for t in titles if len(t) < 15),
            no_url=sum(1 for it in items if not it.public_url),
            needs_browser=(n == 0),  # requests yielded an HTML page but no items
        )
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--out", default="/private/tmp/claude-501/-Users-victorsole-Documents-GitHub-brubru/467dde5d-b102-4717-9258-3805a4ea37f8/scratchpad/estate_scan.jsonl")
    a = ap.parse_args()
    urls = mine_urls()
    if a.limit:
        urls = urls[:a.limit]
    print(f"[scan] {len(urls)} URLs, {a.workers} workers -> {a.out}", flush=True)
    done = 0
    with open(a.out, "w") as fh, cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for rec in ex.map(scan_one, urls):
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            done += 1
            if done % 250 == 0:
                print(f"[scan] {done}/{len(urls)}", flush=True)
    print(f"[scan] complete: {done} URLs", flush=True)


if __name__ == "__main__":
    main()

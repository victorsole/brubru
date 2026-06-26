"""
Phase 0 golden-URL probe for the EU extract engine.

Characterises every golden URL BEFORE any handler is built, so the golden set is
known-good and each URL's behaviour is on record:
  - reachable via plain requests, or does it 403 / hit a /challenge / need a browser?
  - how many candidate items are in the *server* HTML (0 ⇒ JS-rendered ⇒ browser)?
  - is it stable across repeated passes (flapping item counts = a problem)?

Run it several passes per URL ("test them a lot"). It does NOT extract structured
items yet (that's Phase 1); it validates the substrate the rig will stand on, and
saves the last good HTML to fixtures/ for the Phase-1 handlers to regress against.

Usage:  python3.12 tests/extract_engine/probe_golden.py [--passes 4] [--pace 1.5]
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

_HERE = Path(__file__).resolve().parent
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
# Broad candidate selectors across platform types — we only count, not extract.
_CANDIDATE = [".ecl-content-item", ".teaser", ".card", ".views-row", "article",
              ".node", ".list-item", ".result", ".search-result"]
_CHALLENGE = re.compile(r"/challenge|/sorry|/cdn-cgi|just a moment|/login|enable javascript", re.I)


def _slug(url: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", url.lower()).strip("_")[:60]


def _candidates(html: str) -> int:
    soup = BeautifulSoup(html, "html.parser")
    counts = [len(soup.select(sel)) for sel in _CANDIDATE]
    # also count news/event/publication anchors as a fallback signal
    anchors = len([a for a in soup.select("a[href]")
                   if re.search(r"/(news|events?|publications?|press|media)/", a.get("href", ""), re.I)])
    return max(counts + [anchors])


def probe_one(url: str, *, passes: int, pace: float) -> dict:
    s = requests.Session()
    s.headers.update({"User-Agent": _UA})
    results = []
    last_good = None
    for i in range(passes):
        rec = {"status": None, "challenge": False, "len": 0, "items": 0, "err": None}
        try:
            r = s.get(url, timeout=30, allow_redirects=True)
            rec["status"] = r.status_code
            rec["challenge"] = bool(_CHALLENGE.search(r.url) or _CHALLENGE.search(r.text[:2000]))
            rec["len"] = len(r.text)
            if r.status_code == 200 and not rec["challenge"]:
                rec["items"] = _candidates(r.text)
                last_good = r.text
        except requests.RequestException as e:
            rec["err"] = type(e).__name__
        results.append(rec)
        time.sleep(pace)
    item_counts = [r["items"] for r in results if r["status"] == 200 and not r["challenge"]]
    ok = sum(1 for r in results if r["status"] == 200 and not r["challenge"])
    if ok == 0:
        verdict = "NEEDS_BROWSER"  # 403 / challenge / always errored
    elif item_counts and max(item_counts) == 0:
        verdict = "NEEDS_BROWSER"  # reachable but no items in server HTML ⇒ JS-rendered
    elif len(set(item_counts)) > 1:
        verdict = "FLAKY"          # item count varies across passes
    else:
        verdict = "OK_REQUESTS"
    if last_good:
        (_HERE / "fixtures" / f"{_slug(url)}.html").write_text(last_good, encoding="utf-8")
    return {"url": url, "verdict": verdict, "ok_passes": f"{ok}/{passes}",
            "items": item_counts[0] if item_counts else 0,
            "statuses": [r["status"] for r in results],
            "challenge": any(r["challenge"] for r in results)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--passes", type=int, default=4)
    ap.add_argument("--pace", type=float, default=1.5)
    args = ap.parse_args()
    golden = json.loads((_HERE / "golden_urls.json").read_text())
    print(f"Probing {sum(len(v) for v in golden.values())} golden URLs, {args.passes} passes each\n")
    summary = {}
    for platform, urls in golden.items():
        print(f"=== {platform} ===")
        for url in urls:
            res = probe_one(url, passes=args.passes, pace=args.pace)
            summary[res["verdict"]] = summary.get(res["verdict"], 0) + 1
            tag = {"OK_REQUESTS": "[OK]", "NEEDS_BROWSER": "[BROWSER]", "FLAKY": "[FLAKY]"}[res["verdict"]]
            print(f"  {tag:10s} items={res['items']:<4d} ok={res['ok_passes']} "
                  f"status={res['statuses']} chal={res['challenge']}  {url}")
            time.sleep(args.pace)
    print(f"\nSUMMARY: {summary}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3.12
"""Is Brubru's EIC knowledge behind the EIC's own sources?

Why (8 Oct 2026): the EIC guides and Tender Docs templates were written on 16-17
June 2026 and never revisited. The Work Programme was amended that same week
(dual-use, a new STEP Scale Up Defence call), the official application forms were
re-issued on 12 June and 9 July, and new EIC Fund Investment Guidelines followed
on 27 August. Production chat then gave wrong EIC answers for months. This check
compares what we last verified (data/eic_call_calendar.json, "_source_versions")
with the live sources:

- the dates the EIC Accelerator page shows for the Work Programme, the Guide for
  Applicants and the full-proposal annexes, and its newest news item;
- the version stamped inside the official short and full proposal forms;
- the end dates of the 2026 Accelerator, STEP and Defence topics on the portal.

Exit 0: everything matches. Exit 1: something moved (review the guides, templates
and calendar, then run with --accept). Exit 2: a source could not be read, so the
answer is UNPROVEN, never "no change".

Usage (from backend/):
    python3.12 scripts/check_eic_sources.py
    python3.12 scripts/check_eic_sources.py --accept    # store the live values after review
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import re
import sys
from datetime import date
from pathlib import Path

import requests

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

logging.disable(logging.CRITICAL)

CALENDAR = BACKEND_DIR / "data" / "eic_call_calendar.json"
ACCELERATOR_PAGE = "https://eic.ec.europa.eu/eic-funding-opportunities/eic-accelerator_en"
FORMS = {
    "short_form_version": "https://ec.europa.eu/info/funding-tenders/opportunities/docs/2021-2027/horizon/temp-form/af/af_he-eic-accelerator-short_en.pdf",
    "full_form_version": "https://ec.europa.eu/info/funding-tenders/opportunities/docs/2021-2027/horizon/temp-form/af/af_he-eic-accelerator_en.pdf",
}
SEDIA = "https://api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey=SEDIA&text=***&pageSize=3&pageNumber=1"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0 Safari/537.36"}
DATE = r"(\d{1,2} (?:January|February|March|April|May|June|July|August|September|October|November|December) 20\d\d)"


def _page_text(url: str) -> str:
    """Plain request first; a WAF answer (202, 403, tiny body) switches to the browser fetcher."""
    try:
        r = requests.get(url, headers=UA, timeout=60)
        if r.status_code == 200 and len(r.text) > 20000:
            html = r.text
        else:
            raise RuntimeError(f"http {r.status_code}, {len(r.text)} bytes")
    except Exception:
        from services.scrapers.waf_browser_fetcher import fetch_one
        html = fetch_one(url, expand_accordions=False, strip_chrome=True).html or ""
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text).replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text)


def read_accelerator_page() -> dict:
    t = _page_text(ACCELERATOR_PAGE)
    out = {}
    for key, pattern in (
        ("wp_page_date", r"EIC Work Programme 2026 This document.{0,600}?" + DATE),
        ("guide_page_date", r"EIC Accelerator guide for applicants.{0,400}?" + DATE),
        ("annexes_page_date", r"Annexes for the EIC Accelerator full proposal.{0,500}?" + DATE),
        ("latest_news_date", r"News article\s+" + DATE),
    ):
        m = re.search(pattern, t)
        out[key] = m.group(1) if m else None
    return out


def _pdf_text(content: bytes) -> str:
    """Poppler's pdftotext first: pypdf drops the Part B headers that carry the version stamp."""
    import shutil
    import subprocess
    import tempfile
    if shutil.which("pdftotext"):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "form.pdf"
            src.write_bytes(content)
            done = subprocess.run(["pdftotext", "-layout", str(src), "-"], capture_output=True, text=True, timeout=120)
            if done.returncode == 0 and done.stdout.strip():
                return done.stdout
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(content))
    return " ".join((page.extract_text() or "") for page in reader.pages)


def read_form_version(url: str) -> str | None:
    r = requests.get(url, headers=UA, timeout=120)
    if r.status_code != 200 or not r.content.startswith(b"%PDF"):
        return None
    text = _pdf_text(r.content)
    # The Part B footer reads e.g. "...(HE EIC Accelerator stage 2 - full proposal): V2.1– 09.07.2026"
    found = re.findall(r"V ?(\d+\.\d+)\s*[–-]\s*(\d{2}\.\d{2}\.\d{4})", text)
    if not found:
        return None
    # The highest version stamped in the document is the current one.
    best = max(found, key=lambda v: (tuple(int(x) for x in v[0].split(".")), v[1][6:] + v[1][3:5] + v[1][:2]))
    return f"{best[0]} {best[1]}"


def read_portal_end_dates(topics: list[str]) -> dict:
    out = {}
    for topic in topics:
        query = {"bool": {"must": [{"terms": {"type": ["0", "1", "2", "8"]}}, {"term": {"identifier": topic}}]}}
        files = {"query": (None, json.dumps(query), "application/json"), "languages": (None, '["en"]', "application/json")}
        try:
            d = requests.post(SEDIA, files=files, headers=UA, timeout=60).json()
            md = d["results"][0]["metadata"] if d.get("results") else {}
            raw = (md.get("deadlineDate") or [None])[0]
            out[topic] = raw[:10] if raw else None
        except Exception:
            out[topic] = None
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--accept", action="store_true", help="store the live values as the new baseline")
    args = ap.parse_args()

    calendar = json.loads(CALENDAR.read_text())
    stored = calendar.get("_source_versions") or {}

    live = {}
    try:
        live.update(read_accelerator_page())
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] EIC Accelerator page unreadable: {type(exc).__name__}")
    for key, url in FORMS.items():
        try:
            live[key] = read_form_version(url)
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] {key} unreadable: {type(exc).__name__}")
            live[key] = None
    live["portal_end_dates"] = read_portal_end_dates(sorted((stored.get("portal_end_dates") or {}).keys()))

    changed, unreadable = [], []
    print(f"{'source':<40} {'stored':<22} {'live':<22} verdict")
    for key in ("wp_page_date", "guide_page_date", "annexes_page_date", "latest_news_date", "short_form_version", "full_form_version"):
        s, l = stored.get(key), live.get(key)
        verdict = "UNREADABLE" if l is None else ("OK" if l == s else "CHANGED")
        (unreadable if l is None else changed if l != s else []).append(key)
        print(f"{key:<40} {str(s):<22} {str(l):<22} {verdict}")
    for topic, s in (stored.get("portal_end_dates") or {}).items():
        l = live["portal_end_dates"].get(topic)
        verdict = "UNREADABLE" if l is None else ("OK" if l == s else "CHANGED")
        (unreadable if l is None else changed if l != s else []).append(topic)
        print(f"{'portal end ' + topic:<40} {str(s):<22} {str(l):<22} {verdict}")

    if args.accept:
        if unreadable:
            print("[ERROR] not accepting: some sources were unreadable")
            return 2
        new = dict(stored)
        new.update({k: v for k, v in live.items() if k != "portal_end_dates"})
        new["portal_end_dates"] = live["portal_end_dates"]
        new["checked_on"] = date.today().isoformat()
        calendar["_source_versions"] = new
        CALENDAR.write_text(json.dumps(calendar, ensure_ascii=False, indent=2) + "\n")
        print(f"[OK] baseline stored ({len(changed)} change(s) accepted)")
        return 0

    if unreadable:
        print(f"[UNPROVEN] {len(unreadable)} source(s) unreadable: {', '.join(unreadable)}")
        return 2
    if changed:
        print(f"[BEHIND] {len(changed)} source(s) moved: {', '.join(changed)}. Review the eic_* guides, "
              "the funding_templates/eic-*.json files and data/eic_call_calendar.json, then run --accept.")
        return 1
    print("[OK] Brubru's EIC knowledge matches the live sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

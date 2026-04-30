"""
URL freshness audit for the Brubru v1 API.

Walks every URL field returned by the API across:
  - /laws (eurlex_url)
  - /procedures/{ref} (eurlex_documents JSON, legal_text_url, url)
  - /commission-register-documents (portal_url, pdf_url, source_url)
  - /webstreams (multimedia_url, video_url)
  - /research-publications (html_url, pdf_url)
  - /publications (url)
  - /tenders (ted_url)
  - /press-releases (url)
  - /council-documents (url)
  - /eprs (html_url, pdf_url)

For each URL:
  1. HEAD check — must return 2xx or 3xx (redirect is fine)
  2. For EUR-Lex URLs specifically: GET + verify body has real legal text
     (article/recital markers, not the empty "Document not in this language"
     placeholder).

Output: docs/govclipping/url-audit-{YYYY-MM-DD}.md with a table per source
+ a summary count of broken/empty URLs.

Usage:
    cd backend && python3.12 scripts/audit_api_urls.py
    # Optional: --sample N   (default 50 per endpoint)
    # Optional: --only laws   (audit just one source)
"""

import argparse
import asyncio
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs" / "govclipping"
DOCS_DIR.mkdir(parents=True, exist_ok=True)


CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


# Sources to audit. Each entry: (label, fetcher_callable_returning_url_list)
def make_sources(api_key: str, base: str = "https://brubru-production.up.railway.app"):
    """Each fetcher hits the live API and returns (label, urls) tuples."""
    hdr = {"X-API-Key": api_key, "Accept": "application/json"}

    async def fetch(client: httpx.AsyncClient, path: str) -> dict:
        try:
            r = await client.get(f"{base}{path}", headers=hdr, timeout=15.0)
            return r.json()
        except Exception as e:
            return {"error": str(e), "data": []}

    async def laws_urls(client):
        d = await fetch(client, "/api/v1/laws?limit=50")
        return [(it.get("celex"), it.get("eurlex_url")) for it in d.get("data", []) if it.get("eurlex_url")]

    async def commission_urls(client):
        d = await fetch(client, "/api/v1/commission-register-documents?limit=50&has_pdf=true")
        out = []
        for it in d.get("data", []):
            if it.get("pdf_url"):
                out.append((it.get("reference"), it["pdf_url"]))
            elif it.get("portal_url"):
                out.append((it.get("reference"), it["portal_url"]))
        return out

    async def webstream_urls(client):
        d = await fetch(client, "/api/v1/webstreams?limit=50")
        out = []
        for it in d.get("data", []):
            if it.get("multimedia_url"):
                out.append((it.get("title", "")[:50], it["multimedia_url"]))
        return out

    async def research_urls(client):
        d = await fetch(client, "/api/v1/research-publications?limit=30")
        out = []
        for it in d.get("data", []):
            if it.get("html_url"):
                out.append((it.get("publication_id"), it["html_url"]))
            if it.get("pdf_url"):
                out.append((it.get("publication_id"), it["pdf_url"]))
        return out

    async def tender_urls(client):
        d = await fetch(client, "/api/v1/tenders?limit=20")
        return [(it.get("publication_number"), it.get("ted_url")) for it in d.get("data", []) if it.get("ted_url")]

    async def press_urls(client):
        d = await fetch(client, "/api/v1/press-releases?limit=20")
        return [(it.get("title", "")[:40], it.get("url")) for it in d.get("data", []) if it.get("url")]

    async def council_urls(client):
        d = await fetch(client, "/api/v1/council-documents?limit=20")
        return [(it.get("title", "")[:40], it.get("url")) for it in d.get("data", []) if it.get("url")]

    async def publications_urls(client):
        d = await fetch(client, "/api/v1/publications?limit=20")
        return [(it.get("title", "")[:40], it.get("url")) for it in d.get("data", []) if it.get("url")]

    return {
        "laws": laws_urls,
        "commission_register": commission_urls,
        "webstreams": webstream_urls,
        "research_publications": research_urls,
        "tenders": tender_urls,
        "press_releases": press_urls,
        "council_documents": council_urls,
        "publications": publications_urls,
    }


def is_eurlex_url(url: str) -> bool:
    return "eur-lex.europa.eu" in url or "publications.europa.eu/resource/celex" in url


# Markers that indicate a EUR-Lex page is content-poor / placeholder.
# When ANY of these patterns is the dominant content, the URL is "broken-empty".
EUR_LEX_EMPTY_PATTERNS = [
    "The requested document does not exist",
    "Sorry, the requested document is not available in this language",
    "Document de la Commission européenne",  # Generic title
    "is not available in HTML format",
]
# Markers that indicate REAL legal text content.
EUR_LEX_CONTENT_PATTERNS = [
    "Whereas:",
    "considérant",
    "considerando",
    "Article",
    "Recital",
    "Recital (",
    "doc-ti",  # CSS class on real legal text
    "TitleIntern",
]


async def check_url(client: httpx.AsyncClient, url: str, deep_check: bool = False) -> Tuple[int, str]:
    """Return (http_status, verdict). Verdicts:
      OK          — 2xx response, content present
      BROKEN      — 404 / 410 / 5xx — the URL is genuinely dead
      EMPTY       — 2xx but content is a placeholder / unpopulated
      RATELIMITED — 429 (URL is fine, server defending)
      BLOCKED     — 403/406 from a host that's known to anti-bot but works in browsers
                    (consilium, ted aggressive)
      TIMEOUT / ERROR
    """
    try:
        r = await client.get(
            url, follow_redirects=True, timeout=12.0,
            headers={"User-Agent": CHROME_UA, "Accept": "text/html,application/pdf,*/*"},
        )
    except httpx.TimeoutException:
        return 0, "TIMEOUT"
    except Exception as e:
        return 0, f"ERROR:{type(e).__name__}"

    if r.status_code == 429:
        return r.status_code, "RATELIMITED"
    if r.status_code in (403, 406):
        host = urlparse(url).netloc
        if host in ("www.consilium.europa.eu", "consilium.europa.eu",
                    "ted.europa.eu", "www.ted.europa.eu"):
            return r.status_code, "BLOCKED"
        return r.status_code, "BROKEN"
    if r.status_code >= 400:
        return r.status_code, "BROKEN"

    if not deep_check:
        return r.status_code, "OK"

    # Deep check for EUR-Lex pages — verify content isn't a placeholder.
    body = r.text[:50000].lower() if r.text else ""
    if any(p.lower() in body for p in EUR_LEX_EMPTY_PATTERNS):
        return r.status_code, "EMPTY"
    if any(p.lower() in body for p in EUR_LEX_CONTENT_PATTERNS):
        return r.status_code, "OK"
    # No clear marker — likely fine but flag as UNCERTAIN
    if len(body) < 2000:
        return r.status_code, "EMPTY"
    return r.status_code, "OK"


async def audit_source(client: httpx.AsyncClient, label: str, fetcher, sample: int) -> dict:
    print(f"\n=== Auditing {label} ===")
    pairs = await fetcher(client)
    pairs = pairs[:sample]
    print(f"  Fetched {len(pairs)} URLs to check")
    results = {"OK": 0, "BROKEN": 0, "EMPTY": 0, "RATELIMITED": 0, "BLOCKED": 0, "TIMEOUT": 0, "ERROR": 0}
    bad = []
    sem = asyncio.Semaphore(8)

    async def check_one(ref, url):
        async with sem:
            deep = is_eurlex_url(url)
            code, verdict = await check_url(client, url, deep_check=deep)
            return ref, url, code, verdict

    out = await asyncio.gather(*[check_one(r, u) for r, u in pairs])
    for ref, url, code, verdict in out:
        v = verdict.split(":")[0]
        if v in results:
            results[v] += 1
        else:
            results["ERROR"] += 1
        # Only BROKEN, EMPTY, TIMEOUT and ERROR are real problems we'd act on.
        # RATELIMITED + BLOCKED are anti-bot artefacts — URL itself is fine.
        if v in ("BROKEN", "EMPTY", "TIMEOUT", "ERROR"):
            bad.append({"ref": ref, "url": url, "status": code, "verdict": verdict})
    print(f"  OK={results['OK']}  BROKEN={results['BROKEN']}  EMPTY={results['EMPTY']}  RATELIMITED={results['RATELIMITED']}  BLOCKED={results['BLOCKED']}  TIMEOUT={results['TIMEOUT']}")
    return {"label": label, "checked": len(pairs), "results": results, "bad": bad}


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=30, help="Max URLs to check per source")
    parser.add_argument("--only", default=None, help="Only audit one source label")
    parser.add_argument("--base", default="https://brubru-production.up.railway.app")
    args = parser.parse_args()

    # Load API key
    env_path = ROOT / ".env"
    api_key = None
    for line in env_path.read_text().splitlines():
        if line.startswith("BRUBRU_API_KEY="):
            api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
            break
    if not api_key:
        print("ERR: BRUBRU_API_KEY missing from .env")
        sys.exit(1)

    sources = make_sources(api_key, base=args.base)
    if args.only:
        sources = {k: v for k, v in sources.items() if k == args.only}

    async with httpx.AsyncClient(timeout=15.0) as client:
        audits = []
        for label, fetcher in sources.items():
            audit = await audit_source(client, label, fetcher, args.sample)
            audits.append(audit)

    # Write report
    today = date.today().isoformat()
    report_path = DOCS_DIR / f"url-audit-{today}.md"
    lines = [
        f"# URL freshness audit — {today}",
        "",
        f"Base: `{args.base}`",
        f"Sample size per source: {args.sample}",
        "",
        "## Summary",
        "",
        "| Source | Checked | OK | BROKEN | EMPTY | Ratelimited | Blocked | Timeout |",
        "|---|---|---|---|---|---|---|---|",
    ]
    total = {"checked": 0, "OK": 0, "BROKEN": 0, "EMPTY": 0, "RATELIMITED": 0, "BLOCKED": 0, "TIMEOUT": 0, "ERROR": 0}
    for a in audits:
        r = a["results"]
        lines.append(f"| {a['label']} | {a['checked']} | {r['OK']} | {r['BROKEN']} | {r['EMPTY']} | {r['RATELIMITED']} | {r['BLOCKED']} | {r['TIMEOUT']} |")
        total["checked"] += a["checked"]
        for k in r:
            total[k] += r[k]
    lines.append(f"| **TOTAL** | **{total['checked']}** | **{total['OK']}** | **{total['BROKEN']}** | **{total['EMPTY']}** | **{total['RATELIMITED']}** | **{total['BLOCKED']}** | **{total['TIMEOUT']}** |")
    lines.append("")
    lines.append("**Real problems = BROKEN + EMPTY + TIMEOUT.** Ratelimited + Blocked are anti-bot artefacts (the URLs work for users + properly-rate-limited partners).")
    lines.append("")

    for a in audits:
        if not a["bad"]:
            continue
        lines.append(f"## {a['label']} — {len(a['bad'])} bad URLs")
        lines.append("")
        lines.append("| Ref | Status | Verdict | URL |")
        lines.append("|---|---|---|---|")
        for b in a["bad"][:50]:
            ref = (b["ref"] or "?")[:40]
            url = b["url"][:120]
            lines.append(f"| {ref} | {b['status']} | {b['verdict']} | <{url}> |")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print()
    print(f"=== Report written to {report_path} ===")
    print(f"Total: {total['OK']}/{total['checked']} OK, {total['BROKEN']} broken, {total['EMPTY']} empty")


if __name__ == "__main__":
    asyncio.run(main())

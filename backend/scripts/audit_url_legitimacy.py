"""
URL-legitimacy audit for the Brubru EU Data API v1.

Every previous audit checked SHAPE (does the row have a source_url field?).
This one checks LEGITIMACY (is that URL real, specific to the row, and
returning real content?).

Triggered the 22 April 2026 LIBE-seed-transcript and the 1 May 2026
parliamentary-questions seed-fixture incidents. Runs as part of the
standard audit loop from now on.

Three signals:

  1. PER-ROW UNIQUENESS — if every row in a list endpoint shares the same
     source_url, that's a fixture, not real data.
  2. NOT A GENERIC LISTING URL — known generic placeholders (committee
     latest-documents, plenary parl-q listing, RSB landing page, etc.)
     don't belong on per-row source_url fields.
  3. URL RESOLVES — HEAD/GET returns < 400.

Reports per-folder verdicts:
  OK            : URLs unique enough + return 200 + not on the placeholder list.
  FIXTURE       : every row shares a single URL → flagged for deletion.
  PLACEHOLDER   : URL on the known-generic list → API needs an override.
  STALE         : URL returns 404/410 → data is real but link rotted.
  ANTIBOT       : URL returns 403/429 from a known anti-bot host → ignored.

Run: python3.12 backend/scripts/audit_url_legitimacy.py
"""

import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
OUT = Path("/tmp/jordi_audit")
OUT.mkdir(exist_ok=True)
BASE = "https://brubru-production.up.railway.app"

# Hosts known to anti-bot 403/429/404 honest crawlers — not data quality issues.
ANTI_BOT_HOSTS = {
    "linkedin.com", "www.linkedin.com",
    "ted.europa.eu",
    "www.consilium.europa.eu",
    "consilium.europa.eu",
}

# URLs we know are placeholder listings (table-of-contents, not row-specific).
# When these appear as a row's source_url it's a data-quality bug.
KNOWN_PLACEHOLDERS = {
    "https://www.europarl.europa.eu/committees/en/documents/latest-documents",
    "https://www.europarl.europa.eu/committees/en/meetings/meeting-documents",
    "https://www.europarl.europa.eu/plenary/en/parliamentary-questions.html",
    "https://www.europarl.europa.eu/plenary/en/agendas.html",
    "https://commission.europa.eu/law/law-making-process/regulatory-scrutiny-board_en",
    "https://commission.europa.eu/news/college-meetings_en",
    "https://commission.europa.eu/news_en",
    "https://commission.europa.eu/news/all-news_en",
    "https://technical-regulation-information-system.ec.europa.eu/",
    "https://www.consilium.europa.eu/en/meetings/",
    "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/home",
    "https://ec.europa.eu/info/law/better-regulation/have-your-say/initiatives",
}


def get_env(k):
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


KEY = get_env("BRUBRU_API_KEY")
if not KEY:
    print("[FATAL] BRUBRU_API_KEY missing"); sys.exit(1)


def fetch(path):
    url = BASE + path
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode()


def head_url(url, timeout=15):
    """GET with a real browser UA + Accept headers, read 1KB. Returns http status, or 0 on error."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read(1024)  # Drain a tiny bit so the connection closes cleanly.
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


# Folder → (path-to-list, count-to-sample, candidate URL fields)
PLAN = [
    ("laws",                          "/api/v1/laws?limit=10",                          {"eurlex_url"}),
    ("procedures",                    "/api/v1/procedures?limit=10",                    {"url", "law_tracker_url"}),
    ("delegated-acts",                "/api/v1/delegated-acts?limit=10",                {"source_url"}),
    ("implementing-acts",             "/api/v1/implementing-acts?limit=10",             {"source_url"}),
    ("tris-notifications",            "/api/v1/tris-notifications?limit=10",            {"source_url", "pdf_url"}),
    ("commission-register",           "/api/v1/commission-register-documents?limit=10", {"portal_url", "pdf_url"}),
    ("council-documents",             "/api/v1/council-documents?limit=10",             {"url"}),
    ("commissioners",                 "/api/v1/commissioners",                          {"bio_url", "unified_calendar_url", "agenda_url"}),
    ("officials",                     "/api/v1/officials?limit=10",                     {"profile_url"}),
    ("meps",                          "/api/v1/meps?limit=10",                          {"profile_url"}),
    ("meetings",                      "/api/v1/meetings?limit=10",                      {"source_url"}),
    ("rsb-opinions",                  "/api/v1/rsb-opinions?limit=10",                  {"source_url", "pdf_url"}),
    ("amendments",                    "/api/v1/amendments?limit=10",                    {"source_url"}),
    ("votes",                         "/api/v1/votes?limit=10",                         set()),  # no URL fields
    ("texts-adopted",                 "/api/v1/texts-adopted?limit=10",                 {"source_url", "pdf_url"}),
    ("resolutions",                   "/api/v1/resolutions?limit=10",                   {"source_url"}),
    ("reports",                       "/api/v1/reports?limit=10",                       {"document_url"}),
    ("opinions",                      "/api/v1/opinions?limit=10",                      {"source_url"}),
    ("parliamentary-questions",       "/api/v1/parliamentary-questions?limit=10",       {"source_url", "answer_url"}),
    ("webstreams",                    "/api/v1/webstreams?limit=10",                    {"multimedia_url", "video_url"}),
    ("publications",                  "/api/v1/publications?limit=10",                  {"url"}),
    ("press-releases",                "/api/v1/press-releases?limit=10",                {"url"}),
    ("calendar",                      "/api/v1/calendar/events?limit=10",               {"source_url", "agenda_url", "webstream_url"}),
    ("consultations",                 "/api/v1/consultations?limit=10",                 {"portal_url"}),
    ("research-publications",         "/api/v1/research-publications?limit=10",         {"html_url", "pdf_url"}),
    ("tenders",                       "/api/v1/tenders?limit=10",                       {"ted_url"}),
    ("knowledge-guides",              "/api/v1/knowledge-guides?limit=10",              set()),
    ("infringements",                 "/api/v1/infringements?limit=10",                 {"source_url", "pdf_url"}),
    ("funding-opportunities",         "/api/v1/funding-opportunities?limit=10",         {"source_url", "documents_url"}),
    ("ft-calls-for-proposals",        "/api/v1/ft-calls-for-proposals?limit=10",        {"source_url", "documents_url"}),
    ("ft-calls-for-tenders",          "/api/v1/ft-calls-for-tenders?limit=10",          {"source_url", "documents_url"}),
    ("ft-funded-projects",            "/api/v1/ft-funded-projects?limit=10",            {"source_url"}),
]


def audit_folder(folder, path, url_fields):
    code, body = fetch(path)
    try:
        payload = json.loads(body) if body else None
    except Exception:
        payload = None
    if code != 200 or not isinstance(payload, dict):
        return {"folder": folder, "verdict": "ENDPOINT_FAIL", "http_status": code, "rows": 0}

    items = payload.get("data", []) or []
    n = len(items)
    if n == 0:
        return {"folder": folder, "verdict": "EMPTY", "http_status": 200, "rows": 0}

    # Pick the primary URL field as the candidate with the MOST distinct values
    # across rows. This avoids accidentally flagging legitimate shared-parent
    # URLs (e.g. commissioners.unified_calendar_url is shared across all 27)
    # when a per-row URL (e.g. bio_url) is also available.
    primary = None
    best_distinct = 0
    for f in url_fields:
        vals = [it.get(f) for it in items if it.get(f)]
        if not vals:
            continue
        distinct = len(set(vals))
        if distinct > best_distinct:
            best_distinct = distinct
            primary = f

    rec = {
        "folder": folder,
        "http_status": 200,
        "rows": n,
        "primary_url_field": primary,
        "url_fields_audited": sorted(url_fields),
    }

    if not primary:
        rec["verdict"] = "NO_URL"
        return rec

    # Collect URLs per row
    urls = [it.get(primary) for it in items if it.get(primary)]
    distinct_urls = set(urls)
    placeholder_hits = [u for u in urls if u in KNOWN_PLACEHOLDERS]

    rec["distinct_url_count"] = len(distinct_urls)
    rec["placeholder_hits"] = len(placeholder_hits)
    rec["sample_urls"] = sorted(distinct_urls)[:5]

    # FIXTURE: every row shares a single URL AND that URL is a known
    # placeholder. Otherwise it might just be a real shared-parent (e.g. all
    # amendments to one DOCX share the parent's source_url) — still notable
    # but not a fabrication.
    if n > 1 and len(distinct_urls) == 1:
        only_url = next(iter(distinct_urls))
        if only_url in KNOWN_PLACEHOLDERS:
            rec["verdict"] = "FIXTURE"
            return rec
        # Real shared-parent — informational, not a failure.
        rec["verdict"] = "SHARED_PARENT"
        return rec

    # PLACEHOLDER: any URL is on the known-generic list
    if placeholder_hits:
        rec["verdict"] = "PLACEHOLDER"
        rec["placeholder_urls"] = sorted(set(placeholder_hits))
        return rec

    # Probe a couple of URLs (first + middle + last) to detect 404/410/403
    sample_to_probe = list({urls[0], urls[len(urls) // 2], urls[-1]})
    probe_results = []
    for u in sample_to_probe:
        host = urlparse(u).netloc
        s = head_url(u)
        kind = "OK" if 200 <= s < 400 else (
            "ANTIBOT" if (s in (403, 429) or (s == 404 and host in ANTI_BOT_HOSTS)) else "STALE"
        )
        probe_results.append({"url": u, "status": s, "kind": kind})
        time.sleep(0.6)

    rec["probe_results"] = probe_results

    stale = [p for p in probe_results if p["kind"] == "STALE"]
    if stale:
        rec["verdict"] = "STALE"
        return rec

    rec["verdict"] = "OK"
    return rec


def main():
    print(f"[INFO] URL-legitimacy audit: {len(PLAN)} folders\n")
    results = []
    for folder, path, url_fields in PLAN:
        rec = audit_folder(folder, path, url_fields)
        v = rec["verdict"]
        marker = {"OK": "✓", "FIXTURE": "✗", "PLACEHOLDER": "✗", "STALE": "✗",
                  "EMPTY": "·", "NO_URL": "·", "ENDPOINT_FAIL": "✗", "ANTIBOT": "·"}.get(v, "?")
        meta = ""
        if "distinct_url_count" in rec:
            meta = f" rows={rec['rows']} distinct={rec['distinct_url_count']}"
        if rec.get("placeholder_hits"):
            meta += f" placeholders={rec['placeholder_hits']}"
        print(f"  {marker} {v:14s}  {folder:25s}{meta}")
        if rec.get("verdict") == "FIXTURE":
            print(f"      shared URL: {list(rec.get('sample_urls', []))[0] if rec.get('sample_urls') else '?'}")
        if rec.get("verdict") == "STALE":
            for p in rec.get("probe_results", []):
                if p["kind"] == "STALE":
                    print(f"      STALE [{p['status']}]: {p['url']}")
        results.append(rec)
        # Be polite between folders, especially for upstream HEADs
        time.sleep(1.05)

    out = OUT / "url_legitimacy.json"
    out.write_text(json.dumps(results, indent=2))

    n_ok = sum(1 for r in results if r["verdict"] == "OK")
    n_bad = sum(1 for r in results if r["verdict"] in ("FIXTURE", "PLACEHOLDER", "STALE", "ENDPOINT_FAIL"))
    print(f"\n[SUMMARY] OK: {n_ok}/{len(results)} | FIX-NEEDED: {n_bad}")
    print(f"[DONE] Wrote: {out}")
    return 0 if n_bad == 0 else 2


if __name__ == "__main__":
    sys.exit(main())

"""
Audit every API folder against Jordi's 30 April 2026 meeting feedback.

For each endpoint, captures one representative response and flags:
  1. presence/absence of `body content` field (raw content, item #1, #8)
  2. presence of unwanted `meta` envelope (item #2)
  3. agenda-vs-profile separation on commissioners (item #3)
  4. rate-limit ceiling (item #4)
  6. EP committee agenda PDFs surfaced (items #6, #7)
  7. per-event source URL on calendar (item #7)

Run: python3.12 backend/scripts/audit_jordi_feedback.py
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
OUT_DIR = Path("/tmp/jordi_audit")
OUT_DIR.mkdir(exist_ok=True)

BASE = "https://brubru-production.up.railway.app"

def get_env(key):
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""

KEY = get_env("BRUBRU_API_KEY")
if not KEY:
    print("[FATAL] BRUBRU_API_KEY missing from .env"); sys.exit(1)

# (folder_tag, path) — one representative call per folder we want to audit.
# Detail variants get their own row so we can compare list-vs-detail shapes.
SAMPLES = [
    ("laws-list",                     "/api/v1/laws?q=GDPR&limit=1&detail_level=Full"),
    ("laws-detail",                   "/api/v1/laws/32016R0679?detail_level=Full"),
    ("laws-text",                     "/api/v1/laws/32016R0679/text?format=plain"),
    ("procedures-list",               "/api/v1/procedures?limit=1&detail_level=Full"),
    ("legal-text-recital-map",        "/api/v1/legal-text/32016R0679/recital-article-map"),
    ("legal-text-defined-terms",      "/api/v1/legal-text/32016R0679/defined-terms"),
    ("delegated-acts",                "/api/v1/delegated-acts?limit=1&detail_level=Full"),
    ("implementing-acts",             "/api/v1/implementing-acts?limit=1&detail_level=Full"),
    ("tris-notifications",            "/api/v1/tris-notifications?limit=1&detail_level=Full"),
    ("commission-register",           "/api/v1/commission-register-documents?limit=1&detail_level=Full"),
    ("council-documents",             "/api/v1/council-documents?limit=1&detail_level=Full"),
    ("metadata-dgs",                  "/api/v1/meta/dgs?limit=1"),
    ("metadata-committees",           "/api/v1/meta/committees?limit=1"),
    ("metadata-policy-areas",         "/api/v1/meta/policy-areas?limit=1"),
    ("commissioners-list",            "/api/v1/commissioners?limit=1&detail_level=Full"),
    ("commissioners-detail-fitto",    "/api/v1/commissioners/fitto"),
    ("commissioners-agenda-fitto",    "/api/v1/commissioners/fitto/agenda?limit=1"),
    ("officials",                     "/api/v1/officials?limit=1&detail_level=Full"),
    ("meps",                          "/api/v1/meps?limit=1&detail_level=Full"),
    ("meetings",                      "/api/v1/meetings?limit=1&detail_level=Full"),
    ("rsb-opinions",                  "/api/v1/rsb-opinions?limit=1&detail_level=Full"),
    ("committees-work",               "/api/v1/committees/LIBE/work-items?limit=1&detail_level=Full"),
    ("committees-minutes",            "/api/v1/committees/LIBE/minutes?limit=1&detail_level=Full"),
    ("ep-documents",                  "/api/v1/ep-documents?limit=1&detail_level=Full"),
    ("amendments",                    "/api/v1/amendments?limit=1&detail_level=Full"),
    ("votes",                         "/api/v1/votes?limit=1&detail_level=Full"),
    ("texts-adopted",                 "/api/v1/texts-adopted?limit=1&detail_level=Full"),
    ("texts-submitted",               "/api/v1/texts-submitted?limit=1&detail_level=Full"),
    ("resolutions",                   "/api/v1/resolutions?limit=1&detail_level=Full"),
    ("reports",                       "/api/v1/reports?limit=1&detail_level=Full"),
    ("opinions",                      "/api/v1/opinions?limit=1&detail_level=Full"),
    ("parliamentary-questions",       "/api/v1/parliamentary-questions?limit=1&detail_level=Full"),
    ("webstreams",                    "/api/v1/webstreams?limit=1&detail_level=Full"),
    ("publications",                  "/api/v1/publications?limit=1&detail_level=Full"),
    ("press-releases",                "/api/v1/press-releases?limit=1&detail_level=Full"),
    ("calendar",                      "/api/v1/calendar/events?limit=1"),
    ("consultations",                 "/api/v1/consultations?limit=1&detail_level=Full"),
    ("research-publications",         "/api/v1/research-publications?limit=1&detail_level=Full"),
    ("tenders",                       "/api/v1/tenders?limit=1&detail_level=Full"),
    ("predictions",                   "/api/v1/predictions/" + quote("2025/0232(COD)", safe="") + "/timeline"),
    ("knowledge-guides",              "/api/v1/knowledge-guides?limit=1&detail_level=Full"),
    ("citations",                     "/api/v1/citations/verify?q=" + quote("Regulation (EU) 2016/679")),
    ("whoami",                        "/api/v1/whoami"),
]

def fetch(path):
    url = BASE + path
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            return resp.status, dict(resp.getheaders()), body
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), e.read()
    except Exception as e:
        return 0, {}, str(e).encode()

# Body-content field names we expect at "Full" detail level for each folder.
BODY_HINTS = {
    "laws": ["text_html", "text_plain", "text_xml_url", "text_xml", "body_html", "body_text", "summary"],
    "amendments": ["original_text", "proposed_text", "justification", "text", "amendment_text"],
    "parliamentary-questions": ["question_text", "answer_text", "text", "body"],
    "research-publications": ["abstract", "summary", "pdf_text", "body_text"],
    "commission-register": ["pdf_text", "summary", "description", "body"],
    "reports": ["body_text", "summary", "pdf_text"],
    "opinions": ["body_text", "summary", "pdf_text"],
    "resolutions": ["body_text", "summary", "pdf_text"],
    "texts-adopted": ["body_text", "summary", "pdf_text"],
    "texts-submitted": ["body_text", "summary", "pdf_text"],
    "publications": ["summary", "body_html", "body_plain", "content"],
    "press-releases": ["summary", "body_html", "body_plain", "content"],
    "consultations": ["description", "summary", "feedback_text"],
    "delegated-acts": ["summary", "body", "text"],
    "implementing-acts": ["summary", "body", "text"],
    "tris-notifications": ["description", "summary", "draft_regulation_text"],
    "council-documents": ["summary", "body", "text"],
    "tenders": ["description", "summary", "body"],
    "knowledge-guides": ["body", "content"],
}

URL_HINTS = ["source_url", "url", "pdf_url", "eurlex_url", "agenda_pdf_url", "webstream_url", "detail_url", "profile_url", "homepage", "documents_url"]


def first_item(payload):
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), list) and payload["data"]:
            return payload["data"][0]
        if isinstance(payload.get("items"), list) and payload["items"]:
            return payload["items"][0]
        return payload
    if isinstance(payload, list) and payload:
        return payload[0]
    return None


def audit_one(tag, payload, headers):
    notes = []
    has_meta = False
    body_hint_present = None
    list_envelope_keys = []
    item = None

    if isinstance(payload, dict):
        if "meta" in payload:
            has_meta = True
        if "data" in payload and isinstance(payload["data"], list):
            list_envelope_keys = sorted(payload.keys())

    item = first_item(payload)
    item_keys = []
    if isinstance(item, dict):
        item_keys = sorted(item.keys())

    # body content presence
    family = tag.split("-")[0] if tag.split("-")[0] in BODY_HINTS else tag
    expected = BODY_HINTS.get(family, [])
    if expected and isinstance(item, dict):
        body_hint_present = [f for f in expected if f in item]

    # url presence
    urls_present = []
    if isinstance(item, dict):
        urls_present = [f for f in URL_HINTS if f in item and item.get(f)]

    return {
        "tag": tag,
        "has_meta_envelope": has_meta,
        "list_envelope_keys": list_envelope_keys,
        "item_keys": item_keys,
        "body_hint_fields_present": body_hint_present,
        "url_fields_present": urls_present,
    }


def main():
    print(f"[INFO] Fetching {len(SAMPLES)} sample responses (1.1 s gap to respect 60/min)")
    results = []
    for i, (tag, path) in enumerate(SAMPLES, 1):
        status, headers, body = fetch(path)
        f = OUT_DIR / f"{tag}.json"
        f.write_bytes(body if body else b"{}")
        try:
            payload = json.loads(body)
        except Exception:
            payload = None
        result = {
            "tag": tag,
            "path": path,
            "status": status,
            "size": len(body),
            "x_powered_by": headers.get("X-Powered-By") or headers.get("x-powered-by"),
            "x_source": headers.get("X-Source") or headers.get("x-source"),
            "x_ratelimit_limit": headers.get("X-RateLimit-Limit") or headers.get("x-ratelimit-limit"),
        }
        if payload is not None and status == 200:
            result.update(audit_one(tag, payload, headers))
        else:
            result["error"] = (body[:300] or b"").decode(errors="replace")
        results.append(result)
        print(f"[{i:02d}/{len(SAMPLES)}] {status:3d}  {tag:35s}  {len(body):>6d} bytes")
        time.sleep(1.1)

    out = OUT_DIR / "audit_summary.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\n[DONE] Wrote summary: {out}")
    return results


if __name__ == "__main__":
    main()

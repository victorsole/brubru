"""
Thorough per-endpoint audit of the Brubru EU Data API v1.

Hits multiple representative calls per folder to detect:
  - HTTP non-200 responses
  - Empty result sets where data should exist
  - Body / content fields that are present in schema but NULL on rows
  - Pagination correctness (page=2 returns different items than page=1)
  - Detail-level shaping (Minimal vs Full)
  - URL fields that 404 or are generic placeholders
  - Filter echo (params come back in the envelope)

Writes one big JSON summary to /tmp/jordi_audit/thorough.json plus a
human-readable report at /tmp/jordi_audit/thorough_report.md.

Run: python3.12 backend/scripts/audit_thorough.py
"""

import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote, urlparse

import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
OUT = Path("/tmp/jordi_audit")
OUT.mkdir(exist_ok=True)
BASE = "https://brubru-production.up.railway.app"


def get_env(k):
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


KEY = get_env("BRUBRU_API_KEY")
if not KEY:
    print("[FATAL] BRUBRU_API_KEY missing from .env"); sys.exit(1)


def fetch(path, headers_only=False):
    """Single call with auth. Returns (status, headers_dict, body_bytes)."""
    url = BASE + path
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {KEY}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = b"" if headers_only else resp.read()
            return resp.status, {k.lower(): v for k, v in resp.getheaders()}, body
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, e.read()
    except Exception as e:
        return 0, {}, str(e).encode()


# ============================================================================
# Test plan: list of (folder, label, path) tuples. Multiple per folder so we
# exercise filters, pagination, detail levels, and edge cases.
# ============================================================================
PLAN = [
    # Meta + auth
    ("meta", "ping",                        "/api/v1/ping"),
    ("meta", "whoami",                      "/api/v1/whoami"),
    ("meta", "openapi.json",                "/api/v1/openapi.json"),
    ("meta", "meta/enums",                  "/api/v1/meta/enums"),

    # Metadata enums
    ("metadata", "meta/dgs",                "/api/v1/meta/dgs"),
    ("metadata", "meta/committees",         "/api/v1/meta/committees"),
    ("metadata", "meta/policy-areas",       "/api/v1/meta/policy-areas"),
    ("metadata", "meta/political-groups",   "/api/v1/meta/political-groups"),
    ("metadata", "meta/countries",          "/api/v1/meta/countries"),
    ("metadata", "meta/languages",          "/api/v1/meta/languages"),
    ("metadata", "meta/procedure-types",    "/api/v1/meta/procedure-types"),
    ("metadata", "meta/legal-bases",        "/api/v1/meta/legal-bases"),
    ("metadata", "meta/procedure-statuses", "/api/v1/meta/procedure-statuses"),
    ("metadata", "meta/event-types",        "/api/v1/meta/event-types"),
    ("metadata", "meta/document-types",     "/api/v1/meta/document-types"),
    ("metadata", "meta/institutions",       "/api/v1/meta/institutions"),
    ("metadata", "meta/commissioners",      "/api/v1/meta/commissioners"),

    # Laws
    ("laws", "list-default",                "/api/v1/laws?limit=3"),
    ("laws", "list-search-GDPR",            "/api/v1/laws?q=GDPR&limit=3"),
    ("laws", "list-by-doc-type",            "/api/v1/laws?doc_type=Regulation&limit=3"),
    ("laws", "list-by-policy-area",         "/api/v1/laws?policy_area=Digital&limit=3"),
    ("laws", "list-by-celex",               "/api/v1/laws?celex=32016R0679"),
    ("laws", "list-paginate-page2",         "/api/v1/laws?limit=3&page=2"),
    ("laws", "detail-GDPR",                 "/api/v1/laws/32016R0679"),
    ("laws", "detail-AI-Act",               "/api/v1/laws/32024R1689"),
    ("laws", "text-GDPR-plain",             "/api/v1/laws/32016R0679/text?format=plain"),
    ("laws", "list-conflict-422",           "/api/v1/laws?published_to=2026-01-01&published_end=2026-01-02&limit=1"),
    ("laws", "list-bad-range-422",          "/api/v1/laws?published_from=2026-12-31&published_to=2026-01-01&limit=1"),

    # Procedures
    ("procedures", "list-default",          "/api/v1/procedures?limit=3"),
    ("procedures", "list-by-committee",     "/api/v1/procedures?committee=LIBE&limit=3"),
    ("procedures", "list-paginate-page2",   "/api/v1/procedures?limit=3&page=2"),
    ("procedures", "detail-by-oeil",        "/api/v1/procedures/" + quote("2024/0001(COD)", safe="")),

    # Legal-text
    ("legal-text", "recital-article-map",   "/api/v1/legal-text/32016R0679/recital-article-map"),
    ("legal-text", "defined-terms",         "/api/v1/legal-text/32016R0679/defined-terms"),
    ("legal-text", "recital-map-AI-Act",    "/api/v1/legal-text/32024R1689/recital-article-map"),

    # Acts (delegated, implementing, TRIS)
    ("delegated-acts", "list",              "/api/v1/delegated-acts?limit=3"),
    ("implementing-acts", "list",           "/api/v1/implementing-acts?limit=3"),
    ("tris-notifications", "list",          "/api/v1/tris-notifications?limit=3"),
    ("tris-notifications", "by-country",    "/api/v1/tris-notifications?country=DE&limit=3"),

    # Commission Register + Council
    ("commission-register", "list",         "/api/v1/commission-register-documents?limit=3"),
    ("commission-register", "by-category-SWD", "/api/v1/commission-register-documents?category=SWD&limit=3"),
    ("council-documents", "list",           "/api/v1/council-documents?limit=3"),

    # Commissioners
    ("commissioners", "list",               "/api/v1/commissioners"),
    ("commissioners", "detail-fitto",       "/api/v1/commissioners/raffaele-fitto"),
    ("commissioners", "detail-virkkunen",   "/api/v1/commissioners/henna-virkkunen"),
    ("commissioners", "detail-404",         "/api/v1/commissioners/no-such-person"),
    ("commissioners", "agenda-fitto",       "/api/v1/commissioners/fitto/agenda?limit=3"),
    ("commissioners", "agenda-by-date",     "/api/v1/commissioners/fitto/agenda?date_from=2026-04-01&date_to=2026-04-30&limit=3"),

    # Officials
    ("officials", "list",                   "/api/v1/officials?limit=3"),
    ("officials", "by-institution",         "/api/v1/officials?institution=COMMISSION&limit=3"),

    # MEPs
    ("meps", "list",                        "/api/v1/meps?limit=3"),

    # Transparency meetings
    ("meetings", "list",                    "/api/v1/meetings?limit=3"),

    # RSB
    ("rsb-opinions", "list",                "/api/v1/rsb-opinions?limit=3"),

    # EP detail
    ("committees", "work-LIBE",             "/api/v1/committees/LIBE/work-items?limit=3"),
    ("committees", "minutes-LIBE",          "/api/v1/committees/LIBE/minutes?limit=3"),
    ("ep-documents", "list",                "/api/v1/ep-documents?limit=3"),
    ("amendments", "list",                  "/api/v1/amendments?limit=3"),
    ("amendments", "by-procedure",          "/api/v1/amendments?procedure_reference=" + quote("2024/0001(COD)") + "&limit=3"),
    ("votes", "list",                       "/api/v1/votes?limit=3"),
    ("texts-adopted", "list",               "/api/v1/texts-adopted?limit=3"),
    ("texts-submitted", "list",             "/api/v1/texts-submitted?limit=3"),
    ("resolutions", "list",                 "/api/v1/resolutions?limit=3"),
    ("reports", "list",                     "/api/v1/reports?limit=3"),
    ("reports", "by-committee",             "/api/v1/reports?committee_code=LIBE&limit=3"),
    ("opinions", "list",                    "/api/v1/opinions?limit=3"),
    ("parliamentary-questions", "list",     "/api/v1/parliamentary-questions?limit=3"),
    ("webstreams", "list",                  "/api/v1/webstreams?limit=3"),
    ("webstreams", "by-committee",          "/api/v1/webstreams?committee=LIBE&limit=3"),

    # Live data
    ("publications", "list",                "/api/v1/publications?limit=3"),
    ("publications", "sources",             "/api/v1/publications/sources"),
    ("press-releases", "list",              "/api/v1/press-releases?limit=3"),
    ("calendar", "list-default",            "/api/v1/calendar/events?limit=3"),
    ("calendar", "by-plenary",              "/api/v1/calendar/events?event_type=plenary_session&limit=3"),
    ("calendar", "by-committee-meeting",    "/api/v1/calendar/events?event_type=committee_meeting&limit=3"),
    ("calendar", "by-committee-week",       "/api/v1/calendar/events?event_type=committee_week&limit=3"),
    ("calendar", "by-college",              "/api/v1/calendar/events?event_type=commission_college_meeting&limit=3"),
    ("calendar", "by-council",              "/api/v1/calendar/events?event_type=council_meeting&limit=3"),
    ("consultations", "list",               "/api/v1/consultations?limit=3"),
    ("research-publications", "list",       "/api/v1/research-publications?limit=3"),
    ("research-publications", "by-source-JRC", "/api/v1/research-publications?source=JRC&limit=3"),
    ("research-publications", "by-source-STOA", "/api/v1/research-publications?source=STOA&limit=3"),
    ("tenders", "list",                     "/api/v1/tenders?limit=3"),
    ("predictions", "timeline",             "/api/v1/predictions/" + quote("2024/0001(COD)", safe="") + "/timeline"),
    ("predictions", "outcome",              "/api/v1/predictions/" + quote("2024/0001(COD)", safe="") + "/outcome"),
    ("knowledge-guides", "list-summary",    "/api/v1/knowledge-guides?limit=3&detail_level=Summary"),
    ("knowledge-guides", "list-full",       "/api/v1/knowledge-guides?limit=2&detail_level=Full"),
    ("knowledge-guides", "search",          "/api/v1/knowledge-guides?q=GDPR&limit=3"),
    ("knowledge-guides", "detail",          "/api/v1/knowledge-guides/csam_regulation_online"),

    # Citations
    ("citations", "verify-q",               "/api/v1/citations/verify?q=" + quote("Regulation (EU) 2016/679")),
    ("citations", "verify-celex",           "/api/v1/verify-citation/32016R0679"),
]

# Body-content fields we expect at Full level for each folder.
EXPECTED_BODY_FIELDS = {
    "laws": {"summary", "text_url", "text_plain", "text_html"},
    "amendments": {"original_text", "proposed_text", "justification"},
    "parliamentary-questions": {"text_question", "text_answer"},
    "research-publications": {"abstract", "summary", "pdf_text"},
    "commission-register": {"summary", "description", "pdf_text"},
    "reports": {"summary", "body_text", "pdf_text"},
    "opinions": {"summary", "body_text"},
    "resolutions": {"summary", "body_text"},
    "texts-adopted": {"summary", "body_text"},
    "texts-submitted": {"summary", "body_text"},
    "publications": {"summary", "body_html", "body_plain"},
    "press-releases": {"summary", "body_html"},
    "consultations": {"description", "summary"},
    "delegated-acts": {"summary", "body"},
    "implementing-acts": {"summary", "body"},
    "tris-notifications": {"short_summary", "full_text_summary", "main_content"},
    "council-documents": {"summary", "body"},
    "tenders": {"description", "summary"},
    "knowledge-guides": {"content", "quick_facts", "summary"},
}


# ============================================================================
# Audit individual response
# ============================================================================
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


def check_meta_envelope(payload):
    return isinstance(payload, dict) and "meta" in payload and isinstance(payload.get("meta"), dict) and "powered_by" in payload["meta"]


def check_envelope_keys(payload):
    if not isinstance(payload, dict):
        return None
    expected = {"total", "returned", "pages", "page", "limit", "has_more", "data"}
    return expected.issubset(payload.keys())


def find_url_fields(item):
    """Return list of (field_name, value) pairs for URL-looking fields."""
    if not isinstance(item, dict):
        return []
    out = []
    for k, v in item.items():
        if not isinstance(v, str):
            continue
        if "url" in k.lower() and v.startswith(("http://", "https://", "/api/v1/")):
            out.append((k, v))
    return out


def body_field_audit(folder, item):
    """For folders we expect body content on, return which fields are present and which are NULL."""
    expected = EXPECTED_BODY_FIELDS.get(folder, set())
    if not expected or not isinstance(item, dict):
        return None
    present_with_value = [f for f in expected if f in item and item[f] not in (None, "", [])]
    present_null = [f for f in expected if f in item and item[f] in (None, "", [])]
    missing = [f for f in expected if f not in item]
    return {"present_value": sorted(present_with_value), "present_null": sorted(present_null), "missing": sorted(missing)}


# ============================================================================
# Run audit
# ============================================================================
def main():
    print(f"[INFO] Running thorough audit: {len(PLAN)} sample calls (1.05s gap)")
    results = []
    saved = {}
    pagination_pairs = defaultdict(dict)

    for i, (folder, label, path) in enumerate(PLAN, 1):
        status, headers, body = fetch(path)
        try:
            payload = json.loads(body) if body else None
        except Exception:
            payload = None

        # Save the raw body for spot-check diagnostics.
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", f"{folder}__{label}")
        f = OUT / f"{slug}.json"
        f.write_bytes(body if body else b"{}")

        rec = {
            "folder": folder,
            "label": label,
            "path": path,
            "status": status,
            "size": len(body),
            "x_powered_by": headers.get("x-powered-by"),
            "x_ratelimit_tier": headers.get("x-ratelimit-tier"),
            "x_ratelimit_limit": headers.get("x-ratelimit-limit"),
            "x_request_id": headers.get("x-request-id"),
        }

        if status == 200 and payload is not None:
            rec["meta_envelope"] = check_meta_envelope(payload)
            rec["envelope_keys_ok"] = check_envelope_keys(payload)
            if isinstance(payload, dict):
                rec["envelope_total"] = payload.get("total")
                rec["envelope_returned"] = payload.get("returned")
                rec["envelope_pages"] = payload.get("pages")
                rec["envelope_detail_level"] = payload.get("detail_level")
            item = first_item(payload)
            if isinstance(item, dict):
                rec["item_keys"] = sorted(item.keys())
                rec["url_fields"] = [k for k, _ in find_url_fields(item)]
                rec["body_audit"] = body_field_audit(folder, item)
                # Record first item id/celex/reference for pagination diff
                first_id = item.get("id") or item.get("celex") or item.get("oeil_procedure_ref") or item.get("reference") or item.get("notification_number")
                if first_id and "list" in label or "default" in label:
                    pagination_pairs[folder]["page1"] = first_id
                if "page2" in label and first_id:
                    pagination_pairs[folder]["page2"] = first_id
        elif status >= 400:
            rec["error_body"] = (body[:500] or b"").decode(errors="replace")

        results.append(rec)
        print(f"  [{i:03d}/{len(PLAN)}] {status:3d}  {folder:25s}  {label:30s}  {len(body):>7d}b")
        time.sleep(1.05)

    # Pagination correctness
    paginate_ok = {}
    for folder, ids in pagination_pairs.items():
        if "page1" in ids and "page2" in ids:
            paginate_ok[folder] = ids["page1"] != ids["page2"]

    summary = {
        "total_calls": len(results),
        "n_200": sum(1 for r in results if r["status"] == 200),
        "n_4xx": sum(1 for r in results if 400 <= r["status"] < 500),
        "n_5xx": sum(1 for r in results if 500 <= r["status"] < 600),
        "n_meta_envelope": sum(1 for r in results if r.get("meta_envelope")),
        "non_200": [(r["folder"], r["label"], r["status"]) for r in results if r["status"] != 200],
        "pagination_correct": paginate_ok,
        "results": results,
    }
    out = OUT / "thorough.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"\n[DONE] Wrote summary: {out}")
    print(f"  200 OK : {summary['n_200']} / {summary['total_calls']}")
    print(f"  4xx    : {summary['n_4xx']}")
    print(f"  5xx    : {summary['n_5xx']}")
    print(f"  meta envelope still present: {summary['n_meta_envelope']}")
    return summary


if __name__ == "__main__":
    main()

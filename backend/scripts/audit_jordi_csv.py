"""
Re-audit Brubru's v1 API endpoint-by-endpoint against Jordi's CSV feedback.

Source CSV: docs/govclipping/Review BruBru api.csv

For each row, runs a targeted test that maps Jordi's comment to a checkable
assertion (URL works, fields non-empty, content exposed, no duplicate-URL,
list/detail parity, etc). Outputs:

  - /tmp/jordi_csv_audit/results.json   (machine-readable, per-endpoint)
  - /tmp/jordi_csv_audit/summary.txt    (human-readable)

Run: python3.12 backend/scripts/audit_jordi_csv.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import quote
from urllib import request as _urllib_request, error as _urllib_error

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
CSV_PATH = ROOT / "docs" / "govclipping" / "Review BruBru api.csv"
OUT_DIR = Path("/tmp/jordi_csv_audit")
OUT_DIR.mkdir(exist_ok=True, parents=True)

BASE = "https://brubru-production.up.railway.app"


def get_env(key: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


KEY = get_env("BRUBRU_API_KEY")
if not KEY:
    print("[FATAL] BRUBRU_API_KEY missing from .env")
    sys.exit(1)


def http(method: str, path: str, body: dict | None = None, timeout: float = 30.0):
    url = f"{BASE}{path}"
    headers = {"X-API-Key": KEY, "Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = _urllib_request.Request(url, method=method, headers=headers, data=data)
    t0 = time.time()
    try:
        with _urllib_request.urlopen(req, timeout=timeout) as r:
            payload = r.read()
            return r.getcode(), payload, int((time.time() - t0) * 1000)
    except _urllib_error.HTTPError as e:
        return e.code, e.read(), int((time.time() - t0) * 1000)
    except Exception as e:
        return 0, str(e).encode(), int((time.time() - t0) * 1000)


def parse_json(body: bytes):
    try:
        return json.loads(body.decode("utf-8", errors="replace"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Per-endpoint check definitions, keyed off the path Jordi reported.
# Each check returns {"verdict": "ok|fail|warn|skip", "detail": str}
# ---------------------------------------------------------------------------

def check_status_200(path: str, body: dict | None = None) -> dict:
    code, payload, _ms = http("GET" if body is None else "POST", path, body)
    if code == 200:
        return {"verdict": "ok", "detail": f"200 ({len(payload)} bytes)", "code": code}
    return {"verdict": "fail", "detail": f"{code}: {payload[:200].decode('utf-8','replace')}", "code": code}


def check_list_returns_data(path: str, min_items: int = 1) -> dict:
    code, payload, _ = http("GET", path)
    if code != 200:
        return {"verdict": "fail", "detail": f"HTTP {code}", "code": code}
    j = parse_json(payload)
    n = len(j.get("data", []) if j else [])
    if n >= min_items:
        return {"verdict": "ok", "detail": f"{n} items", "code": code}
    return {"verdict": "fail", "detail": f"only {n} items in data[]", "code": code}


def check_field_filled(path: str, field: str) -> dict:
    code, payload, _ = http("GET", path)
    if code != 200:
        return {"verdict": "fail", "detail": f"HTTP {code}", "code": code}
    j = parse_json(payload)
    items = (j or {}).get("data") or []
    if not items:
        return {"verdict": "warn", "detail": "empty list — cannot check field", "code": code}
    n_filled = sum(1 for it in items if (it.get(field) or "") != "")
    if n_filled == len(items):
        return {"verdict": "ok", "detail": f"{field} filled on all {len(items)} items", "code": code}
    if n_filled == 0:
        return {"verdict": "fail", "detail": f"{field} EMPTY on all {len(items)} items", "code": code}
    return {"verdict": "warn", "detail": f"{field} filled on {n_filled}/{len(items)}", "code": code}


def check_url_distinct(path: str, field: str = "url", sample: int = 20) -> dict:
    code, payload, _ = http("GET", path + ("&" if "?" in path else "?") + f"limit={sample}")
    if code != 200:
        return {"verdict": "fail", "detail": f"HTTP {code}", "code": code}
    j = parse_json(payload)
    items = (j or {}).get("data") or []
    if not items:
        return {"verdict": "warn", "detail": "empty list — cannot check distinctness", "code": code}
    urls = [it.get(field) for it in items if it.get(field)]
    distinct = set(urls)
    if len(distinct) == 1 and len(urls) > 1:
        return {"verdict": "fail", "detail": f"all {len(urls)} {field}s identical: {next(iter(distinct))[:80]}", "code": code}
    if len(urls) == 0:
        return {"verdict": "fail", "detail": f"no rows have {field}", "code": code}
    return {"verdict": "ok", "detail": f"{len(distinct)} distinct {field}s across {len(urls)} rows", "code": code}


def check_url_works(path: str, field: str, sample_first: bool = True) -> dict:
    code, payload, _ = http("GET", path + ("&" if "?" in path else "?") + "limit=3")
    if code != 200:
        return {"verdict": "fail", "detail": f"list HTTP {code}", "code": code}
    j = parse_json(payload)
    items = (j or {}).get("data") or []
    if not items:
        return {"verdict": "warn", "detail": "empty list — cannot probe URL", "code": code}
    target = items[0].get(field)
    if not target:
        return {"verdict": "fail", "detail": f"first row missing {field}", "code": code}
    try:
        req = _urllib_request.Request(target, method="GET", headers={"User-Agent": "Mozilla/5.0 (Brubru audit)", "Accept": "*/*"})
        with _urllib_request.urlopen(req, timeout=15) as r:
            if r.getcode() < 400:
                return {"verdict": "ok", "detail": f"{target[:80]} -> {r.getcode()}", "code": code, "probed_url": target}
            return {"verdict": "fail", "detail": f"{target[:80]} -> HTTP {r.getcode()}", "code": code, "probed_url": target}
    except _urllib_error.HTTPError as he:
        return {"verdict": "fail", "detail": f"{target[:80]} -> HTTP {he.code}", "code": code, "probed_url": target}
    except Exception as e:
        return {"verdict": "fail", "detail": f"{target[:80]} -> {type(e).__name__}: {str(e)[:80]}", "code": code, "probed_url": target}


def check_list_detail_parity(list_path: str, detail_path_tmpl: str, key_field: str = "id") -> dict:
    code, payload, _ = http("GET", list_path + ("&" if "?" in list_path else "?") + "limit=1")
    if code != 200:
        return {"verdict": "fail", "detail": f"list HTTP {code}", "code": code}
    j = parse_json(payload)
    items = (j or {}).get("data") or []
    if not items:
        return {"verdict": "warn", "detail": "empty list — cannot diff", "code": code}
    list_keys = set((items[0] or {}).keys())
    key_value = items[0].get(key_field)
    if not key_value:
        return {"verdict": "fail", "detail": f"first row missing {key_field}", "code": code}
    detail_path = detail_path_tmpl.replace("{ID}", quote(str(key_value), safe=""))
    code2, payload2, _ = http("GET", detail_path)
    if code2 != 200:
        return {"verdict": "fail", "detail": f"detail HTTP {code2} at {detail_path}", "code": code2}
    j2 = parse_json(payload2)
    detail_keys = set((j2 or {}).keys())
    only_in_list = list_keys - detail_keys
    only_in_detail = detail_keys - list_keys
    msg_parts = []
    if only_in_list:
        msg_parts.append(f"LIST has but DETAIL lacks: {sorted(only_in_list)}")
    if only_in_detail:
        msg_parts.append(f"DETAIL has but LIST lacks: {sorted(only_in_detail)}")
    if not msg_parts:
        return {"verdict": "ok", "detail": f"{len(list_keys)} fields identical", "code": code}
    if only_in_list and not only_in_detail:
        return {"verdict": "fail", "detail": "; ".join(msg_parts), "code": code}
    if only_in_detail and not only_in_list:
        return {"verdict": "warn", "detail": "; ".join(msg_parts), "code": code}
    return {"verdict": "fail", "detail": "; ".join(msg_parts), "code": code}


def check_body_field_present(path: str, body_fields: list[str]) -> dict:
    """For Jordi's 'guardes el contingut? caldria exposar-lo'. At least one body
    field must be present and non-empty on the first row."""
    code, payload, _ = http("GET", path + ("&" if "?" in path else "?") + "limit=3")
    if code != 200:
        return {"verdict": "fail", "detail": f"HTTP {code}", "code": code}
    j = parse_json(payload)
    items = (j or {}).get("data") or []
    if not items:
        return {"verdict": "warn", "detail": "empty list — cannot check body", "code": code}
    found = []
    for f in body_fields:
        for it in items:
            v = it.get(f)
            if v and isinstance(v, str) and len(v) > 50:
                found.append(f"{f}({len(v)}c)")
                break
    if found:
        return {"verdict": "ok", "detail": f"body fields present: {found}", "code": code}
    keys = sorted((items[0] or {}).keys())
    return {"verdict": "fail", "detail": f"none of {body_fields} non-empty (>50c). Schema fields: {keys}", "code": code}


# ---------------------------------------------------------------------------
# Map of CSV path -> (test_fn, args). Most tests verify Jordi's specific complaint.
# ---------------------------------------------------------------------------

TESTS: list[tuple[str, str, callable]] = [
    # path_in_csv, jordi_comment_keyword, callable
    ("/api/v1/amendments", "ok", lambda: check_status_200("/api/v1/amendments?limit=1")),
    ("/api/v1/calendar/events", "ok", lambda: check_status_200("/api/v1/calendar/events?limit=1")),
    ("/api/v1/citations/verify", "per a què serveix?", lambda: check_status_200("/api/v1/citations/verify?q=32016R0679")),
    ("/api/v1/verify-citation/{ref}", "per a què serveix?", lambda: check_status_200("/api/v1/verify-citation/32016R0679")),
    ("/api/v1/commission-register-documents", "expose body", lambda: check_body_field_present("/api/v1/commission-register-documents", ["body", "summary", "body_text", "pdf_text", "description", "common_name"])),
    ("/api/v1/commissioners/andrius-kubilius/agenda", "falta url evento", lambda: check_field_filled("/api/v1/commissioners/andrius-kubilius/agenda?limit=5", "detail_url")),
    ("/api/v1/commissioners/andrius-kubilius", "ok", lambda: check_status_200("/api/v1/commissioners/andrius-kubilius")),
    ("/api/v1/committees/AFCO/minutes", "ok", lambda: check_status_200("/api/v1/committees/AFCO/minutes?limit=1")),
    ("/api/v1/committees/afco/work-items", "falta links", lambda: check_field_filled("/api/v1/committees/afco/work-items?limit=5", "url")),
    ("/api/v1/consultations", "description sometimes empty", lambda: check_field_filled("/api/v1/consultations?limit=5", "description")),
    ("/api/v1/consultations/13693/feedback", "initiative_id example", lambda: check_status_200("/api/v1/consultations/by-initiative/13693/feedback?limit=2")),
    ("/api/v1/consultations/13693", "initiative_id example", lambda: check_status_200("/api/v1/consultations/13693")),
    ("/api/v1/council-documents", "all same url", lambda: check_url_distinct("/api/v1/council-documents?limit=10", "url")),
    ("/api/v1/delegated-acts", "url retorna error", lambda: check_url_works("/api/v1/delegated-acts", "source_url")),
    ("/api/v1/delegated-acts/{reference}", "url retorna error", lambda: check_status_200("/api/v1/delegated-acts?limit=1")),
    ("/api/v1/ep-documents", "document_url broken; html_url?", lambda: check_url_works("/api/v1/ep-documents", "document_url")),
    ("/api/v1/eprs", "ok", lambda: check_status_200("/api/v1/eprs?limit=1")),
    ("/api/v1/funding-opportunities", "no retorna info", lambda: check_list_returns_data("/api/v1/funding-opportunities?limit=5")),
    ("/api/v1/ft-calls-for-proposals", "no retorna info", lambda: check_list_returns_data("/api/v1/ft-calls-for-proposals?limit=5")),
    ("/api/v1/ft-calls-for-tenders", "no retorna info", lambda: check_list_returns_data("/api/v1/ft-calls-for-tenders?limit=5")),
    ("/api/v1/ft-funded-projects", "no retorna info", lambda: check_list_returns_data("/api/v1/ft-funded-projects?limit=5")),
    ("/api/v1/implementing-acts", "expose content", lambda: check_body_field_present("/api/v1/implementing-acts", ["body", "summary", "body_text", "description"])),
    ("/api/v1/delegated-acts", "expose content", lambda: check_body_field_present("/api/v1/delegated-acts", ["body", "summary", "body_text", "description"])),
    ("/api/v1/infringements", "expose content", lambda: check_body_field_present("/api/v1/infringements", ["summary", "body_text", "pdf_text"])),
    ("/api/v1/infringements_list_detail_parity", "DETAIL fewer fields", lambda: check_list_detail_parity("/api/v1/infringements", "/api/v1/infringements/{ID}", "inf_reference")),
    ("/api/v1/laws", "freshness check", lambda: check_status_200("/api/v1/laws?limit=1")),
    ("/api/v1/laws/{celex}", "ok", lambda: check_status_200("/api/v1/laws/32016R0679")),
    ("/api/v1/laws/{celex}/text", "ok", lambda: check_status_200("/api/v1/laws/32016R0679/text")),
    ("/api/v1/legal-text/resolve-aliases", "purpose", lambda: check_status_200("/api/v1/legal-text/resolve-aliases", body={"text": "GDPR and AI Act"})),
    ("/api/v1/legal-text/resolve-references", "purpose", lambda: check_status_200("/api/v1/legal-text/resolve-references", body={"text": "Article 5 of Regulation (EU) 2022/2065"})),
    ("/api/v1/legal-text/{celex}/defined-terms", "example CELEX needed", lambda: check_status_200("/api/v1/legal-text/32022R2065/defined-terms")),
    ("/api/v1/legal-text/{celex}/recital-article-map", "example CELEX needed", lambda: check_status_200("/api/v1/legal-text/32025R2149/recital-article-map")),
    ("/api/v1/meetings", "no retorna info", lambda: check_list_returns_data("/api/v1/meetings?limit=5")),
    ("/api/v1/meps", "country/group/role empty", lambda: check_field_filled("/api/v1/meps?limit=5", "country")),
    ("/api/v1/meps_group", "country/group/role empty", lambda: check_field_filled("/api/v1/meps?limit=5", "group")),
    ("/api/v1/meps_role", "country/group/role empty", lambda: check_field_filled("/api/v1/meps?limit=5", "role")),
    ("/api/v1/meta/enums", "ok", lambda: check_status_200("/api/v1/meta/enums")),
    ("/api/v1/commissioners", "ok", lambda: check_status_200("/api/v1/commissioners")),
    ("/api/v1/committees", "ok", lambda: check_status_200("/api/v1/committees")),
    ("/api/v1/countries", "ok", lambda: check_status_200("/api/v1/countries")),
    ("/api/v1/directorates-general", "ok", lambda: check_status_200("/api/v1/directorates-general")),
    ("/api/v1/document-types", "ok", lambda: check_status_200("/api/v1/document-types")),
    ("/api/v1/event-types", "ok", lambda: check_status_200("/api/v1/event-types")),
    ("/api/v1/institutions", "ok", lambda: check_status_200("/api/v1/institutions")),
    ("/api/v1/languages", "ok", lambda: check_status_200("/api/v1/languages")),
    ("/api/v1/legal-bases", "ok", lambda: check_status_200("/api/v1/legal-bases")),
    ("/api/v1/meta/commissioners", "duplicate?", lambda: check_status_200("/api/v1/meta/commissioners")),
    ("/api/v1/meta/committees", "duplicate?", lambda: check_status_200("/api/v1/meta/committees")),
    ("/api/v1/meta/countries", "duplicate?", lambda: check_status_200("/api/v1/meta/countries")),
    ("/api/v1/meta/dgs", "duplicate?", lambda: check_status_200("/api/v1/meta/dgs")),
    ("/api/v1/meta/directorates-general", "duplicate?", lambda: check_status_200("/api/v1/meta/directorates-general")),
    ("/api/v1/meta/document-types", "duplicate?", lambda: check_status_200("/api/v1/meta/document-types")),
    ("/api/v1/officials", "many fields empty + no source url", lambda: check_field_filled("/api/v1/officials?limit=5", "bio_url")),
    ("/api/v1/opinions", "no retorna info", lambda: check_list_returns_data("/api/v1/opinions?limit=5")),
    ("/api/v1/parliamentary-questions", "expose content", lambda: check_body_field_present("/api/v1/parliamentary-questions", ["text_question", "text_answer", "summary", "subject"])),
    ("/api/v1/predictions/{procedure_ref}/outcome", "example needed", lambda: check_status_200("/api/v1/predictions/2025/0232%28COD%29/outcome")),
    ("/api/v1/predictions/{procedure_ref}/timeline", "example needed", lambda: check_status_200("/api/v1/predictions/2025/0232%28COD%29/timeline")),
    ("/api/v1/press-releases", "summary weird, content missing", lambda: check_body_field_present("/api/v1/press-releases", ["body", "body_text", "body_html", "summary"])),
    ("/api/v1/procedures_list_detail_parity", "LIST fewer fields than DETAIL", lambda: check_list_detail_parity("/api/v1/procedures", "/api/v1/procedures/{ID}", "oeil_procedure_ref")),
    ("/api/v1/procedures", "fewer fields", lambda: check_status_200("/api/v1/procedures?limit=1")),
    ("/api/v1/publications", "missing content", lambda: check_body_field_present("/api/v1/publications", ["body", "summary", "body_text", "body_html"])),
    ("/api/v1/publications/sources", "purpose", lambda: check_status_200("/api/v1/publications/sources")),
    ("/api/v1/reports", "ok", lambda: check_status_200("/api/v1/reports?limit=1")),
    ("/api/v1/research-publications", "ok", lambda: check_status_200("/api/v1/research-publications?limit=1")),
    ("/api/v1/resolutions", "no key events", lambda: check_field_filled("/api/v1/resolutions?limit=5", "key_events")),
    ("/api/v1/rsb-opinions", "ok", lambda: check_status_200("/api/v1/rsb-opinions?limit=1")),
    ("/api/v1/tenders", "ok", lambda: check_status_200("/api/v1/tenders?limit=1")),
    ("/api/v1/texts-adopted", "expose content", lambda: check_body_field_present("/api/v1/texts-adopted", ["body_text", "summary", "description", "full_text"])),
    ("/api/v1/texts-submitted", "no retorna info", lambda: check_list_returns_data("/api/v1/texts-submitted?limit=5")),
    ("/api/v1/tris-notifications", "no retorna info", lambda: check_list_returns_data("/api/v1/tris-notifications?limit=5")),
]


def main():
    print(f"Auditing {len(TESTS)} tests against {BASE}")
    print(f"Source: {CSV_PATH}")
    # Free-tier API key has a 60 req/min ceiling. Each test fires 1-3 calls,
    # so we throttle to ~1.1s/test (≈55/min). Override with --fast if running
    # against an enterprise key.
    throttle_s = 0.0 if "--fast" in sys.argv else 1.2
    print(f"Throttle: {throttle_s}s between tests\n")
    results = []
    for path, comment, fn in TESTS:
        try:
            r = fn()
        except Exception as e:
            r = {"verdict": "fail", "detail": f"audit-internal-error: {type(e).__name__}: {e}", "code": -1}
        r["path"] = path
        r["jordi"] = comment
        verdict = r.get("verdict", "?")
        symbol = {"ok": "[OK]", "fail": "[FAIL]", "warn": "[WARN]", "skip": "[SKIP]"}.get(verdict, "[?]")
        print(f"{symbol} {path:60s} {comment[:30]:30s} -> {r.get('detail','')[:140]}")
        results.append(r)
        if throttle_s:
            time.sleep(throttle_s)

    counts = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    print(f"\nResults: {counts}")
    (OUT_DIR / "results.json").write_text(json.dumps(results, indent=2))
    summary_lines = [f"Audit summary {time.strftime('%Y-%m-%d %H:%M:%S')}", f"BASE={BASE}", "", f"Counts: {counts}", ""]
    summary_lines += ["Failures:"]
    for r in results:
        if r["verdict"] == "fail":
            summary_lines.append(f"  {r['path']:60s}  ({r['jordi']:30s})  {r.get('detail','')}")
    summary_lines += ["", "Warnings:"]
    for r in results:
        if r["verdict"] == "warn":
            summary_lines.append(f"  {r['path']:60s}  ({r['jordi']:30s})  {r.get('detail','')}")
    (OUT_DIR / "summary.txt").write_text("\n".join(summary_lines))
    print(f"\nWrote {OUT_DIR}/results.json and summary.txt")


if __name__ == "__main__":
    main()

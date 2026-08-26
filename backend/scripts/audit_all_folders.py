"""
Comprehensive per-folder audit of the Brubru v1 API.

For each Postman folder (= OpenAPI tag), hits each endpoint against
production, verifies HTTP status + envelope shape + URL fields, and
generates a per-folder report.

Output: docs/govclipping/postman-audit-{YYYY-MM-DD}.md

Usage:
    cd backend && python3.12 scripts/audit_all_folders.py
"""

import asyncio
import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urlparse

import httpx

ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs" / "govclipping"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/151.0 Safari/537.36"
)

ANTI_BOT_HOSTS = {
    "www.linkedin.com", "linkedin.com",
    "twitter.com", "x.com",
    "www.consilium.europa.eu", "consilium.europa.eu",
    "ted.europa.eu", "www.ted.europa.eu",
}


# Sensible default params per path-param so each endpoint hits real data.
PATH_DEFAULTS = {
    "celex": "32016R0679",
    "reference": "lip-2021-0296-COD",
    "ref": "32016R0679",                       # for /verify-citation/{ref}
    "name": "fitto",
    "code": "LIBE",
    "publication_id": "EPRS_BLOG_chinas-economic-challenge-to-the-world",
    "mep_id": "1",
    "guide_id": "ai_act_regulation",
    "initiative_id": "13174",
    "ta_reference": "P10_TA(2026)0104",
    "procedure_ref": "2025/2089(INI)",
    "slug": "fitto",
    "vote_id": None,           # Resolved at runtime
    "id": None,                # Resolved at runtime
    "event_id": None,          # Resolved at runtime
    "tender_id": None,         # Resolved at runtime
    "amendment_id": None,
    "stream_id": None,
    "meeting_id": None,
    "opinion_reference": None,
    "question_reference": None,
    "notification_number": None,
    "publication_id_path": None,
}


# Per-folder LIST endpoint to use when resolving sample IDs for detail endpoints.
SAMPLE_LIST_BY_FOLDER = {
    "v1-amendments": "/api/v1/amendments?limit=1",
    "v1-votes": "/api/v1/votes?limit=1",
    "v1-meetings": "/api/v1/meetings?limit=1",
    "v1-rsb-opinions": "/api/v1/rsb-opinions?limit=1",
    "v1-parliamentary-questions": "/api/v1/parliamentary-questions?limit=1",
    "v1-tris-notifications": "/api/v1/tris-notifications?limit=1",
    "v1-delegated-acts": "/api/v1/delegated-acts?limit=1",
    "v1-implementing-acts": "/api/v1/implementing-acts?limit=1",
    "v1-tenders": "/api/v1/tenders?limit=1",
    "v1-eprs": "/api/v1/eprs?limit=1",
    "v1-publications": "/api/v1/publications?limit=1",
    "v1-calendar": "/api/v1/calendar/events?limit=1",
    "v1-webstreams": "/api/v1/webstreams?limit=1",
    "v1-commission-register": "/api/v1/commission-register-documents?limit=1",
    "v1-officials": "/api/v1/officials?limit=1",
    "v1-procedures": "/api/v1/procedures?limit=1",
    "v1-resolutions": "/api/v1/resolutions?limit=1",
    "v1-texts-adopted": "/api/v1/texts-adopted?limit=1",
}


SAMPLE_KEY_BY_FOLDER = {
    "v1-amendments": "id",
    "v1-votes": "id",
    "v1-meetings": "id",
    "v1-rsb-opinions": "opinion_reference",
    "v1-parliamentary-questions": "question_reference",
    "v1-tris-notifications": "notification_number",
    "v1-delegated-acts": "reference",
    "v1-implementing-acts": "reference",
    "v1-tenders": "id",
    "v1-eprs": "publication_id",
    "v1-publications": "id",
    "v1-calendar": "id",
    "v1-webstreams": "id",
    "v1-commission-register": "reference",
    "v1-officials": "slug",
    "v1-procedures": "file_id",       # /procedures/{reference} accepts file_id or oeil_procedure_ref
    "v1-resolutions": "procedure_ref",
    "v1-texts-adopted": "ta_reference",
}


URL_FIELDS = {
    "url", "html_url", "pdf_url", "portal_url", "source_url",
    "ted_url", "documents_url", "doceo_url", "ep_page_url",
    "eurlex_url", "agenda_url", "agenda_pdf_url", "bio_url",
    "unified_calendar_url", "homepage", "streaming_url",
    "multimedia_url", "video_url", "feedback_url",
    "commission_observations_url", "answer_url", "oeil_url",
    "text_url", "legal_text_url",
    "website", "twitter", "linkedin", "youtube",
    "webstream_url",
}


async def fetch_spec(client: httpx.AsyncClient, base: str) -> dict:
    r = await client.get(f"{base}/api/v1/openapi.json", timeout=20.0)
    r.raise_for_status()
    return r.json()


async def fetch_json(client: httpx.AsyncClient, base: str, path: str, hdr: dict) -> Tuple[int, Any]:
    """Fetch with auto-throttle: if 429, sleep + retry up to 2x."""
    for attempt in range(3):
        try:
            r = await client.get(f"{base}{path}", headers=hdr, timeout=20.0)
            if r.status_code == 429 and attempt < 2:
                # Hit rate limit; sleep 65s for the sliding window to reset.
                await asyncio.sleep(65)
                continue
            try:
                return r.status_code, r.json()
            except Exception:
                return r.status_code, r.text[:200]
        except Exception as e:
            return 0, f"{type(e).__name__}: {e}"
    return 429, "rate-limited even after retry"


async def head_url(client: httpx.AsyncClient, url: str) -> Tuple[int, str]:
    try:
        r = await client.get(
            url, follow_redirects=True, timeout=12.0,
            headers={"User-Agent": CHROME_UA, "Accept": "text/html,application/pdf,*/*"},
        )
        if r.status_code == 429:
            return r.status_code, "RATELIMITED"
        host = urlparse(url).netloc
        # LinkedIn returns 404 to non-logged-in scrapers as part of anti-bot.
        # The URLs work in browsers — classify as BLOCKED, not BROKEN.
        if host in ANTI_BOT_HOSTS and r.status_code in (403, 404, 406, 999):
            return r.status_code, "BLOCKED"
        if r.status_code >= 400:
            return r.status_code, "BROKEN"
        return r.status_code, "OK"
    except Exception:
        return 0, "TIMEOUT"


def collect_urls(obj: Any, out: List[Tuple[str, str]], path: str = "") -> None:
    """Walk a JSON tree and emit (field_path, url) tuples."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            full = f"{path}.{k}" if path else k
            if k in URL_FIELDS and isinstance(v, str) and v.startswith(("http://", "https://")):
                out.append((full, v))
            else:
                collect_urls(v, out, full)
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:10]):  # cap nested list scan
            collect_urls(v, out, f"{path}[{i}]")


def resolve_path_params(path: str, sample_ids: Dict[str, str], folder_tag: str = "") -> Optional[str]:
    """Replace {param} placeholders. Folder-scoped sample IDs win over generic
    PATH_DEFAULTS, so different folders that share a param name (e.g. `reference`
    means CRD ref in delegated-acts but file_id in procedures) don't collide.
    """
    out_segments = []
    for seg in path.lstrip("/").split("/"):
        m = re.match(r"^\{([^:}]+)(?::path)?\}$", seg)
        if m:
            name = m.group(1)
            # Prefer folder-scoped key (e.g. "v1-delegated-acts:reference")
            scoped = sample_ids.get(f"{folder_tag}:{name}")
            val = scoped or sample_ids.get(name) or PATH_DEFAULTS.get(name)
            if val is None:
                return None
            out_segments.append(quote(str(val), safe=""))
        else:
            out_segments.append(seg)
    return "/" + "/".join(out_segments)


async def main():
    base = "https://brubru-production.up.railway.app"
    api_key = None
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("BRUBRU_API_KEY="):
            api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
            break
    if not api_key:
        print("ERR: BRUBRU_API_KEY missing")
        sys.exit(1)
    hdr = {"X-API-Key": api_key, "Accept": "application/json"}

    async with httpx.AsyncClient() as client:
        print("Fetching live OpenAPI spec...")
        spec = await fetch_spec(client, base)
        print(f"  {len(spec.get('paths', {}))} paths in spec")

        # Group endpoints by tag (= Postman folder)
        folders: Dict[str, List[Tuple[str, str, dict]]] = defaultdict(list)
        for path, methods in spec.get("paths", {}).items():
            for method, op in methods.items():
                if method not in ("get", "post"):  # POSTs excluded from public tests for safety
                    continue
                tag = (op.get("tags") or ["v1-misc"])[0]
                folders[tag].append((path, method, op))

        # Resolve sample IDs by hitting one LIST per folder
        print("\nResolving sample IDs...")
        sample_ids: Dict[str, str] = {}
        for tag, list_path in SAMPLE_LIST_BY_FOLDER.items():
            code, data = await fetch_json(client, base, list_path, hdr)
            if code == 200 and isinstance(data, dict) and data.get("data"):
                key = SAMPLE_KEY_BY_FOLDER.get(tag, "id")
                val = data["data"][0].get(key)
                if val:
                    # Map per-tag id keys to PATH_DEFAULTS slots
                    map_to = {
                        "v1-amendments": "amendment_id",
                        "v1-votes": "vote_id",
                        "v1-meetings": "meeting_id",
                        "v1-rsb-opinions": "opinion_reference",
                        "v1-parliamentary-questions": "question_reference",
                        "v1-tris-notifications": "notification_number",
                        "v1-delegated-acts": "reference",
                        "v1-implementing-acts": "reference",
                        "v1-tenders": "tender_id",
                        "v1-eprs": "publication_id",
                        "v1-publications": "publication_id",
                        "v1-calendar": "event_id",
                        "v1-webstreams": "stream_id",
                        "v1-commission-register": "reference",
                        "v1-officials": "slug",
                        "v1-procedures": "reference",
                        "v1-resolutions": "procedure_ref",
                        "v1-texts-adopted": "ta_reference",
                    }.get(tag, key)
                    # Store both global (last-wins) and folder-scoped (always
                    # wins for this folder).
                    sample_ids[map_to] = str(val)
                    sample_ids[f"{tag}:{map_to}"] = str(val)
                    # Also store under the original key for in-folder lookup
                    sample_ids[f"{tag}:{key}"] = str(val)
        print(f"  Resolved {len(sample_ids)} sample IDs")

        # Walk each folder
        print("\n=== Auditing folders ===")
        folder_audits = {}
        for tag in sorted(folders.keys()):
            endpoints = folders[tag]
            results = []
            url_results = []
            for path, method, op in endpoints:
                resolved = resolve_path_params(path, sample_ids, folder_tag=tag)
                if resolved is None:
                    results.append((method, path, "—", "skip-no-sample"))
                    continue
                # Add sensible default query params
                full_path = resolved
                if "?" not in full_path:
                    full_path += "?limit=3"
                code, body = await fetch_json(client, base, full_path, hdr)
                total = body.get("total") if isinstance(body, dict) else None
                results.append((method, path, code, total))
                # Pace: stay well under the 60/min API ceiling (1.2 req/sec).
                await asyncio.sleep(1.1)
                # Audit URL fields in response
                if isinstance(body, dict):
                    urls: List[Tuple[str, str]] = []
                    collect_urls(body, urls)
                    url_results.extend((path, fp, u) for fp, u in urls[:30])

            # HEAD-check the URLs in parallel (capped per folder)
            sem = asyncio.Semaphore(8)
            async def check(pair):
                p, fp, u = pair
                async with sem:
                    code, verdict = await head_url(client, u)
                    return p, fp, u, code, verdict
            url_results = url_results[:60]  # cap
            url_audit = await asyncio.gather(*[check(t) for t in url_results])

            folder_audits[tag] = {
                "endpoints": results,
                "urls": url_audit,
            }

            ok = sum(1 for _, _, c, _ in results if c == 200)
            broken = sum(1 for _, _, c, _ in results if isinstance(c, int) and 400 <= c < 600)
            url_ok = sum(1 for *_, v in url_audit if v == "OK")
            url_anti = sum(1 for *_, v in url_audit if v in ("BLOCKED", "RATELIMITED"))
            url_bad = sum(1 for *_, v in url_audit if v in ("BROKEN", "TIMEOUT"))
            print(f"  {tag:30s}  ep_ok={ok}/{len(results)}  url_ok={url_ok}  anti_bot={url_anti}  url_broken={url_bad}")

    # Write report
    today = date.today().isoformat()
    report = DOCS_DIR / f"postman-audit-{today}.md"
    lines = [
        f"# Postman folder audit — {today}",
        "",
        f"Base: `{base}`",
        f"Folders: **{len(folder_audits)}** ({sum(len(v['endpoints']) for v in folder_audits.values())} endpoints walked)",
        "",
        "## Summary",
        "",
        "| Folder | Endpoints OK | URLs OK | Anti-bot | Broken |",
        "|---|---|---|---|---|",
    ]
    total_ep = total_ep_ok = total_url = total_url_ok = total_anti = total_broken = 0
    for tag, audit in sorted(folder_audits.items()):
        eps = audit["endpoints"]
        urls = audit["urls"]
        ep_ok = sum(1 for _, _, c, _ in eps if c == 200)
        url_ok = sum(1 for *_, v in urls if v == "OK")
        url_anti = sum(1 for *_, v in urls if v in ("BLOCKED", "RATELIMITED"))
        url_bad = sum(1 for *_, v in urls if v in ("BROKEN", "TIMEOUT"))
        total_ep += len(eps); total_ep_ok += ep_ok
        total_url += len(urls); total_url_ok += url_ok
        total_anti += url_anti; total_broken += url_bad
        lines.append(f"| {tag.replace('v1-','')} | {ep_ok}/{len(eps)} | {url_ok}/{len(urls)} | {url_anti} | {url_bad} |")
    lines.append(f"| **TOTAL** | **{total_ep_ok}/{total_ep}** | **{total_url_ok}/{total_url}** | **{total_anti}** | **{total_broken}** |")
    lines.append("")

    # Detail per-folder for any with broken URLs or non-200 endpoints
    for tag, audit in sorted(folder_audits.items()):
        bad_eps = [(m, p, c, t) for m, p, c, t in audit["endpoints"] if c != 200 and c != "—"]
        bad_urls = [(p, fp, u, c, v) for p, fp, u, c, v in audit["urls"] if v in ("BROKEN", "TIMEOUT")]
        if not bad_eps and not bad_urls:
            continue
        lines.append(f"## {tag.replace('v1-','')} — issues")
        lines.append("")
        if bad_eps:
            lines.append("**Endpoints:**")
            lines.append("")
            lines.append("| Method | Path | Status | Total |")
            lines.append("|---|---|---|---|")
            for m, p, c, t in bad_eps[:20]:
                lines.append(f"| {m.upper()} | `{p}` | {c} | {t} |")
            lines.append("")
        if bad_urls:
            lines.append("**Broken URLs:**")
            lines.append("")
            lines.append("| Endpoint | Field | URL | Status | Verdict |")
            lines.append("|---|---|---|---|---|")
            for p, fp, u, c, v in bad_urls[:20]:
                lines.append(f"| `{p}` | `{fp}` | <{u[:80]}> | {c} | {v} |")
            lines.append("")

    report.write_text("\n".join(lines), encoding="utf-8")
    print()
    print(f"Report: {report}")
    print(f"=== Endpoints: {total_ep_ok}/{total_ep} OK · URLs: {total_url_ok}/{total_url} OK · {total_anti} anti-bot · {total_broken} broken ===")


if __name__ == "__main__":
    asyncio.run(main())

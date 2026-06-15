"""
Ingest EU Funding & Tenders Portal NEWS and EVENTS into economy_items.

The F&T Portal's Support -> News and Support -> Events pages are backed by the
SEDIA search-api, but on DEDICATED indexes selected by apiKey:
    news   -> apiKey=SEDIA-NEWS-PROD
    events -> apiKey=SEDIA-EVENTS-PROD

GOTCHA (cost an hour to find): every multipart form part MUST carry
`filename="blob"` in its Content-Disposition, otherwise the server returns
HTTP 500 "Send timeout" (code 101504). The portal SPA sends it that way.

Stored as economy_items (body_code 'ftportal', item_type 'news' / 'event') so
they inherit the 5-datapoint contract and feed /api/v2/funding/ft-news +
/ft-events. Idempotent upsert on (body_code, item_type, public_url).

Run:
    python3.12 backend/scripts/ingest_ft_news_events.py --kind news --apply
    python3.12 backend/scripts/ingest_ft_news_events.py --all --apply
"""
from __future__ import annotations

import argparse
import datetime as dt
import html as _html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

import psycopg2
from bs4 import BeautifulSoup

from ingest_funding_sedia import get_env

UA = "Mozilla/5.0 (compatible; BrubruIngest/1.0; +https://brubru.beresol.eu)"
BOUNDARY = "----WebKitFormBoundaryBrubru"

KINDS = {
    "news":   {"apikey": "SEDIA-NEWS-PROD",   "item_type": "news",  "date_field": "publicationDate"},
    "events": {"apikey": "SEDIA-EVENTS-PROD", "item_type": "event", "date_field": "startDate"},
}
PORTAL = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/support"


def _multipart(fields: Dict[str, Any]) -> bytes:
    out: List[str] = []
    for k, v in fields.items():
        out += [f"--{BOUNDARY}",
                f'Content-Disposition: form-data; name="{k}"; filename="blob"',
                "Content-Type: application/json", "", json.dumps(v)]
    out += [f"--{BOUNDARY}--", ""]
    return "\r\n".join(out).encode()


def fetch_page(apikey: str, page: int, size: int = 100) -> Dict[str, Any]:
    url = (f"https://api.tech.ec.europa.eu/search-api/prod/rest/search"
           f"?apiKey={apikey}&text=***&pageSize={size}&pageNumber={page}")
    body = _multipart({"query": {"bool": {"must": []}}, "languages": ["en"]})
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": f"multipart/form-data; boundary={BOUNDARY}",
        "Accept": "application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  [HTTP {e.code}] page={page}: {e.read()[:120]}")
        return {}
    except Exception as e:  # noqa: BLE001
        print(f"  [{type(e).__name__}] page={page}: {str(e)[:80]}")
        return {}


def _first(v):
    if isinstance(v, list):
        return v[0] if v else None
    return v


def _parse_date(s) -> Optional[dt.datetime]:
    s = _first(s)
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


def _strip(html_str: str, max_len: int = 6000) -> str:
    if not html_str:
        return ""
    try:
        t = BeautifulSoup(html_str, "html.parser").get_text(" ", strip=True)
    except Exception:  # noqa: BLE001
        t = re.sub(r"<[^>]+>", " ", html_str)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:max_len]


def normalise(kind: str, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    md = result.get("metadata") or {}
    title = _first(md.get("title")) or result.get("title")
    url = _first(md.get("url")) or result.get("url")
    if not title or not url:
        return None
    desc = _strip(_first(md.get("description")) or "", 1200)
    programmes = md.get("programmes") or []
    if not isinstance(programmes, list):
        programmes = [programmes]
    audiences = md.get("audiences") or []
    if not isinstance(audiences, list):
        audiences = [audiences]

    if kind == "news":
        doc_date = _parse_date(md.get("publicationDate")) or _parse_date(md.get("es_SortDate"))
        body_html_src = _first(md.get("body")) or ""
        body_core = _strip(body_html_src, 6000) or desc
        meta_lines = []
        if programmes:
            meta_lines.append(("Programmes", ", ".join(str(p) for p in programmes)))
        if audiences:
            meta_lines.append(("Audiences", ", ".join(str(a) for a in audiences)))
        if doc_date:
            meta_lines.append(("Published", doc_date.date().isoformat()))
        summary = desc[:300] if desc else title
    else:  # events
        start = _parse_date(md.get("startDate"))
        end = _parse_date(md.get("endDate"))
        doc_date = start or _parse_date(md.get("es_SortDate"))
        body_core = desc
        meta_lines = []
        if start:
            meta_lines.append(("Starts", start.isoformat()))
        if end:
            meta_lines.append(("Ends", end.isoformat()))
        if programmes:
            meta_lines.append(("Programmes", ", ".join(str(p) for p in programmes)))
        rec = _first(md.get("recordingLink"))
        if rec:
            meta_lines.append(("Recording", rec))
        det = _first(md.get("detailsUrl"))
        if det:
            meta_lines.append(("Details", det))
        when = f" ({start.date().isoformat()})" if start else ""
        summary = (desc[:280] if desc else "") + when

    txt_parts = [title, ""]
    txt_parts += [f"{k}: {v}" for k, v in meta_lines]
    if body_core:
        txt_parts += ["", body_core]
    body_txt = "\n".join(txt_parts).strip()
    html_meta = "".join(
        f"<li><strong>{_html.escape(k)}:</strong> {_html.escape(str(v))}</li>" for k, v in meta_lines)
    body_html = (f"<h1>{_html.escape(title)}</h1><ul>{html_meta}</ul>"
                 + (f"<div>{_html.escape(body_core)}</div>" if body_core else ""))

    return {
        "title": title,
        "summary": summary or title,
        "public_url": url,
        "body_txt": body_txt,
        "body_html": body_html,
        "document_date": doc_date,
        "guid": _first(md.get("id")) or _first(md.get("REFERENCE")) or url,
    }


UPSERT = """
INSERT INTO economy_items
    (body_code, item_type, title, summary, public_url, body_txt, body_html,
     document_date, creation_date, source_kind, guid, fetched_at)
VALUES ('ftportal', %(item_type)s, %(title)s, %(summary)s, %(public_url)s,
        %(body_txt)s, %(body_html)s, %(document_date)s, NOW(), 'sedia', %(guid)s, NOW())
ON CONFLICT (body_code, item_type, public_url) DO UPDATE SET
    title=EXCLUDED.title, summary=EXCLUDED.summary, body_txt=EXCLUDED.body_txt,
    body_html=EXCLUDED.body_html, document_date=EXCLUDED.document_date, fetched_at=NOW()
"""


def ingest(cur, kind: str, *, apply: bool, max_items: int = 2000) -> int:
    cfg = KINDS[kind]
    seen: Dict[str, Dict[str, Any]] = {}
    page = 1
    while len(seen) < max_items:
        data = fetch_page(cfg["apikey"], page)
        results = data.get("results") or []
        if not results:
            break
        for r in results:
            row = normalise(kind, r)
            if row:
                seen[row["public_url"]] = row
        total = data.get("totalResults", len(seen))
        if len(results) < 100 or len(seen) >= total:
            break
        page += 1
        time.sleep(0.3)
    print(f"[{kind}] {len(seen)} distinct items")
    written = 0
    for row in seen.values():
        row["item_type"] = cfg["item_type"]
        if apply:
            cur.execute(UPSERT, row)
            written += 1
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=sorted(KINDS))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if not args.all and not args.kind:
        ap.error("pass --kind news|events or --all")
    db = get_env("DATABASE_URL")
    if not db:
        print("[FATAL] DATABASE_URL missing"); sys.exit(1)
    conn = psycopg2.connect(db); cur = conn.cursor()
    total = 0
    for kind in (sorted(KINDS) if args.all else [args.kind]):
        try:
            total += ingest(cur, kind, apply=args.apply)
            if args.apply:
                conn.commit()
        except Exception as exc:  # noqa: BLE001
            conn.rollback(); print(f"  [DB ERR] {kind}: {exc}")
    print(f"\n[DONE] written={total} apply={args.apply}")


if __name__ == "__main__":
    main()

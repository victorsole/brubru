"""
CC-2(b) — Backfill body text for texts_adopted, institutional_publications, and
infringement_procedures.

For each row that has a source URL but no body text yet, fetch the HTML, strip
boilerplate (nav/header/footer/scripts), collapse whitespace, and write the
result back to the body column. Resumable: skips rows that already have body
text > 500 chars.

Throttle: 0.6s between requests (~100/min).

Usage:
    python3.12 backend/scripts/backfill_body_text.py --kind texts-adopted [--limit 50] [--apply]
    python3.12 backend/scripts/backfill_body_text.py --kind press-releases [--limit 50] [--apply]
    python3.12 backend/scripts/backfill_body_text.py --kind infringements [--limit 50] [--apply]

Defaults to dry-run with --limit 5.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from typing import Optional, Tuple
from urllib import error as urllib_error
from urllib import request as urllib_request

import psycopg2
import psycopg2.extras
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
USER_AGENT = "Mozilla/5.0 (compatible; BrubruBackfill/1.0; +https://brubru.beresol.eu)"

# Per-kind config: which table, which URL column (in priority order), which
# body column, and a minimum body length to consider a row "already filled".
KINDS = {
    "texts-adopted": {
        "table": "texts_adopted",
        "id_col": "id",
        "url_cols": ["full_text_url", "source_url", "pdf_url"],
        "body_col": "full_text",
        "min_filled": 500,
        "id_label": "ta_reference",
    },
    "press-releases": {
        "table": "institutional_publications",
        "id_col": "id",
        "url_cols": ["url"],
        "body_col": "html_content",
        "min_filled": 500,
        "id_label": "external_id",
        "where_extra": "category = 'press_release'",
    },
    "publications": {
        "table": "institutional_publications",
        "id_col": "id",
        "url_cols": ["url"],
        "body_col": "html_content",
        "min_filled": 500,
        "id_label": "external_id",
        "where_extra": "(category IS NULL OR category != 'press_release') AND url NOT LIKE '%<%'",  # skip dirty URLs
    },
    "infringements": {
        "table": "infringement_procedures",
        "id_col": "id",
        "url_cols": ["source_url", "pdf_url"],
        "body_col": "summary",
        "min_filled": 300,
        "id_label": "inf_reference",
    },
    # Phase 3: tables with a CELEX column. Source URL is built from CELEX via
    # the Cellar API (publications.europa.eu/resource/celex/{celex}) which
    # requires Accept: application/xhtml+xml + Accept-Language: en. Bypasses
    # EUR-Lex's WAF. See `cellar_url_for_celex` below.
    "register-docs": {
        "table": "commission_documents",
        "id_col": "id",
        "url_cols": ["celex"],          # CELEX column → Cellar URL
        "body_col": "text_body",
        "min_filled": 500,
        "id_label": "reference",
        "use_cellar": True,
    },
    "acts": {
        "table": "secondary_acts",
        "id_col": "id",
        "url_cols": ["celex"],
        "body_col": "text_body",
        "min_filled": 500,
        "id_label": "reference",
        "use_cellar": True,
    },
}


def cellar_url_for_celex(celex: str) -> str:
    """Build a Cellar resource URL for a CELEX number.

    EUR-Lex public WAF blocks server-side scrapes of /legal-content/EN/TXT/...
    The Publications Office's Cellar resource URL with explicit content
    negotiation (Accept: application/xhtml+xml, Accept-Language: en) is the
    canonical machine-readable path.
    """
    return f"http://publications.europa.eu/resource/celex/{celex.strip().upper()}"


def get_env(key: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def http_fetch(url: str, timeout: float = 25.0, cellar: bool = False, _accept: Optional[str] = None) -> Tuple[Optional[bytes], str]:
    """Fetch a URL. Returns (bytes, content_kind) where kind is 'html', 'pdf', or '' on failure.

    When cellar=True, uses the explicit content-negotiation headers required
    by the Publications Office Cellar API (Accept: application/xhtml+xml +
    Accept-Language: en) to receive a server-side rendered XHTML body for a
    CELEX resource. Without these the Cellar endpoint returns 400.

    Many CELEX resources don't have an XHTML manifestation but DO have a PDF
    one (typical for JOIN, RES, DEC, and some SWDs). On HTTP 404 with cellar
    mode, we automatically retry with Accept: application/pdf.
    """
    is_pdf_ext = url.lower().endswith(".pdf")
    if url.lower().endswith((".docx", ".doc", ".xlsx")):
        return None, ""
    headers = {"User-Agent": USER_AGENT}
    if cellar:
        headers["Accept"] = _accept or "application/xhtml+xml"
        headers["Accept-Language"] = "en"
    else:
        headers["Accept"] = "text/html,application/xhtml+xml,application/pdf"
        headers["Accept-Language"] = "en"
    req = urllib_request.Request(url, headers=headers)
    try:
        with urllib_request.urlopen(req, timeout=timeout) as r:
            ctype = (r.headers.get("Content-Type") or "").lower()
            blob = r.read()
            if "pdf" in ctype or is_pdf_ext or blob[:4] == b"%PDF":
                return blob, "pdf"
            if "html" in ctype or "xml" in ctype:
                return blob, "html"
            return None, ""
    except urllib_error.HTTPError as e:
        # Cellar returns HTTP 300 (Multiple Choices) when a CELEX has multiple
        # language manifestations and we haven't pinned one. The response
        # body lists each manifestation as <a href> — grab the first DOC link
        # and re-fetch.
        if e.code == 300 and cellar:
            try:
                body = e.read()
                m = re.search(rb'href="(http://publications\.europa\.eu/resource/cellar/[^"]+/DOC_[^"]+)"', body)
                if m:
                    next_url = m.group(1).decode()
                    return http_fetch(next_url, timeout=timeout, cellar=cellar, _accept=_accept)
            except Exception:  # noqa: BLE001
                pass
        # Cellar 404 on xhtml+xml usually means no XHTML manifestation exists.
        # Many CELEX docs only ship as PDF — retry once with that Accept.
        if e.code == 404 and cellar and (_accept or "application/xhtml+xml") != "application/pdf":
            return http_fetch(url, timeout=timeout, cellar=cellar, _accept="application/pdf")
        if e.code != 404:
            print(f"  [HTTP {e.code}] {url[:80]}")
        return None, ""
    except Exception as e:  # noqa: BLE001
        print(f"  [{type(e).__name__}] {url[:80]}: {str(e)[:60]}")
        return None, ""


def extract_html_text(html_bytes: bytes) -> str:
    """Strip boilerplate and return the readable body text."""
    if not html_bytes:
        return ""
    try:
        soup = BeautifulSoup(html_bytes, "html.parser")
    except Exception:  # noqa: BLE001
        return ""
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
        tag.decompose()
    body = soup.find("main") or soup.find("article") or soup.body or soup
    text = body.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text.replace("\x00", "")


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes via pypdf. Returns '' on failure."""
    if not pdf_bytes:
        return ""
    import io
    try:
        import pypdf  # noqa: F401
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        chunks = []
        for page in reader.pages:
            try:
                chunks.append(page.extract_text() or "")
            except Exception:  # noqa: BLE001
                continue
        text = re.sub(r"\s+", " ", "\n".join(chunks)).strip()
        return text.replace("\x00", "")
    except Exception as exc:  # noqa: BLE001
        print(f"  [PDF parse failed] {exc}")
        return ""


def extract_text(blob: bytes, kind: str) -> str:
    if kind == "pdf":
        return extract_pdf_text(blob)
    if kind == "html":
        return extract_html_text(blob)
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True, choices=sorted(KINDS.keys()))
    ap.add_argument("--limit", type=int, default=5, help="Max rows to process (0 = unbounded)")
    ap.add_argument("--apply", action="store_true", help="Write to DB. Default is dry-run.")
    ap.add_argument("--throttle", type=float, default=0.6, help="Seconds between HTTP calls")
    args = ap.parse_args()

    cfg = KINDS[args.kind]

    db = get_env("DATABASE_URL")
    if not db:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)

    conn = psycopg2.connect(db)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    url_col_pick = " COALESCE(" + ", ".join(cfg["url_cols"]) + ") AS picked_url"
    where_parts = [f"({cfg['body_col']} IS NULL OR length({cfg['body_col']}) < {cfg['min_filled']})"]
    where_parts.append("(" + " OR ".join(f"{c} IS NOT NULL" for c in cfg["url_cols"]) + ")")
    if cfg.get("where_extra"):
        where_parts.append(cfg["where_extra"])

    sql = (
        f"SELECT {cfg['id_col']} AS row_id, {cfg['id_label']} AS row_label, "
        f"{url_col_pick} FROM {cfg['table']} "
        f"WHERE {' AND '.join(where_parts)} "
        f"ORDER BY {cfg['id_col']} DESC"
    )
    if args.limit:
        sql += f" LIMIT {args.limit}"

    cur.execute(sql)
    rows = cur.fetchall()
    print(f"[INFO] kind={args.kind} table={cfg['table']} body_col={cfg['body_col']}")
    print(f"[INFO] {len(rows)} rows to process (apply={args.apply}, throttle={args.throttle}s)")

    # Pick the right "updated at" column per table.
    timestamp_col = "last_updated"
    if cfg["table"] == "institutional_publications":
        timestamp_col = "fetched_at"
    update_sql = (
        f"UPDATE {cfg['table']} "
        f"SET {cfg['body_col']} = %(body)s, {timestamp_col} = NOW() "
        f"WHERE {cfg['id_col']} = %(row_id)s"
    )

    n_filled = 0
    n_failed = 0
    use_cellar = bool(cfg.get("use_cellar"))
    for row in rows:
        raw = row["picked_url"]
        label = row["row_label"]
        if not raw or "<" in (raw or ""):
            print(f"  [SKIP] {label}: dirty URL")
            n_failed += 1
            continue
        # CELEX-based tables: build the Cellar resource URL from the CELEX.
        url = cellar_url_for_celex(raw) if use_cellar else raw
        blob, kind = http_fetch(url, cellar=use_cellar)
        if not blob:
            n_failed += 1
            time.sleep(args.throttle)
            continue
        text = extract_text(blob, kind)
        if len(text) < cfg["min_filled"]:
            print(f"  [SHORT] {label}: only {len(text)}c extracted")
            n_failed += 1
            time.sleep(args.throttle)
            continue
        n_filled += 1
        print(f"  [OK] {label}: {len(text)}c")
        if args.apply:
            cur.execute(update_sql, {"row_id": row["row_id"], "body": text})
            conn.commit()
        time.sleep(args.throttle)

    print(f"\n[DONE] Filled body on {n_filled} rows, {n_failed} failures.")
    if not args.apply:
        print("[NOTE] Dry-run — pass --apply to write to DB.")


if __name__ == "__main__":
    main()

"""
Backfill ``eu_cohesion_datasets`` from Socrata at cohesiondata.ec.europa.eu.

Source: ``/api/views.json`` returns the full catalog. Each entry is a
Socrata view with rich metadata: name, description, columns, tags,
view/download counts, ESF+/ERDF/CF/JTF/Interreg classification, and
the URL pattern for the actual rows API.

Run:
    python3.12 backend/scripts/backfill_eu_cohesion_datasets.py            # dry-run
    python3.12 backend/scripts/backfill_eu_cohesion_datasets.py --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from html import escape as html_escape
from pathlib import Path
from typing import Any
from urllib import request as ureq

import psycopg2
from psycopg2.extras import Json

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _specialised_helpers import ChunkedDb, get_env  # noqa: E402

CATALOG_URL = "https://cohesiondata.ec.europa.eu/api/views.json"
PUBLIC_URL_TPL = "https://cohesiondata.ec.europa.eu/d/{socrata_id}"
API_ENDPOINT_TPL = "https://cohesiondata.ec.europa.eu/resource/{socrata_id}.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
MIN_BODY_LEN = 200


def fetch_catalog() -> list[dict]:
    items: list[dict] = []
    page = 1
    while True:
        url = f"{CATALOG_URL}?limit=200&page={page}"
        req = ureq.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with ureq.urlopen(req, timeout=120) as r:
            payload = json.loads(r.read())
        if not payload:
            break
        items.extend(payload)
        if len(payload) < 200:
            break
        page += 1
        if page > 50:  # safety
            break
    return items


def compose_body(view: dict) -> tuple[str | None, str | None, str | None]:
    name = view.get("name") or ""
    desc = view.get("description") or ""
    cols = view.get("columns", []) or []
    tags = view.get("tags") or []
    if not name and not desc:
        return None, None, None

    # Composed body — name + description + tags + columns
    parts_text = []
    parts_html = []
    if desc:
        parts_text.append(f"Description\n\n{desc}")
        parts_html.append(f"<section><h2>Description</h2><p>{html_escape(desc)}</p></section>")
    if tags:
        parts_text.append("Tags\n\n" + ", ".join(tags))
        parts_html.append(f"<section><h2>Tags</h2><p>{html_escape(', '.join(tags))}</p></section>")
    if cols:
        col_lines = []
        col_html = ["<table><thead><tr><th>Field</th><th>Type</th><th>Description</th></tr></thead><tbody>"]
        for c in cols[:100]:
            cn = c.get("name") or "?"
            ct = (c.get("dataTypeName") or "?")
            cd = (c.get("description") or "").strip()
            col_lines.append(f"  - {cn}  ({ct})  {cd}".rstrip())
            col_html.append(
                f"<tr><td>{html_escape(cn)}</td><td>{html_escape(ct)}</td><td>{html_escape(cd)}</td></tr>"
            )
        col_html.append("</tbody></table>")
        parts_text.append("Columns\n\n" + "\n".join(col_lines))
        parts_html.append(f"<section><h2>Columns ({len(cols)})</h2>{''.join(col_html)}</section>")

    body_text = "\n\n".join(parts_text)
    body_html = f"<article>{''.join(parts_html)}</article>"
    return body_html, body_text, "cohesion_composed"


def to_iso(epoch_or_iso: Any) -> str | None:
    if epoch_or_iso is None or epoch_or_iso == "":
        return None
    if isinstance(epoch_or_iso, (int, float)):
        try:
            return datetime.utcfromtimestamp(int(epoch_or_iso)).isoformat()
        except Exception:
            return None
    s = str(epoch_or_iso)
    return s


UPSERT_SQL = """
INSERT INTO eu_cohesion_datasets (
    socrata_id, name, description, category, tags, attribution,
    download_count, view_count, row_count,
    last_updated_at, created_at_src, columns,
    public_url, api_endpoint,
    has_body, body_html, body_text, body_source,
    fetched_at, updated_at
) VALUES (
    %(socrata_id)s, %(name)s, %(description)s, %(category)s, %(tags)s, %(attribution)s,
    %(download_count)s, %(view_count)s, %(row_count)s,
    %(last_updated_at)s, %(created_at_src)s, %(columns)s,
    %(public_url)s, %(api_endpoint)s,
    %(has_body)s, %(body_html)s, %(body_text)s, %(body_source)s,
    NOW(), NOW()
)
ON CONFLICT (socrata_id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    category = EXCLUDED.category,
    tags = EXCLUDED.tags,
    attribution = EXCLUDED.attribution,
    download_count = EXCLUDED.download_count,
    view_count = EXCLUDED.view_count,
    row_count = EXCLUDED.row_count,
    last_updated_at = EXCLUDED.last_updated_at,
    columns = EXCLUDED.columns,
    public_url = EXCLUDED.public_url,
    api_endpoint = EXCLUDED.api_endpoint,
    has_body = EXCLUDED.has_body,
    body_html = EXCLUDED.body_html,
    body_text = EXCLUDED.body_text,
    body_source = EXCLUDED.body_source,
    updated_at = NOW();
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()

    print("[INFO] Fetching Cohesion Open Data catalog...", flush=True)
    items = fetch_catalog()
    print(f"[INFO] {len(items):,} datasets in catalog", flush=True)

    db = ChunkedDb()
    counts = {"upserted": 0, "with_body": 0, "errors": 0}

    rows = items if args.apply else items[: args.limit]
    for i, v in enumerate(rows, 1):
        socrata_id = v.get("id")
        if not socrata_id:
            continue
        body_html, body_text, body_source = compose_body(v)
        has_body = bool(body_text and len(body_text) >= MIN_BODY_LEN)
        if has_body:
            counts["with_body"] += 1

        # Convert epoch timestamps
        last_updated = to_iso(v.get("rowsUpdatedAt") or v.get("updatedAt") or v.get("indexUpdatedAt"))
        created_at_src = to_iso(v.get("createdAt"))

        params = {
            "socrata_id": socrata_id,
            "name": v.get("name"),
            "description": v.get("description"),
            "category": v.get("category"),
            "tags": v.get("tags") or [],
            "attribution": v.get("attribution"),
            "download_count": v.get("downloadCount"),
            "view_count": v.get("viewCount"),
            "row_count": (v.get("columns", [{}])[0].get("cachedContents", {}).get("count") if v.get("columns") else None),
            "last_updated_at": last_updated,
            "created_at_src": created_at_src,
            "columns": Json(v.get("columns") or []),
            "public_url": PUBLIC_URL_TPL.format(socrata_id=socrata_id),
            "api_endpoint": API_ENDPOINT_TPL.format(socrata_id=socrata_id),
            "has_body": has_body,
            "body_html": body_html if has_body else None,
            "body_text": body_text if has_body else None,
            "body_source": body_source if has_body else None,
        }

        if not args.apply:
            print(f"  [{i:3}] {socrata_id} | {(v.get('name') or '')[:50]:50} | "
                  f"cat={v.get('category','—')[:30]:30} | body={'+' if has_body else '—'}", flush=True)
            continue

        try:
            db.execute(UPSERT_SQL, params)
            counts["upserted"] += 1
            if counts["upserted"] % 50 == 0:
                db.commit()
                print(f"  [{i:3}/{len(items)}] {socrata_id} | upserted={counts['upserted']:,}", flush=True)
        except Exception as exc:
            db.rollback()
            counts["errors"] += 1
            print(f"  [{i:3}] DB error {socrata_id}: {exc!s}", flush=True)

    if args.apply:
        db.commit()
    print()
    print(f"[DONE] {counts}{' (DRY)' if not args.apply else ''}")
    db.close()


if __name__ == "__main__":
    main()

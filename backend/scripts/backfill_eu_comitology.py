"""
Backfill EU Comitology Register from the live JSON API.

Discovery method: Playwright network capture on
ec.europa.eu/transparency/comitology-register/screen/documents
revealed the real backend lives at /core/api/front/ (not the /api/front/
that the SPA's `<base href>` would suggest). The same API serves both
committees and documents.

Endpoints used:
  POST /core/api/front/documents/search?page=N&size=N   — list documents
  GET  /core/api/front/committees/codes                  — committee code list
  GET  /core/api/front/committees/{code}                 — single committee
  GET  /core/api/front/documentTypes                     — lookup
  GET  /core/api/front/legislativeProcedures             — lookup

Universe at time of writing: 112,832 documents across ~300 committees.

Run:
    python3.12 backend/scripts/backfill_eu_comitology.py            # dry-run
    python3.12 backend/scripts/backfill_eu_comitology.py --apply
    python3.12 backend/scripts/backfill_eu_comitology.py --apply --skip-documents
    python3.12 backend/scripts/backfill_eu_comitology.py --apply --skip-committees
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional
from urllib import request as ureq

from psycopg2.extras import Json

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _specialised_helpers import ChunkedDb  # noqa: E402

BASE = "https://ec.europa.eu/transparency/comitology-register/core/api/front"
# The Comitology Register is an Angular SPA. /screen/documents/{ref} on its own
# loads the SPA shell which then routes to the home screen unless the action
# segment (/consult) + language query are present. The "/consult?lang=en" form
# is the SPA's own deep-link convention — it's what the search UI navigates to
# when a user clicks a result. /committees/{code}/consult?lang=en mirrors the
# pattern for the committee detail view.
PUBLIC_DOC_URL_TPL = "https://ec.europa.eu/transparency/comitology-register/screen/documents/{reference}/consult?lang=en"
PUBLIC_COM_URL_TPL = "https://ec.europa.eu/transparency/comitology-register/screen/committees/{code}/consult?lang=en"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
PAGE_SIZE = 100
THROTTLE_S = 0.15


def get_json(url: str) -> dict | list:
    req = ureq.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with ureq.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def post_json(url: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = ureq.Request(url, data=data, headers={
        "User-Agent": UA, "Accept": "application/json", "Content-Type": "application/json",
    })
    with ureq.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


# ─────────────────────── Committees ──────────────────────────────────────


COMMITTEE_UPSERT_SQL = """
INSERT INTO eu_comitology_committees (
    code, title, dg_code, dg_title, parent_code, abolished_since,
    rules_procedure_filename, public_url, raw_json,
    fetched_at, updated_at
) VALUES (
    %(code)s, %(title)s, %(dg_code)s, %(dg_title)s, %(parent_code)s, %(abolished_since)s,
    %(rules_procedure_filename)s, %(public_url)s, %(raw_json)s,
    NOW(), NOW()
)
ON CONFLICT (code) DO UPDATE SET
    title = COALESCE(EXCLUDED.title, eu_comitology_committees.title),
    dg_code = COALESCE(EXCLUDED.dg_code, eu_comitology_committees.dg_code),
    dg_title = COALESCE(EXCLUDED.dg_title, eu_comitology_committees.dg_title),
    parent_code = COALESCE(EXCLUDED.parent_code, eu_comitology_committees.parent_code),
    abolished_since = EXCLUDED.abolished_since,
    rules_procedure_filename = COALESCE(EXCLUDED.rules_procedure_filename, eu_comitology_committees.rules_procedure_filename),
    public_url = EXCLUDED.public_url,
    raw_json = EXCLUDED.raw_json,
    fetched_at = NOW(),
    updated_at = NOW();
"""


def upsert_committees(db: ChunkedDb, throttle: float, dry_run: bool, limit: int = 0) -> int:
    print("[INFO] Fetching committee codes...", flush=True)
    codes = get_json(f"{BASE}/committees/codes")
    if not isinstance(codes, list):
        print(f"[WARN] codes response shape: {type(codes)}", flush=True)
        return 0
    print(f"[INFO] {len(codes):,} committees", flush=True)
    if dry_run:
        codes = codes[:limit] if limit else codes[:5]

    upserted = 0
    for i, code in enumerate(codes, 1):
        if i > 1:
            time.sleep(throttle)
        try:
            payload = get_json(f"{BASE}/committees/{code}")
        except Exception as exc:
            print(f"  [{i:3}] {code}: fetch error {exc!s}", flush=True)
            continue

        # Title from dg.dgTitles[0].title? No — committee TITLE is elsewhere.
        # Actually, the committee has its own titles array if present; otherwise
        # we use the DG title plus the code. Inspect the payload first time:
        title_obj = (payload.get("committeeTitles") or [{}])[0] if isinstance(payload.get("committeeTitles"), list) else {}
        title = title_obj.get("title") if isinstance(title_obj, dict) else None
        dg = payload.get("dg") or {}
        dg_code = dg.get("code") if isinstance(dg, dict) else None
        dg_titles = (dg.get("dgTitles") or [{}]) if isinstance(dg, dict) else [{}]
        dg_title = dg_titles[0].get("title") if dg_titles and isinstance(dg_titles[0], dict) else None
        parent = payload.get("parentCommittee") or {}
        parent_code = parent.get("code") if isinstance(parent, dict) else None
        rules = payload.get("rulesProcedures") or {}
        rules_filename = rules.get("filename") if isinstance(rules, dict) else None

        params = {
            "code": code,
            "title": title,
            "dg_code": dg_code,
            "dg_title": dg_title,
            "parent_code": parent_code,
            "abolished_since": payload.get("abolishedSince"),
            "rules_procedure_filename": rules_filename,
            "public_url": PUBLIC_COM_URL_TPL.format(code=code),
            "raw_json": Json(payload),
        }
        if dry_run:
            print(f"  [{i:3}] {code} | dg={dg_code or '—'} | parent={parent_code or '—'} | title={(title or '')[:60]}", flush=True)
            continue
        try:
            db.execute(COMMITTEE_UPSERT_SQL, params)
            upserted += 1
            if upserted % 50 == 0:
                db.commit()
                print(f"  [{i:3}/{len(codes)}] {code} | upserted={upserted}", flush=True)
        except Exception as exc:
            db.rollback()
            print(f"  [{i:3}] DB error {code}: {exc!s}", flush=True)

    db.commit()
    print(f"[DONE committees] upserted={upserted}/{len(codes)}")
    return upserted


# ─────────────────────── Documents ───────────────────────────────────────


DOC_UPSERT_SQL = """
INSERT INTO eu_comitology_documents (
    document_reference, title, meeting_code, committee_code, committee_title,
    document_type, document_type_label, document_type_letter,
    creation_date, update_date, meeting_start_date, meeting_end_date,
    version, public_url,
    fetched_at, updated_at
) VALUES (
    %(document_reference)s, %(title)s, %(meeting_code)s, %(committee_code)s, %(committee_title)s,
    %(document_type)s, %(document_type_label)s, %(document_type_letter)s,
    %(creation_date)s, %(update_date)s, %(meeting_start_date)s, %(meeting_end_date)s,
    %(version)s, %(public_url)s,
    NOW(), NOW()
)
ON CONFLICT (document_reference) DO UPDATE SET
    title = EXCLUDED.title,
    meeting_code = EXCLUDED.meeting_code,
    committee_code = EXCLUDED.committee_code,
    committee_title = EXCLUDED.committee_title,
    document_type = EXCLUDED.document_type,
    document_type_label = EXCLUDED.document_type_label,
    document_type_letter = EXCLUDED.document_type_letter,
    creation_date = EXCLUDED.creation_date,
    update_date = EXCLUDED.update_date,
    meeting_start_date = EXCLUDED.meeting_start_date,
    meeting_end_date = EXCLUDED.meeting_end_date,
    version = EXCLUDED.version,
    public_url = EXCLUDED.public_url,
    updated_at = NOW();
"""


def upsert_documents(db: ChunkedDb, throttle: float, dry_run: bool, limit: int = 0) -> int:
    page = 0
    total = 0
    counts = {"upserted": 0, "errors": 0}
    print("[INFO] Paging through Comitology documents...", flush=True)
    while True:
        try:
            payload = post_json(f"{BASE}/documents/search?page={page}&size={PAGE_SIZE}", {})
        except Exception as exc:
            print(f"  [page {page}] fetch error {exc!s}", flush=True)
            counts["errors"] += 1
            page += 1
            if counts["errors"] >= 5:
                break
            continue
        if not isinstance(payload, dict):
            break
        if total == 0:
            total = payload.get("totalElements", 0)
            print(f"[INFO] {total:,} documents total", flush=True)
        rows = payload.get("content") or []
        if not rows:
            break

        for row in rows:
            doc_ref = row.get("documentReference")
            if not doc_ref:
                continue
            dt = row.get("documentType") or {}
            params = {
                "document_reference": doc_ref,
                "title": row.get("title"),
                "meeting_code": row.get("meetingCode"),
                "committee_code": row.get("committeeCode"),
                "committee_title": row.get("committeeTitle"),
                "document_type": Json(dt) if isinstance(dt, dict) and dt else None,
                "document_type_label": dt.get("label") if isinstance(dt, dict) else None,
                "document_type_letter": dt.get("letter") if isinstance(dt, dict) else None,
                "creation_date": row.get("creationDate"),
                "update_date": row.get("updateDate"),
                "meeting_start_date": row.get("meetingStartDate"),
                "meeting_end_date": row.get("meetingEndDate"),
                "version": row.get("version"),
                "public_url": PUBLIC_DOC_URL_TPL.format(reference=doc_ref),
            }
            if dry_run:
                print(f"  {doc_ref} | {row.get('committeeCode','—')} | {row.get('title','')[:60]}", flush=True)
                continue
            try:
                db.execute(DOC_UPSERT_SQL, params)
                counts["upserted"] += 1
            except Exception as exc:
                db.rollback()
                counts["errors"] += 1
                print(f"  [{doc_ref}] DB error: {exc!s}", flush=True)

        if not dry_run:
            db.commit()
            print(f"  [page {page:4}] upserted={counts['upserted']:,} of {total:,}", flush=True)

        page += 1
        if dry_run and (limit and counts["upserted"] >= limit):
            break
        if payload.get("last", True):
            break
        time.sleep(throttle)

    if not dry_run:
        db.commit()
    print(f"[DONE documents] upserted={counts['upserted']:,} of {total:,}")
    return counts["upserted"]


# ─────────────────────── Main ────────────────────────────────────────────


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--throttle", type=float, default=THROTTLE_S)
    ap.add_argument("--skip-committees", action="store_true")
    ap.add_argument("--skip-documents", action="store_true")
    args = ap.parse_args()

    db = ChunkedDb()
    try:
        if not args.skip_committees:
            upsert_committees(db, args.throttle, dry_run=not args.apply, limit=args.limit if not args.apply else 0)
        if not args.skip_documents:
            upsert_documents(db, args.throttle, dry_run=not args.apply, limit=args.limit)
    finally:
        db.close()


if __name__ == "__main__":
    main()

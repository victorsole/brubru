"""
Backfill ``eu_geographical_indications`` from eAmbrosia + GIview.

Source 1: eAmbrosia at ``webgate.ec.europa.eu/eambrosia-api/api/v1/``
  - GET /geographical-indications?lang=en — single call, ~3,994 records,
    deep per-record detail (legal_instrument with CELEX, summary sheets
    with attachment IDs, producer group, competent authorities, CN
    classification, sustainability reports).
  - GET /attachments/{attachmentId} — fetch a summary sheet for body.

Source 2: GIview at ``tmdn.org/giview/api/search/union_register``
  - POST {"size":1,"page":0} — single call, ~5,809 records (broader,
    includes pending applications + additional third-country GIs).

The backfill UPSERTs eAmbrosia first (source='eambrosia'), then merges
GIview-only records (source='giview' for IDs not in eAmbrosia).

Optional --enrich-bodies pass: walks the table, looks up the first
summary sheet attachment per row, fetches the file from eAmbrosia, and
writes body_html/body_text. Skips rows that already have a body unless
--refresh-bodies is set.

Run:
    python3.12 backend/scripts/backfill_eu_gi.py            # dry-run, 5 rows
    python3.12 backend/scripts/backfill_eu_gi.py --apply
    python3.12 backend/scripts/backfill_eu_gi.py --apply --enrich-bodies
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

import psycopg2
from psycopg2.extras import Json

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _specialised_helpers import ChunkedDb, get_env, strip_html_to_text  # noqa: E402

EAMBROSIA_BASE = "https://webgate.ec.europa.eu/eambrosia-api"
GIVIEW_URL = "https://www.tmdn.org/giview/api/search/union_register"
PUBLIC_URL_TPL = "https://webgate.ec.europa.eu/eambrosia/#searchTab=protectedProducts&giIdentifier={gi}"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
)
THROTTLE_S = 0.5
MIN_BODY_LEN = 200  # Summary sheets can be short


# ─────────────────────── HTTP helpers ────────────────────────────────────


def get_json(url: str, *, timeout: int = 60) -> Any:
    req = urllib_request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/json",
        "Accept-Language": "en",
    })
    with urllib_request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def post_json(url: str, body: dict, *, timeout: int = 60) -> Any:
    data = json.dumps(body).encode()
    req = urllib_request.Request(url, data=data, headers={
        "User-Agent": UA,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Accept-Language": "en",
    })
    with urllib_request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def fetch_attachment(attachment_id: str) -> tuple[Optional[bytes], Optional[str]]:
    """eAmbrosia attachment download. Returns (bytes, content_type)."""
    url = f"{EAMBROSIA_BASE}/api/v1/attachments/{attachment_id}"
    req = urllib_request.Request(url, headers={
        "User-Agent": UA, "Accept": "*/*", "Accept-Language": "en",
    })
    try:
        with urllib_request.urlopen(req, timeout=45) as r:
            ctype = (r.headers.get("Content-Type") or "").lower()
            return r.read(), ctype
    except (urllib_error.HTTPError, urllib_error.URLError):
        return None, None
    except Exception:
        return None, None


def extract_pdf_text(pdf_bytes: bytes) -> Optional[str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader  # type: ignore
    try:
        import io
        reader = PdfReader(io.BytesIO(pdf_bytes))
        return "\n\n".join((p.extract_text() or "") for p in reader.pages).strip() or None
    except Exception:
        return None


# ─────────────────────── Date parsing ────────────────────────────────────


def parse_date(value: Any) -> Optional[str]:
    if not value:
        return None
    s = str(value)
    if "T" in s:
        s = s.split("T")[0]
    return s if re.match(r"^\d{4}-\d{2}-\d{2}$", s) else None


def parse_ts(value: Any) -> Optional[str]:
    if not value:
        return None
    s = str(value)
    # "2022-12-01T11:37:06.395Z"
    if re.match(r"^\d{4}-\d{2}-\d{2}T", s):
        return s
    return None


# ─────────────────────── UPSERTs ─────────────────────────────────────────


UPSERT_FROM_EAMBROSIA = """
INSERT INTO eu_geographical_indications (
    gi_identifier, protected_names, file_number, countries, third_country_flag,
    gi_type, product_type, product_categories, cn_classification,
    status, eu_protection_date, modification_date,
    amendments_in_progress, removed_flag,
    legal_instrument, publications, single_document, summary_sheets,
    transcriptions, amendments,
    producer_group_name, producer_group_email, producer_group_phone,
    producer_group_url, producer_group_address, producer_group_country,
    producer_group_updated_on,
    competent_control_authorities, recognised_producers_group, sustainability_reports,
    source, eambrosia_url, eurlex_url, public_url,
    fetched_at, updated_at
) VALUES (
    %(gi_identifier)s, %(protected_names)s, %(file_number)s, %(countries)s, %(third_country_flag)s,
    %(gi_type)s, %(product_type)s, %(product_categories)s, %(cn_classification)s,
    %(status)s, %(eu_protection_date)s, %(modification_date)s,
    %(amendments_in_progress)s, %(removed_flag)s,
    %(legal_instrument)s, %(publications)s, %(single_document)s, %(summary_sheets)s,
    %(transcriptions)s, %(amendments)s,
    %(producer_group_name)s, %(producer_group_email)s, %(producer_group_phone)s,
    %(producer_group_url)s, %(producer_group_address)s, %(producer_group_country)s,
    %(producer_group_updated_on)s,
    %(competent_control_authorities)s, %(recognised_producers_group)s, %(sustainability_reports)s,
    'eambrosia', %(eambrosia_url)s, %(eurlex_url)s, %(public_url)s,
    NOW(), NOW()
)
ON CONFLICT (gi_identifier) DO UPDATE SET
    protected_names = EXCLUDED.protected_names,
    file_number = EXCLUDED.file_number,
    countries = EXCLUDED.countries,
    third_country_flag = EXCLUDED.third_country_flag,
    gi_type = EXCLUDED.gi_type,
    product_type = EXCLUDED.product_type,
    product_categories = EXCLUDED.product_categories,
    cn_classification = EXCLUDED.cn_classification,
    status = EXCLUDED.status,
    eu_protection_date = EXCLUDED.eu_protection_date,
    modification_date = EXCLUDED.modification_date,
    amendments_in_progress = EXCLUDED.amendments_in_progress,
    removed_flag = EXCLUDED.removed_flag,
    legal_instrument = EXCLUDED.legal_instrument,
    publications = EXCLUDED.publications,
    single_document = EXCLUDED.single_document,
    summary_sheets = EXCLUDED.summary_sheets,
    transcriptions = EXCLUDED.transcriptions,
    amendments = EXCLUDED.amendments,
    producer_group_name = EXCLUDED.producer_group_name,
    producer_group_email = EXCLUDED.producer_group_email,
    producer_group_phone = EXCLUDED.producer_group_phone,
    producer_group_url = EXCLUDED.producer_group_url,
    producer_group_address = EXCLUDED.producer_group_address,
    producer_group_country = EXCLUDED.producer_group_country,
    producer_group_updated_on = EXCLUDED.producer_group_updated_on,
    competent_control_authorities = EXCLUDED.competent_control_authorities,
    recognised_producers_group = EXCLUDED.recognised_producers_group,
    sustainability_reports = EXCLUDED.sustainability_reports,
    source = 'eambrosia',
    eambrosia_url = EXCLUDED.eambrosia_url,
    eurlex_url = EXCLUDED.eurlex_url,
    public_url = EXCLUDED.public_url,
    updated_at = NOW();
"""


UPSERT_FROM_GIVIEW = """
INSERT INTO eu_geographical_indications (
    gi_identifier, protected_names, file_number, countries, third_country_flag,
    gi_type, product_type, status, eu_protection_date, modification_date,
    amendments_in_progress,
    legal_instrument, publications, single_document, summary_sheets,
    transcriptions, amendments,
    map_locations,
    source, giview_source, giview_database, eurlex_url, public_url,
    fetched_at, updated_at
) VALUES (
    %(gi_identifier)s, %(protected_names)s, %(file_number)s, %(countries)s, %(third_country_flag)s,
    %(gi_type)s, %(product_type)s, %(status)s, %(eu_protection_date)s, %(modification_date)s,
    %(amendments_in_progress)s,
    %(legal_instrument)s, %(publications)s, %(single_document)s, %(summary_sheets)s,
    %(transcriptions)s, %(amendments)s,
    %(map_locations)s,
    'giview', %(giview_source)s, %(giview_database)s, %(eurlex_url)s, %(public_url)s,
    NOW(), NOW()
)
ON CONFLICT (gi_identifier) DO UPDATE SET
    -- Only fill fields that aren't already set from eAmbrosia
    protected_names = COALESCE(NULLIF(eu_geographical_indications.protected_names, ARRAY[]::TEXT[]),
                               EXCLUDED.protected_names),
    countries = COALESCE(NULLIF(eu_geographical_indications.countries, ARRAY[]::TEXT[]),
                         EXCLUDED.countries),
    map_locations = COALESCE(eu_geographical_indications.map_locations, EXCLUDED.map_locations),
    giview_source = COALESCE(EXCLUDED.giview_source, eu_geographical_indications.giview_source),
    giview_database = COALESCE(EXCLUDED.giview_database, eu_geographical_indications.giview_database),
    -- Mark as 'merged' if eAmbrosia had this row
    source = CASE WHEN eu_geographical_indications.source = 'eambrosia' THEN 'merged'
                  ELSE eu_geographical_indications.source END,
    updated_at = NOW();
"""


# ─────────────────────── Backfill Phase 1: eAmbrosia ─────────────────────


def upsert_from_eambrosia(db: ChunkedDb, dry_run: bool = False, limit: int = 0) -> int:
    print("[INFO] Fetching eAmbrosia /geographical-indications...", flush=True)
    payload = get_json(f"{EAMBROSIA_BASE}/api/v1/geographical-indications?lang=en")
    if not isinstance(payload, list):
        print(f"[WARN] Unexpected eAmbrosia response shape: {type(payload)}", flush=True)
        return 0
    print(f"[INFO] {len(payload):,} GIs from eAmbrosia", flush=True)

    if limit:
        payload = payload[:limit]

    upserted = 0
    for i, gi in enumerate(payload, 1):
        gi_id = gi.get("giIdentifier")
        if not gi_id:
            continue
        legal = gi.get("legalInstrument") or {}
        eurlex_url = (legal.get("uri") if isinstance(legal, dict) else None)
        params = {
            "gi_identifier": gi_id,
            "protected_names": gi.get("protectedNames") or [],
            "file_number": gi.get("fileNumber"),
            "countries": gi.get("countries") or [],
            "third_country_flag": gi.get("thirdCountryFlag"),
            "gi_type": gi.get("giType"),
            "product_type": gi.get("productType"),
            "product_categories": Json(gi.get("productCategories") or []),
            "cn_classification": Json(gi.get("cnClassification") or []),
            "status": gi.get("status"),
            "eu_protection_date": parse_date(gi.get("euProtectionDate")),
            "modification_date": parse_ts(gi.get("modificationDate")),
            "amendments_in_progress": gi.get("amendmentsInProgressFlag"),
            "removed_flag": gi.get("removedFlag"),
            "legal_instrument": Json(legal),
            "publications": Json(gi.get("publications") or []),
            "single_document": Json(gi.get("singleDocument")) if gi.get("singleDocument") else None,
            "summary_sheets": Json(gi.get("summarySheets") or []),
            "transcriptions": Json(gi.get("transcriptions")) if gi.get("transcriptions") else None,
            "amendments": Json(gi.get("amendments")) if gi.get("amendments") else None,
            "producer_group_name": gi.get("producerGroupName"),
            "producer_group_email": gi.get("producerGroupEmail"),
            "producer_group_phone": gi.get("producerGroupPhone"),
            "producer_group_url": gi.get("producerGroupUrl"),
            "producer_group_address": gi.get("producerGroupAdress"),  # API misspells "Address"
            "producer_group_country": gi.get("producerGroupCountry"),
            "producer_group_updated_on": parse_ts(gi.get("producerGroupUpdatedOn")),
            "competent_control_authorities": Json(gi.get("competentControlAuthorities") or []),
            "recognised_producers_group": Json(gi.get("recognisedProducersGroup") or []),
            "sustainability_reports": Json(gi.get("sustainabilityReports") or []),
            "eambrosia_url": f"{EAMBROSIA_BASE}/api/v1/geographical-indications/{gi_id}",
            "eurlex_url": eurlex_url,
            "public_url": PUBLIC_URL_TPL.format(gi=gi_id),
        }

        if dry_run:
            print(f"  [{i:4}] {gi_id} {gi.get('giType','?'):4} | "
                  f"names={(gi.get('protectedNames') or ['—'])[0][:50]} | "
                  f"file={gi.get('fileNumber','—')}", flush=True)
            continue

        try:
            db.execute(UPSERT_FROM_EAMBROSIA, params)
            upserted += 1
            if upserted % 500 == 0:
                db.commit()
                print(f"  [{i:4}/{len(payload)}] {gi_id} | upserted={upserted:,}", flush=True)
        except Exception as exc:
            db.rollback()
            print(f"  [{i:4}] DB error {gi_id}: {exc!s}", flush=True)

    if not dry_run:
        db.commit()
    print(f"[DONE eAmbrosia] upserted={upserted:,} of {len(payload):,}")
    return upserted


# ─────────────────────── Backfill Phase 2: GIview ────────────────────────


def upsert_from_giview(db: ChunkedDb, dry_run: bool = False) -> tuple[int, int]:
    print("[INFO] Fetching GIview union_register...", flush=True)
    try:
        payload = post_json(GIVIEW_URL, {"size": 1, "page": 0})
    except Exception as exc:
        print(f"[WARN] GIview fetch failed: {exc!s}", flush=True)
        return 0, 0
    records = payload.get("resultRecords") or []
    print(f"[INFO] {len(records):,} GIs from GIview "
          f"(API total {payload.get('totalRecords')})", flush=True)

    new_or_merged = 0
    for i, rec in enumerate(records, 1):
        gi_id = rec.get("id")
        if not gi_id:
            continue
        basic = rec.get("basicData") or {}
        legal = basic.get("legalInstrument") or {}
        params = {
            "gi_identifier": gi_id,
            "protected_names": basic.get("protectedNames") or [],
            "file_number": basic.get("fileNumber"),
            "countries": basic.get("countries") or [],
            "third_country_flag": None,  # GIview doesn't carry this; eAmbrosia does
            "gi_type": basic.get("giType"),
            "product_type": basic.get("productType"),
            "status": (basic.get("status") or "").lower() or None,
            "eu_protection_date": parse_date(basic.get("euProtectionDate")),
            "modification_date": parse_ts(basic.get("modificationDate")),
            "amendments_in_progress": basic.get("amendmentsInProgressFlag"),
            "legal_instrument": Json(legal) if legal else None,
            "publications": Json(basic.get("publications") or []),
            "single_document": Json(basic.get("singleDocument")) if basic.get("singleDocument") else None,
            "summary_sheets": Json(basic.get("summarySheets")) if basic.get("summarySheets") else None,
            "transcriptions": Json(basic.get("transcriptions")) if basic.get("transcriptions") else None,
            "amendments": Json(basic.get("amendments")) if basic.get("amendments") else None,
            "map_locations": Json(rec.get("mapLocations") or []),
            "giview_source": rec.get("source"),
            "giview_database": rec.get("database"),
            "eurlex_url": (legal.get("uri") if isinstance(legal, dict) else None),
            "public_url": PUBLIC_URL_TPL.format(gi=gi_id),
        }

        if dry_run:
            print(f"  [{i:4}] {gi_id} {basic.get('giType','?'):4} | "
                  f"names={(basic.get('protectedNames') or ['—'])[0][:40]} | "
                  f"src={rec.get('source')}", flush=True)
            continue

        try:
            db.execute(UPSERT_FROM_GIVIEW, params)
            new_or_merged += 1
            if new_or_merged % 500 == 0:
                db.commit()
                print(f"  [{i:4}/{len(records)}] {gi_id} | giview-merged={new_or_merged:,}", flush=True)
        except Exception as exc:
            db.rollback()
            print(f"  [{i:4}] GIview DB error {gi_id}: {exc!s}", flush=True)

    if not dry_run:
        db.commit()
    print(f"[DONE GIview] processed={new_or_merged:,}")
    return len(records), new_or_merged


# ─────────────────────── Body enrichment ─────────────────────────────────


_ELI_REG_PAT = re.compile(r"/eli/(reg_impl|reg|dec_impl|dec)/(\d{4})/(\d+)(?:[/?]|$)")
_CELEX_PAT = re.compile(r"CELEX[%:]?3A?(3\d{4}[A-Z]+\d+)")


def derive_celex_from_publication(uri: str) -> Optional[str]:
    """Map an eAmbrosia publications[].uri (ELI or EUR-Lex CELEX URL) to a CELEX.

    Examples:
      http://data.europa.eu/eli/reg_impl/2025/2340/oj   -> 32025R2340
      http://data.europa.eu/eli/reg/2024/834/oj         -> 32024R0834
      https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32013R1308 -> 32013R1308
    """
    if not uri:
        return None
    m = _ELI_REG_PAT.search(uri)
    if m:
        kind, year, num = m.groups()
        type_letter = {"reg_impl": "R", "reg": "R", "dec_impl": "D", "dec": "D"}.get(kind, "R")
        return f"3{year}{type_letter}{num.zfill(4)}"
    m = _CELEX_PAT.search(uri)
    if m:
        return m.group(1)
    return None


def enrich_bodies(db: ChunkedDb, throttle: float, refresh: bool = False) -> dict:
    """Walk eu_geographical_indications, derive a CELEX from each row's
    `publications[].uri` (ELI URIs to EUR-Lex), fetch the regulation body
    from Cellar (XHTML preferred, PDF fallback), and store body_html /
    body_text / body_source.

    eAmbrosia's `summarySheets` attachments are referenced as numeric IDs
    on a Webgate endpoint (/api/v1/attachments/{id}) that consistently
    returns HTTP 500 — the service is broken or auth-walled and the
    legacy /eambrosia/services/attachment endpoint redirects to the
    agriportal login page. Cellar via publications is the honest path:
    the body of a GI registration IS the regulation that registered it.
    """
    from _specialised_helpers import fetch_body_for_celex  # local import

    where = "" if refresh else "WHERE has_body IS NOT TRUE"
    db.execute(f"""
        SELECT gi_identifier, publications, legal_instrument, source
          FROM eu_geographical_indications
          {where}
         ORDER BY modification_date DESC NULLS LAST
    """)
    rows = db.fetchall()
    print(f"[INFO] {len(rows):,} GI rows to enrich with body via Cellar", flush=True)

    counts = {"written": 0, "no_celex": 0, "body_xhtml": 0, "body_pdf": 0,
              "no_body": 0, "errors": 0}

    for i, (gi_id, publications, legal_instrument, source) in enumerate(rows, 1):
        # Try publications first (registration regulations), fall back to legal_instrument.
        celex_candidates: list[str] = []
        if isinstance(publications, list):
            for pub in publications:
                if isinstance(pub, dict) and pub.get("uri"):
                    cx = derive_celex_from_publication(pub["uri"])
                    if cx:
                        celex_candidates.append(cx)
        if not celex_candidates and isinstance(legal_instrument, dict):
            cx = derive_celex_from_publication(legal_instrument.get("uri", ""))
            if cx:
                celex_candidates.append(cx)

        if not celex_candidates:
            counts["no_celex"] += 1
            if i % 250 == 0:
                print(f"  [{i:4}/{len(rows)}] running totals: {counts}", flush=True)
            continue

        # Walk candidates from most-recent backwards (publications often listed oldest first).
        body_html = body_text = body_source = None
        for celex in reversed(celex_candidates):
            time.sleep(throttle if i > 1 else 0)
            body_html, body_text, body_source = fetch_body_for_celex(celex)
            if body_text and len(body_text) >= MIN_BODY_LEN:
                break
            body_html = body_text = body_source = None

        if not body_text:
            counts["no_body"] += 1
            if i % 250 == 0:
                print(f"  [{i:4}/{len(rows)}] running totals: {counts}", flush=True)
            continue

        counts[f"body_{body_source}"] = counts.get(f"body_{body_source}", 0) + 1

        try:
            db.execute(
                """
                UPDATE eu_geographical_indications
                   SET has_body = true,
                       body_html = %(body_html)s,
                       body_text = %(body_text)s,
                       body_source = %(body_source)s,
                       fetched_at = NOW(),
                       updated_at = NOW()
                 WHERE gi_identifier = %(gi)s
                """,
                {"gi": gi_id, "body_html": body_html, "body_text": body_text,
                 "body_source": f"cellar_{body_source}"},
            )
            counts["written"] += 1
            if counts["written"] % 50 == 0:
                db.commit()
                print(f"  [{i:4}/{len(rows)}] {gi_id} | bodies={counts['written']:,} "
                      f"xhtml={counts.get('body_xhtml',0)} pdf={counts.get('body_pdf',0)} "
                      f"no_body={counts['no_body']} no_celex={counts['no_celex']}", flush=True)
        except Exception as exc:
            db.rollback()
            counts["errors"] += 1
            print(f"  [{i:4}] body upsert error {gi_id}: {exc!s}", flush=True)

    db.commit()
    return counts


# ─────────────────────── Main ────────────────────────────────────────────


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--throttle", type=float, default=THROTTLE_S)
    ap.add_argument("--enrich-bodies", action="store_true",
                    help="After metadata UPSERT, fetch attachment PDFs and populate body fields")
    ap.add_argument("--refresh-bodies", action="store_true",
                    help="Re-fetch body even if has_body=true")
    ap.add_argument("--skip-eambrosia", action="store_true")
    ap.add_argument("--skip-giview", action="store_true")
    args = ap.parse_args()

    db = ChunkedDb()

    try:
        if not args.skip_eambrosia:
            upsert_from_eambrosia(db, dry_run=not args.apply, limit=args.limit if not args.apply else 0)

        if not args.skip_giview:
            upsert_from_giview(db, dry_run=not args.apply)

        if args.enrich_bodies and args.apply:
            print()
            counts = enrich_bodies(db, throttle=args.throttle, refresh=args.refresh_bodies)
            print(f"\n[DONE bodies] {counts}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

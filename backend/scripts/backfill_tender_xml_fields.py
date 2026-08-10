#!/usr/bin/env python3.12
"""Backfill procedure_type / CPV / contract_nature / award_criteria / lots
for tenders rows whose only TED-enrichment was the basic search-result
record (these come from the bulk-load scripts in scripts/load_*_tenders.py).

Strategy:
  - Find tenders where procedure_type IS NULL OR procedure_type = ''.
  - For each, fetch the eForms XML from TED via TEDClient.get_notice_xml.
  - Parse the XML via EFormsParser.parse_to_tender_dict.
  - Whitelist-update the row: never overwrite existing non-empty title or
    description (the parser sometimes returns empty strings — see incident
    15 Jun 2026 with notices 00868415-2025 / 00868416-2025).
  - Title fallback: if both parsed.title and existing.title are empty,
    use the FIRST <cac:ProcurementProject>/<cbc:Name>, which is the
    notice's project name.

Idempotent. Concurrency-capped.

Usage:
    python3.12 scripts/backfill_tender_xml_fields.py --limit 5
    python3.12 scripts/backfill_tender_xml_fields.py --all --concurrency 4
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import SessionLocal  # noqa: E402
from models.tender import Tender  # noqa: E402
from services.tenders.eforms_parser import EFormsParser  # noqa: E402
from services.tenders.ted_client import TEDClient  # noqa: E402

NS = {
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}

# Fields we are willing to update from the parsed XML. Title + description
# are special-cased (only filled when target is empty).
SAFE_FIELDS = {
    "procedure_type", "cpv_codes", "cpv_main", "nuts_codes",
    "contract_nature", "estimated_value", "estimated_value_currency",
    "contract_duration_months", "award_criteria_type", "award_criteria",
    "selection_criteria", "exclusion_grounds", "minimum_requirements",
    "has_lots", "lot_count", "lots", "documents_url", "submission_url",
    "is_framework", "xml_content", "raw_json", "form_type",
    "notice_subtype", "notice_id", "submission_deadline",
    # Added 10 Aug 2026: the parser now returns a validated alpha-2 here
    # (it used to return the raw eForms alpha-3, three characters into a
    # varchar(2) column), so re-parsing can repair the rows the TED SPARQL
    # loader filled with language codes.
    "buyer_country",
}


def _extract_project_name(xml_text: str) -> str | None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    for proj in root.findall(".//cac:ProcurementProject", NS):
        name = proj.find("cbc:Name", NS)
        if name is not None and (name.text or "").strip():
            return name.text.strip()
    return None


def _pending_pub_numbers(limit: int | None, mode: str) -> list[str]:
    """Return publication_number values that still need XML enrichment.

    Modes:
      'procedure' — only rows with NULL/empty procedure_type (initial pass).
      'subtype'   — rows that never went through XML parsing (notice_subtype IS NULL).
                    These are older bulk-loaded rows with award_criteria etc. still missing.
      'all'       — union of both.
    """
    db = SessionLocal()
    try:
        q = db.query(Tender.publication_number)
        if mode == "procedure":
            q = q.filter((Tender.procedure_type.is_(None)) | (Tender.procedure_type == ""))
        elif mode == "subtype":
            q = q.filter(Tender.notice_subtype.is_(None))
        else:  # 'all'
            q = q.filter(
                (Tender.procedure_type.is_(None))
                | (Tender.procedure_type == "")
                | (Tender.notice_subtype.is_(None))
            )
        q = q.order_by(Tender.id.desc())
        if limit:
            q = q.limit(limit)
        return [r[0] for r in q.all() if r[0]]
    finally:
        db.close()


async def _process_one(client: TEDClient, pub: str, parser: EFormsParser,
                       stats: dict, sem: asyncio.Semaphore):
    async with sem:
        try:
            xml_text = await client.get_notice_xml(pub)
            if not xml_text:
                stats["miss"] += 1
                print(f"  [miss] {pub}: no XML", flush=True)
                return

            parsed = parser.parse_to_tender_dict(xml_text, pub)

            db = SessionLocal()
            try:
                tender = db.query(Tender).filter(
                    Tender.publication_number == pub
                ).first()
                if not tender:
                    stats["miss"] += 1
                    print(f"  [miss] {pub}: row vanished", flush=True)
                    return

                # Whitelist-update.
                for key, val in parsed.items():
                    if key not in SAFE_FIELDS:
                        continue
                    if val is None:
                        continue
                    # Skip empty containers that would clobber prior data.
                    if isinstance(val, (str, list, dict)) and len(val) == 0:
                        continue
                    setattr(tender, key, val)

                # Title: only if currently empty.
                if not (tender.title or "").strip():
                    cand = (parsed.get("title") or "").strip() or _extract_project_name(xml_text)
                    if cand:
                        tender.title = cand[:1000]

                # Description: same rule.
                if not (tender.description or "").strip():
                    desc = (parsed.get("description") or "").strip()
                    if desc:
                        tender.description = desc

                tender.updated_at = datetime.utcnow()
                tender.last_synced_at = datetime.utcnow()
                db.commit()

                if tender.procedure_type:
                    stats["ok"] += 1
                    if stats["ok"] % 10 == 0:
                        print(f"  ... enriched {stats['ok']}/{stats['total']}", flush=True)
                else:
                    stats["empty"] += 1
                    print(f"  [warn] {pub}: XML parsed but no procedure_type", flush=True)
            finally:
                db.close()
        except Exception as e:
            stats["err"] += 1
            print(f"  [err] {pub}: {str(e)[:160]}", flush=True)


async def run(limit: int | None, concurrency: int, mode: str):
    pubs = _pending_pub_numbers(limit, mode)
    if not pubs:
        print("No pending rows.")
        return
    print(f"[backfill] {len(pubs)} rows pending, concurrency={concurrency}", flush=True)
    stats = {"ok": 0, "miss": 0, "empty": 0, "err": 0, "total": len(pubs)}
    parser = EFormsParser()
    sem = asyncio.Semaphore(concurrency)
    async with TEDClient() as client:
        await asyncio.gather(*[
            _process_one(client, p, parser, stats, sem) for p in pubs
        ])
    print(f"[backfill] done. ok={stats['ok']} miss={stats['miss']} "
          f"empty={stats['empty']} err={stats['err']}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="cap rows (default: all)")
    ap.add_argument("--all", action="store_true", help="run on every pending row")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--mode", choices=["procedure", "subtype", "all"], default="procedure",
                    help="'procedure' = rows missing procedure_type (initial pass), "
                         "'subtype' = rows that never went through XML parsing "
                         "(award_criteria gap), 'all' = both")
    args = ap.parse_args()

    if not args.limit and not args.all:
        ap.error("provide --limit N or --all")

    asyncio.run(run(args.limit, args.concurrency, args.mode))


if __name__ == "__main__":
    sys.exit(main())

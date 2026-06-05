"""Backfill / refresh EP eMeeting committee agendas (ep_emeeting_agendas).

Pure-JSON integration with the European Parliament eMeeting open API (no WAF).
Fetches the most recent agendas for each committee, normalises items + documents,
composes bodies, and upserts into ep_emeeting_agendas (migration 110).

Usage:
    cd backend
    python3.12 scripts/sync_ep_emeeting.py                       # 6 newest per committee, all 26
    python3.12 scripts/sync_ep_emeeting.py --per-committee 10
    python3.12 scripts/sync_ep_emeeting.py --committee AFCO --committee ENVI
    python3.12 scripts/sync_ep_emeeting.py --dry-run
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import SessionLocal
from models.ep_emeeting_agenda import EpEmeetingAgenda
from models.ep_emeeting_document import EpEmeetingDocument
from services.scrapers.ep_emeeting_client import (
    committee_index, fetch_committee, documents_from_agenda,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("sync_ep_emeeting")


def upsert(db, row: dict):
    """Upsert an agenda. Returns (EpEmeetingAgenda, is_new)."""
    existing = db.query(EpEmeetingAgenda).filter(
        EpEmeetingAgenda.oj_reference == row["oj_reference"]
    ).first()
    if existing is None:
        obj = EpEmeetingAgenda(**row)
        db.add(obj)
        return obj, True
    for k, v in row.items():
        setattr(existing, k, v)
    return existing, False


def upsert_document(db, row: dict) -> bool:
    existing = db.query(EpEmeetingDocument).filter(
        EpEmeetingDocument.document_key == row["document_key"]
    ).first()
    if existing is None:
        db.add(EpEmeetingDocument(**row))
        return True
    for k, v in row.items():
        setattr(existing, k, v)
    return False


def main():
    ap = argparse.ArgumentParser(description="Backfill EP eMeeting committee agendas.")
    ap.add_argument("--committee", action="append", dest="committees",
                    help="committee code (repeatable). Default: all 26.")
    ap.add_argument("--per-committee", type=int, default=6, help="newest agendas per committee")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    index = committee_index(args.committees)
    name_by_code = {code: name for code, name in index}
    log.info("[emeeting] streaming %d newest agendas for %d committees",
             args.per_committee, len(index))

    db = SessionLocal()
    tot_ag = tot_ag_new = tot_doc = tot_doc_new = failed = 0
    seen_oj = set()
    try:
        # Stream COMMITTEE BY COMMITTEE: fetch one committee, write+commit its
        # agendas (each in its own tiny transaction), then move on. Survives
        # timeouts (completed committees persist) and never holds a long txn.
        for code, name in index:
            rows = fetch_committee(code, name, args.per_committee, name_by_code)
            # dedupe joint-committee OJs already written this run
            rows = [r for r in rows if r["oj_reference"] not in seen_oj]
            for r in rows:
                seen_oj.add(r["oj_reference"])

            if args.dry_run:
                log.info("    [%s] %d agendas, %d docs", code, len(rows),
                         sum(r["document_count"] for r in rows))
                continue

            c_ag = c_doc = 0
            for r in rows:
                try:
                    agenda_obj, is_new = upsert(db, r)
                    db.flush()
                    for doc in documents_from_agenda(r):
                        doc["agenda_id"] = agenda_obj.id
                        if upsert_document(db, doc):
                            tot_doc_new += 1
                        tot_doc += 1
                        c_doc += 1
                    db.commit()
                    tot_ag += 1
                    c_ag += 1
                    if is_new:
                        tot_ag_new += 1
                except Exception as exc:
                    db.rollback()
                    failed += 1
                    log.warning("[emeeting] skip %s: %s", r.get("oj_reference"), str(exc)[:140])
            log.info("    [%s] %d agendas + %d documents", code, c_ag, c_doc)

        if not args.dry_run:
            log.info("[emeeting] DONE: %d agendas (%d new) + %d documents (%d new); %d skipped",
                     tot_ag, tot_ag_new, tot_doc, tot_doc_new, failed)
    finally:
        db.close()


if __name__ == "__main__":
    main()

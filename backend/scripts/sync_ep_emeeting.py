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
from services.scrapers.ep_emeeting_client import fetch_agendas

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("sync_ep_emeeting")


def upsert(db, row: dict) -> bool:
    existing = db.query(EpEmeetingAgenda).filter(
        EpEmeetingAgenda.oj_reference == row["oj_reference"]
    ).first()
    if existing is None:
        db.add(EpEmeetingAgenda(**row))
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

    log.info("[emeeting] fetching %d newest agendas for %s",
             args.per_committee, ", ".join(args.committees) if args.committees else "all 26 committees")
    rows = fetch_agendas(per_committee=args.per_committee, committees=args.committees)
    # Joint-committee OJs (CJ..) appear in several committees' archives — dedupe
    # by oj_reference (keep the one filed under the OJ's own prefix committee).
    by_ref = {}
    for r in rows:
        by_ref.setdefault(r["oj_reference"], r)
    if len(by_ref) != len(rows):
        log.info("[emeeting] deduped %d -> %d agendas (joint-committee OJs)", len(rows), len(by_ref))
    rows = list(by_ref.values())
    log.info("[emeeting] %d distinct agendas", len(rows))

    docs = sum(r["document_count"] for r in rows)
    with_proc = sum(1 for r in rows if r["procedure_refs"])
    no_body = sum(1 for r in rows if not (r["body_txt"] or "").strip())
    log.info("    total documents: %d ; agendas with >=1 procedure: %d", docs, with_proc)
    if no_body:
        log.warning("    [WARN] %d agendas have empty body_txt", no_body)
    else:
        log.info("    [OK] every agenda has body_txt")

    if args.dry_run:
        log.info("[emeeting] dry-run: nothing written")
        for r in rows[:4]:
            log.info("    [%s] %s docs=%d procs=%s", r["committee_code"], r["oj_reference"],
                     r["document_count"], ",".join(r["procedure_refs"][:3]))
        return

    db = SessionLocal()
    try:
        new = 0
        for r in rows:
            if upsert(db, r):
                new += 1
        db.commit()
        log.info("[emeeting] upserted %d agendas (%d new, %d updated)", len(rows), new, len(rows) - new)
    finally:
        db.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3.12
"""Keep `oeil_procedures` (migration 288) current: every OEIL procedure page the URL probe finds.

Why
---
/api/v2/parliament/resolution-procedures is to hold every INI, RSP and INL procedure (Victor,
9 Oct 2026), and no Brubru table could say which procedures exist. OEIL answers one URL per
procedure; services/scrapers/oeil_probe.py (Superscraper session) asks for them and reads the
page. This script is the ONLY writer of `oeil_procedures`.

Modes
-----
  (default, cron)   1. re-read the procedures that are not finished yet, stalest first, then
                       finished ones not read for 30 days (a status or a key event can change);
                    2. look for new ones: the probe's frontier + rotating window over the numbers
                       no Brubru table holds, in the current year (and the previous one until
                       March, when late pages still appear).
  --from-feed F...  load the JSON written by `scripts/oeil_probe_scan.py --mode full` (seeding).
  --refs R...       read exactly these references (repair, tests).

Rules: a 404 with OEIL's own message on a known page sets served=false (never a delete, a page
can be "being initiated"); a wall or an unexplained answer stops the run and exits non-zero; a
run that read nothing exits non-zero, because a job that stores nothing must fail.

Usage:
    python3.12 scripts/sync_oeil_procedures.py                       # dry-run
    python3.12 scripts/sync_oeil_procedures.py --apply
    python3.12 scripts/sync_oeil_procedures.py --apply --from-feed out/oeil_2025_procedures.json
    python3.12 scripts/sync_oeil_procedures.py --apply --refs "2026/2561(RSP)"
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Set

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR.parent / ".env")

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from services.scrapers.oeil_probe import (  # noqa: E402
    PROCEDURE_URL,
    OeilProber,
    ProbeBlocked,
    audit_targets,
    derive_bands,
    numbers_by_band,
    parse_ref,
)

# A finished procedure can still change (a late key event, an OJ reference), so it is re-read,
# but only after this many days.
FINISHED_RECHECK_DAYS = 30

UPSERT = text("""
INSERT INTO oeil_procedures
    (procedure_ref, procedure_year, procedure_number, procedure_type, title, type_label, instrument,
     subject, oeil_status, key_events, motion_refs, text_refs, public_url,
     served, last_served_at, unserved_since, scraped_at)
VALUES
    (:ref, :year, :number, :ptype, :title, :type_label, :instrument,
     :subject, :status, CAST(:key_events AS jsonb), :motion_refs, :text_refs, :url,
     true, :served_at, NULL, now())
ON CONFLICT (procedure_ref) DO UPDATE SET
    title          = COALESCE(EXCLUDED.title, oeil_procedures.title),
    type_label     = COALESCE(EXCLUDED.type_label, oeil_procedures.type_label),
    instrument     = EXCLUDED.instrument,
    subject        = EXCLUDED.subject,
    oeil_status    = COALESCE(EXCLUDED.oeil_status, oeil_procedures.oeil_status),
    key_events     = EXCLUDED.key_events,
    motion_refs    = EXCLUDED.motion_refs,
    text_refs      = EXCLUDED.text_refs,
    public_url     = EXCLUDED.public_url,
    served         = true,
    last_served_at = GREATEST(oeil_procedures.last_served_at, EXCLUDED.last_served_at),
    unserved_since = NULL,
    scraped_at     = now()
RETURNING (xmax = 0) AS inserted
""")

MARK_UNSERVED = text("""
UPDATE oeil_procedures
   SET served = false, unserved_since = COALESCE(unserved_since, now()), scraped_at = now()
 WHERE procedure_ref = :ref
""")


def info(msg: str) -> None:
    print(msg, flush=True)


def err(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def is_finished(status: Optional[str]) -> bool:
    """True for OEIL statuses after which Parliament does nothing more on the file."""
    s = (status or "").strip().lower()
    if s.startswith("procedure completed"):
        return "awaiting" not in s           # 'completed, awaiting publication in Official Journal'
    return s.startswith(("procedure rejected", "procedure lapsed", "procedure withdrawn"))


def row_params(ref: str, rec: dict, served_at: Optional[datetime] = None) -> dict:
    """Bind parameters for UPSERT from a probe record (parse_procedure) or a feed record."""
    p = parse_ref(ref)
    if not p:
        raise ValueError(f"not an OEIL reference: {ref!r}")
    year, number, ptype = p
    return {
        "ref": ref, "year": year, "number": number, "ptype": ptype,
        "title": rec.get("title") or None,
        "type_label": rec.get("type_label") or None,
        "instrument": rec.get("instrument") or None,
        "subject": rec.get("subject") or None,
        "status": rec.get("status") or None,
        "key_events": json.dumps(rec.get("key_events") or [], ensure_ascii=False),
        "motion_refs": list(rec.get("motion_refs") or []),
        "text_refs": list(rec.get("text_refs") or []),
        "url": PROCEDURE_URL + ref,
        "served_at": served_at or datetime.now(timezone.utc),
    }


class Writer:
    """Short-lived sessions, one per write: the run spends minutes on the network, and a Session
    held across that is a dead connection by the time it writes."""

    def __init__(self, apply: bool):
        self.apply = apply
        self.inserted = self.updated = self.unserved = 0

    def upsert(self, ref: str, rec: dict, served_at: Optional[datetime] = None) -> None:
        params = row_params(ref, rec, served_at)
        if not self.apply:
            info(f"  would write {ref}: {params['status']!r}, {len(rec.get('key_events') or [])} events")
            return
        db = SessionLocal()
        try:
            inserted = db.execute(UPSERT, params).scalar()
            db.commit()
        finally:
            db.close()
        if inserted:
            self.inserted += 1
        else:
            self.updated += 1

    def mark_unserved(self, ref: str) -> None:
        if not self.apply:
            info(f"  would mark {ref} unserved")
            return
        db = SessionLocal()
        try:
            n = db.execute(MARK_UNSERVED, {"ref": ref}).rowcount
            db.commit()
        finally:
            db.close()
        self.unserved += n


def _refs(sql: str, **params) -> List[str]:
    db = SessionLocal()
    try:
        return [r[0] for r in db.execute(text(sql), params).fetchall() if r[0]]
    finally:
        db.close()


def refresh_queue(limit: int) -> List[str]:
    """Unfinished procedures stalest first, then finished ones not read for FINISHED_RECHECK_DAYS."""
    rows = []
    db = SessionLocal()
    try:
        rows = db.execute(text(
            "SELECT procedure_ref, oeil_status, scraped_at FROM oeil_procedures ORDER BY scraped_at")).fetchall()
    finally:
        db.close()
    now = datetime.now(timezone.utc)
    open_ = [r[0] for r in rows if not is_finished(r[1])]
    stale_done = [r[0] for r in rows if is_finished(r[1])
                  and (now - r[2]).days >= FINISHED_RECHECK_DAYS]
    return (open_ + stale_done)[:limit]


def held_refs() -> Set[str]:
    """Every reference any Brubru procedure table holds: a number held anywhere is not 'new'."""
    return set(_refs("SELECT procedure_ref FROM oeil_procedures")) \
        | set(_refs("SELECT oeil_procedure_ref FROM legislative_carriages WHERE oeil_procedure_ref IS NOT NULL")) \
        | set(_refs("SELECT procedure_ref FROM ep_resolutions"))


def discovery_years(today: date) -> List[int]:
    return [today.year - 1, today.year] if today.month <= 2 else [today.year]


def load_feed(paths: Iterable[str], writer: Writer) -> int:
    n = 0
    for path in paths:
        records = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(records, list) or not records:
            raise SystemExit(f"[ERROR] {path}: not a non-empty list of feed records")
        for rec in records:
            if rec.get("state") != "served":
                raise SystemExit(f"[ERROR] {path}: record {rec.get('procedure_ref')!r} is not 'served'")
            fetched = rec.get("fetched_on")
            served_at = (datetime.fromisoformat(fetched).replace(tzinfo=timezone.utc) if fetched else None)
            writer.upsert(rec["procedure_ref"], rec, served_at)
            n += 1
        info(f"[INFO] {path}: {len(records)} record(s)")
    return n


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write; without it nothing is written")
    ap.add_argument("--from-feed", action="append", default=[], metavar="JSON",
                    help="load a feed file from oeil_probe_scan.py --mode full (repeatable)")
    ap.add_argument("--refs", action="append", default=[], metavar="REF",
                    help="read exactly this reference (repeatable)")
    ap.add_argument("--refresh-limit", type=int, default=150, help="known pages re-read per run")
    ap.add_argument("--discover-requests", type=int, default=300, help="request budget for new numbers")
    ap.add_argument("--budget", type=int, default=900, help="wall-clock seconds for the whole run")
    ap.add_argument("--pace", type=float, default=0.35, help="seconds between requests")
    args = ap.parse_args(argv)

    writer = Writer(args.apply)
    if args.from_feed:
        n = load_feed(args.from_feed, writer)
        info(f"[{'APPLIED' if args.apply else 'DRY-RUN'}] feed records={n} inserted={writer.inserted} updated={writer.updated}")
        return 0 if n else 1

    prober = OeilProber(pace=args.pace)
    deadline = time.monotonic() + args.budget
    read = served = new = 0
    try:
        queue = list(args.refs) if args.refs else refresh_queue(args.refresh_limit)
        info(f"[INFO] re-reading {len(queue)} known page(s)")
        for ref in queue:
            if time.monotonic() > deadline:
                info("[INFO] time budget reached during re-reads")
                break
            res = prober.probe(ref)
            read += 1
            if res.kind == "hit":
                served += 1
                writer.upsert(ref, res.record)
            else:
                writer.mark_unserved(ref)

        if not args.refs:
            held = held_refs()
            bands = derive_bands(held)
            for year in discovery_years(date.today()):
                known = numbers_by_band(held, year, bands)
                now = datetime.now(timezone.utc)
                day = now.date().toordinal() * 4 + now.hour // 6
                targets = audit_targets(known, bands, request_budget=args.discover_requests, day_ordinal=day)
                info(f"[INFO] {year}: probing {len(targets)} number(s) no Brubru table holds")
                for number, types in targets:
                    if time.monotonic() > deadline:
                        info("[INFO] time budget reached during discovery")
                        break
                    res = prober.sweep(year, number, types)
                    if res:
                        new += 1
                        writer.upsert(res.ref, res.record)
                        info(f"  new: {res.ref} {res.record.get('status')!r}")
    except ProbeBlocked as exc:
        err(f"[ERROR] OEIL probe stopped: {exc}")
        info(f"[PARTIAL] read={read} served={served} new={new} inserted={writer.inserted} "
             f"updated={writer.updated} unserved={writer.unserved} requests={prober.requests}")
        return 2

    info(f"[{'APPLIED' if args.apply else 'DRY-RUN'}] read={read} served={served} new={new} "
         f"inserted={writer.inserted} updated={writer.updated} unserved={writer.unserved} requests={prober.requests}")
    if prober.requests == 0 or (served + new) == 0:
        err(f"[ERROR] OEIL served no page in this run ({prober.requests} request(s)): refusing to report a clean run")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

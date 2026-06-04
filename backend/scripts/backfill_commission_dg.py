"""
Normalise + backfill `commission_dg` on eu_calendar_events (My EU Calendar, Phase C).

`commission_dg` was scraped dirty/sparse (99% null; the few set were inconsistent
— "DG ENV" vs "ENV" vs "DG MOVE"). This:
  1. normalises any existing value to a canonical DG code (normalise_dg), and
  2. for COMMISSION events still without one, INFERS the DG from the title +
     description (infer_dg, keyword heuristics).

So the Phase-B Commission "department" dropdown and the PI DG-match have real data.
NO LLM / NO Anthropic — pure string rules from the verified EC taxonomy in
knowledge_base/eu_calendar_institutions.py.

Usage:
    python3.12 -m scripts.backfill_commission_dg          # dry-run
    python3.12 -m scripts.backfill_commission_dg --apply
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from core.database import SessionLocal
from models.eu_calendar import EUCalendarEvent, InstitutionEnum
from knowledge_base.eu_calendar_institutions import normalise_dg, infer_dg


def run(apply: bool) -> None:
    db = SessionLocal()
    try:
        events = db.query(EUCalendarEvent).filter(
            EUCalendarEvent.institution == InstitutionEnum.COMMISSION
        ).all()
        stats = Counter()
        assigned = Counter()
        for e in events:
            current = e.commission_dg
            norm = normalise_dg(current)
            if norm:
                if norm != current:
                    stats["normalised"] += 1
                else:
                    stats["already_clean"] += 1
                new = norm
            else:
                inferred = infer_dg(f"{e.title or ''} {e.description or ''}")
                if inferred:
                    stats["inferred"] += 1
                    new = inferred
                else:
                    stats["unresolved"] += 1
                    new = None
            if new and new != current:
                assigned[new] += 1
                if apply:
                    e.commission_dg = new
        if apply:
            db.commit()
        print(f"[{'APPLIED' if apply else 'DRY-RUN'}] commission events: {len(events)}")
        print("  ", dict(stats))
        print("   assigned DG codes:", dict(assigned.most_common()))
    finally:
        db.close()


def main():
    p = argparse.ArgumentParser(description="Normalise + backfill commission_dg.")
    p.add_argument("--apply", action="store_true", help="Persist (default dry-run).")
    run(p.parse_args().apply)


if __name__ == "__main__":
    main()

"""Daily snapshot of the registers the API serves live: MEPs (current term) and the College.

Why (22 Sep 2026): /api/v2/parliament/meps and /api/v2/commission/commissioners are
read live (EP Open Data API, hand-curated JSON), so they had no date that says when a
record appeared or changed, and a partner syncing every morning had to re-read them
whole. This job hashes every record and keeps the dates in `api_record_snapshots`
(services/api_snapshots.py); the endpoints read them from there.

An MEP whose profile call fails is skipped for the day rather than recorded half
hydrated, and a day with any skip does not mark anyone as removed. MEPs who leave
Parliament are not removed either: they stay in the term with `in_office: false`,
which is itself a change the endpoint reports.

Usage (from backend/):
    python3.12 scripts/snapshot_live_registers.py            # dry run: counts only
    python3.12 scripts/snapshot_live_registers.py --apply
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import SessionLocal  # noqa: E402
from services import api_snapshots  # noqa: E402

_VOLATILE = {"creation_date", "updated_date"}


async def mep_records() -> tuple[dict, bool]:
    """Every current-term MEP, hydrated, with `in_office`. The EP API rate-limits
    (429, Retry-After 60), so this runs two calls at a time and waits when told."""
    from api.v1 import meps as m

    raw = await m._fetch_all(term=m.CURRENT_TERM, patient=True)
    current = await m._fetch_current_ids(patient=True)
    if not raw or not current:
        raise RuntimeError("EP Open Data returned no current-term MEPs or no sitting MEPs")
    items = await m._enrich_country_group([m._normalise(r) for r in raw], patient=True, concurrency=2)
    skipped = {i.id for i in items if i.id and m._cached(f"profile:{i.id}") is None}
    records = {}
    for i in items:
        if i.id and i.id not in skipped:
            i.in_office = i.id in current
            records[i.id] = i.model_dump(mode="json", exclude=_VOLATILE)
    print(f"[INFO] MEPs: {len(raw)} in the term, {len(current)} sitting, {len(records)} recorded, {len(skipped)} skipped")
    return records, not skipped


def commissioner_records() -> dict:
    from services.api_clients.commissioner_agenda_client import load_commissioner_profiles

    profiles = load_commissioner_profiles()
    if not profiles:
        raise RuntimeError("commissioners.json returned no profiles")
    return {p.slug: {"slug": p.slug, "name": p.name, "portfolio": p.portfolio,
                     "country": p.country, "bio_url": p.bio_url} for p in profiles}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    started = datetime.now(timezone.utc)
    error, written = None, 0
    db = SessionLocal()
    try:
        from api.v1 import meps as m
        from api.v1.metadata import COMMISSIONERS_DATASET

        meps, meps_complete = asyncio.run(mep_records())
        college = commissioner_records()
        for dataset, records, complete in ((m.SNAPSHOT_DATASET, meps, meps_complete),
                                           (COMMISSIONERS_DATASET, college, True)):
            counts = api_snapshots.record(db, dataset, records, complete=complete)
            written += len(records)
            print(f"[OK] {dataset}: {counts}")
        if args.apply:
            db.commit()
        else:
            db.rollback()
            print("[DRY-RUN] rolled back")
    except Exception as e:  # recorded, then a failing exit
        db.rollback()
        error = f"{type(e).__name__}: {e}"
        print(f"[ERROR] {error}")
    finally:
        if args.apply:
            try:
                from services.sync.freshness import record_run
                record_run(db, source_key="live_register_snapshots", tier="daily",
                           status="failed" if error else "success", items_added=written,
                           error=error, started_at=started, finished_at=datetime.now(timezone.utc))
            except Exception as e:  # noqa: BLE001
                print(f"[WARN] could not record the run: {type(e).__name__}: {e}")
        db.close()
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())

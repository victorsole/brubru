"""Change dates for API records that are not stored as rows (22 Sep 2026, migration 234).

MEPs come live from the EP Open Data API and commissioners from a hand-curated JSON
file, so neither has a row whose `created`/`updated` times the database can keep. A
daily job (scripts/snapshot_live_registers.py) hands every record to `record()`, which
keeps one row per record in `api_record_snapshots` with a hash of its content:

* a record never seen before gets `first_seen_at = content_updated_at = now()`;
* a record whose content hash changed gets `content_updated_at = now()`;
* a record seen with the same content only gets `last_seen_at` moved;
* on a COMPLETE fetch, a listed record that is missing gets `removed_at` (and an
  update), unless that would remove more than `max_removed_share` of the dataset,
  which says the fetch was partial, not that people left.

A live fetch can also be partial per record: an MEP whose profile call failed comes
back without country or group. `keep_known` fields that are null in the new payload
but known in the stored one are carried over, so a flaky upstream never reads as a change.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import text


def content_hash(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def record(db, dataset: str, records: Dict[str, Dict[str, Any]], *, complete: bool,
           keep_known: Iterable[str] = (), max_removed_share: float = 0.10) -> Dict[str, int]:
    """Upsert one dataset's records. `db` is a SQLAlchemy Session; the caller commits."""
    keep_known = tuple(keep_known)
    existing = {r.record_key: r for r in db.execute(text(
        "SELECT record_key, payload, content_hash, removed_at FROM api_record_snapshots WHERE dataset = :d"),
        {"d": dataset})}
    counts = {"new": 0, "changed": 0, "unchanged": 0, "returned": 0, "removed": 0}
    rows = []
    for key, payload in records.items():
        old = existing.get(key)
        if old is not None and keep_known:
            payload = dict(payload)
            for f in keep_known:
                if payload.get(f) in (None, "") and (old.payload or {}).get(f) not in (None, ""):
                    payload[f] = old.payload[f]
        h = content_hash(payload)
        if old is None:
            counts["new"] += 1
        elif old.removed_at is not None:
            counts["returned" if old.content_hash == h else "changed"] += 1
        else:
            counts["changed" if old.content_hash != h else "unchanged"] += 1
        rows.append({"k": key, "p": payload, "h": h})
    # One statement for the whole dataset: the date moves only on a new hash or a return.
    if rows:
        db.execute(text("""
            INSERT INTO api_record_snapshots (dataset, record_key, payload, content_hash)
            SELECT :d, r.k, r.p, r.h FROM jsonb_to_recordset(CAST(:rows AS jsonb)) AS r(k text, p jsonb, h text)
            ON CONFLICT (dataset, record_key) DO UPDATE SET
                payload = EXCLUDED.payload,
                content_updated_at = CASE
                    WHEN api_record_snapshots.content_hash <> EXCLUDED.content_hash
                      OR api_record_snapshots.removed_at IS NOT NULL THEN now()
                    ELSE api_record_snapshots.content_updated_at END,
                content_hash = EXCLUDED.content_hash,
                last_seen_at = now(),
                removed_at = NULL
        """), {"d": dataset, "rows": json.dumps(rows, default=str)})
    if complete:
        listed = [k for k, r in existing.items() if r.removed_at is None]
        gone = [k for k in listed if k not in records]
        if listed and len(gone) > max_removed_share * len(listed):
            raise RuntimeError(f"{dataset}: {len(gone)} of {len(listed)} records missing from a fetch "
                               f"called complete (> {max_removed_share:.0%}); refusing to mark them removed")
        if gone:
            db.execute(text(
                "UPDATE api_record_snapshots SET removed_at = now(), content_updated_at = now() "
                "WHERE dataset = :d AND record_key = ANY(:keys) AND removed_at IS NULL"),
                {"d": dataset, "keys": gone})
        counts["removed"] = len(gone)
    return counts


Dates = Tuple[Optional[datetime], Optional[datetime], Optional[datetime]]  # first seen, updated, removed


def dates_for(db, dataset: str, keys: Optional[Iterable[str]] = None) -> Dict[str, Dates]:
    """{record_key: (first_seen_at, content_updated_at, removed_at)} for the dataset (or some keys)."""
    sql = ("SELECT record_key, first_seen_at, content_updated_at, removed_at "
           "FROM api_record_snapshots WHERE dataset = :d")
    params: Dict[str, Any] = {"d": dataset}
    if keys is not None:
        keys = list(keys)
        if not keys:
            return {}
        sql += " AND record_key = ANY(:keys)"
        params["keys"] = keys
    return {r.record_key: (r.first_seen_at, r.content_updated_at, r.removed_at)
            for r in db.execute(text(sql), params)}


def payloads_for(db, dataset: str) -> Dict[str, Dict[str, Any]]:
    """{record_key: payload} for every record of the dataset."""
    return {r.record_key: r.payload for r in db.execute(text(
        "SELECT record_key, payload FROM api_record_snapshots WHERE dataset = :d"), {"d": dataset})}


def removed_payloads(db, dataset: str) -> List[Tuple[str, Dict[str, Any], Dates]]:
    """Records no longer listed, with their last payload: tombstones for an incremental sync."""
    return [(r.record_key, r.payload, (r.first_seen_at, r.content_updated_at, r.removed_at))
            for r in db.execute(text(
                "SELECT record_key, payload, first_seen_at, content_updated_at, removed_at "
                "FROM api_record_snapshots WHERE dataset = :d AND removed_at IS NOT NULL"), {"d": dataset})]


def in_window(dates: Optional[Dates], w: Dict[str, Optional[datetime]]) -> bool:
    """True when the record's dates satisfy the created_/updated_ window (unknown dates never do)."""
    if not any(v is not None for v in w.values()):
        return True
    if dates is None:
        return False
    created, updated, _ = dates
    return ((w["created_from"] is None or created >= w["created_from"])
            and (w["created_to"] is None or created <= w["created_to"])
            and (w["updated_from"] is None or updated >= w["updated_from"])
            and (w["updated_to"] is None or updated <= w["updated_to"]))


def sort_key(order: str, dates: Optional[Dates], record_key: str):
    """Sort key for a sync order; records with unknown dates sort last."""
    if dates is None:
        return (1, datetime.max, record_key)
    value = dates[1] if order.startswith("updated") else dates[0]
    return (0, value, record_key)

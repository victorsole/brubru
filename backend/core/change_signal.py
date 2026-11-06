"""Writes that add facts a row always had, not a change of the record.

`brubru_touch_if_changed` moves a row's change signal (`updated_at`, served as `updated_date`) and logs the row in
`brubru_change_log` whenever a non-ignored column differs. A cache computed from a law's own text and stored in
`eu_laws.extra_metadata` on a READ (defined terms, the recital map, structure counts) is not a change of the law, yet
it moved `updated_date`, so `updated_from` handed the law out again as changed (register O230, 5 Nov 2026: reading
REACH's and MiCA's definitions moved both).

The trigger keeps the signal when `brubru.keep_change_signal` equals the current transaction id (migration 302/303).
Call this in the same transaction, before the UPDATE, and commit right after it: the setting is transaction-local, so
it cannot silence a later transaction on a pooled connection.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session


def keep_change_signal(db: Session) -> None:
    db.execute(text("SELECT set_config('brubru.keep_change_signal', txid_current()::text, true)"))

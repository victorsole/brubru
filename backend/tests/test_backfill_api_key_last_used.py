"""Tests for `scripts/backfill_api_key_last_used.py`.

The column under-reported because only the REST auth path wrote it; the MCP path
never did. One client's key read `last_used_at = NULL` against 178 recorded
calls. The write path was fixed on 25 Aug 2026; this script repairs history.

Every scenario runs inside a transaction that is rolled back, so the tests
exercise the REAL SQL against the REAL schema without leaving rows behind.
"""
import uuid

import pytest
from sqlalchemy import text

from scripts.backfill_api_key_last_used import _APPLY, _PENDING


@pytest.fixture
def conn():
    """A connection in an explicit transaction, always rolled back."""
    from core.database import engine
    c = engine.connect()
    tx = c.begin()
    yield c
    tx.rollback()
    c.close()


def _a_user(conn):
    row = conn.execute(text("SELECT id FROM users LIMIT 1")).fetchone()
    if not row:
        pytest.skip("no users in the database to attach a test key to")
    return row[0]


def _make_key(conn, name, last_used_at=None):
    kid = uuid.uuid4()
    conn.execute(
        text("""INSERT INTO api_keys (id, user_id, key_hash, key_prefix, name, last_used_at)
                VALUES (:id, :uid, :h, :p, :n, :lu)"""),
        {"id": kid, "uid": _a_user(conn), "h": f"hash-{kid}",
         "p": "brubru_live_test", "n": name, "lu": last_used_at},
    )
    return kid


def _add_calls(conn, kid, when, n=1, is_probe=False):
    for _ in range(n):
        conn.execute(
            text("""INSERT INTO api_usage_events
                    (user_id, api_key_id, endpoint, method, cost_eur_micro,
                     status_code, created_at, is_probe)
                    VALUES (NULL, :k, '/test', 'GET', 0, 200, :t, :p)"""),
            {"k": kid, "t": when, "p": is_probe},
        )


def _last_used(conn, kid):
    return conn.execute(
        text("SELECT last_used_at FROM api_keys WHERE id = :i"), {"i": kid}
    ).scalar()


def _pending_ids(conn):
    return {r["id"] for r in conn.execute(text(_PENDING)).mappings().all()}


# ---------------------------------------------------------------------------

def test_a_null_column_with_usage_is_repaired(conn):
    """The headline case: 178 calls, column reads NULL."""
    kid = _make_key(conn, "null-with-usage")
    _add_calls(conn, kid, "2026-08-11 21:29:47+00", n=3)
    assert kid in _pending_ids(conn), "a NULL column with usage must be seen as pending"

    conn.execute(text(_APPLY))
    assert str(_last_used(conn, kid)).startswith("2026-08-11 21:29:47")
    assert kid not in _pending_ids(conn)


def test_null_is_caught_because_the_filter_is_not_a_bare_comparison(conn):
    """`NULL < x` is NULL, so a filter written only as `last_used_at < max` would
    silently exclude exactly the rows this script exists to repair.

    This is the NULL-propagation trap from
    feedback_null_propagation_and_silent_fallback_hide_failures.
    """
    kid = _make_key(conn, "null-trap", last_used_at=None)
    _add_calls(conn, kid, "2026-08-01 00:00:00+00")
    assert "IS NULL" in _PENDING, "the pending query must test NULL explicitly"
    assert kid in _pending_ids(conn)


def test_a_newer_live_timestamp_is_never_moved_backwards(conn):
    """A key used since the write-path fix may be NEWER than the ledger window.

    Overwriting it with the ledger max would replace one wrong value with
    another, so the update uses GREATEST and must leave this row alone.
    """
    newer = "2026-08-25 12:00:00+00"
    kid = _make_key(conn, "already-fresher", last_used_at=newer)
    _add_calls(conn, kid, "2026-06-01 00:00:00+00")

    assert kid not in _pending_ids(conn), "a fresher column is not stale"
    conn.execute(text(_APPLY))
    assert str(_last_used(conn, kid)).startswith("2026-08-25 12:00:00"), \
        "the backfill moved a live timestamp backwards"


def test_an_older_timestamp_is_advanced_to_the_ledger(conn):
    kid = _make_key(conn, "stale-value", last_used_at="2026-01-01 00:00:00+00")
    _add_calls(conn, kid, "2026-07-15 08:00:00+00")
    conn.execute(text(_APPLY))
    assert str(_last_used(conn, kid)).startswith("2026-07-15 08:00:00")


def test_probe_calls_still_count_as_usage(conn):
    """`is_probe` means the call was OURS, not that it never happened.

    Excluding probes would leave a key with real traffic reading "never used" --
    reintroducing the defect in a new place.
    """
    kid = _make_key(conn, "probe-only")
    _add_calls(conn, kid, "2026-08-20 10:00:00+00", n=5, is_probe=True)
    conn.execute(text(_APPLY))
    assert _last_used(conn, kid) is not None, "a probed key must not read as unused"


def test_a_key_with_no_usage_is_left_alone(conn):
    """Genuinely unused keys must stay NULL -- inventing a timestamp would make
    a real 'never used' key look live and defeat any key-cleanup built on it."""
    kid = _make_key(conn, "genuinely-unused")
    conn.execute(text(_APPLY))
    assert _last_used(conn, kid) is None


def test_running_twice_changes_nothing(conn):
    """Idempotent, so it is safe in cron or after a restore."""
    kid = _make_key(conn, "idempotent")
    _add_calls(conn, kid, "2026-05-05 05:05:05+00")
    conn.execute(text(_APPLY))
    first = _last_used(conn, kid)
    conn.execute(text(_APPLY))
    assert _last_used(conn, kid) == first
    assert kid not in _pending_ids(conn)


def test_production_has_no_key_with_usage_and_a_null_column():
    """The live invariant the backfill was run to establish (20 -> 0)."""
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        stale = db.execute(text("""
            SELECT count(*) FROM api_keys k
            WHERE k.last_used_at IS NULL
              AND EXISTS (SELECT 1 FROM api_usage_events e WHERE e.api_key_id = k.id)
        """)).scalar()
    finally:
        db.close()
    assert stale == 0, f"{stale} key(s) have usage but still read as never used"

"""U2 (10 Sep 2026): /users must report tracking split by who wrote it.

A single `n` per surface is not reportable. On 10 September 2026, 81% of
non-internal tracked items turned out to be our own writes, and reporting them as
one number had already been read as engagement in at least two /users runs.

Also guards the defect the U2 audit found: two surfaces in the table list named a
timestamp column that does not exist, so their queries errored and both printed
"-" -- which reads as "nobody used it". 359 feed subscriptions were invisible in
every run before this. An empty output is never absence.
"""
import os
import pathlib
import sys

import pytest

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _REPO_ROOT + "/backend" not in sys.path:
    sys.path.insert(0, _REPO_ROOT + "/backend")

from scripts.user_activity_report import (  # noqa: E402
    MEUB_TRACK_TABLES,
    SOURCED_TRACK_TABLES,
    section_meub_tracking,
    section_tracking_provenance,
)


def _conn():
    """A live connection, or a loud skip. Never a silent pass."""
    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT + "/backend/.env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set in this environment")
    from sqlalchemy import create_engine
    return create_engine(url).connect()


def test_sourced_tables_are_exactly_the_six_track_tables():
    """The four non-track surfaces have no provenance column and must not be
    silently treated as if they had one."""
    listed = {t for _, t, _ in MEUB_TRACK_TABLES}
    assert SOURCED_TRACK_TABLES <= listed
    assert len(SOURCED_TRACK_TABLES) == 6
    assert "user_feed_subscriptions" not in SOURCED_TRACK_TABLES


def test_every_surface_names_a_timestamp_column_that_exists():
    """The defect that hid 359 feed subscriptions.

    Derived from information_schema, never from a hand-typed list: an allowlist
    written from memory is not a check.
    """
    from sqlalchemy import text
    conn = _conn()
    try:
        wrong = []
        for label, table, ts in MEUB_TRACK_TABLES:
            cols = {
                r[0] for r in conn.execute(
                    text("SELECT column_name FROM information_schema.columns "
                         "WHERE table_schema='public' AND table_name=:t"),
                    {"t": table},
                )
            }
            if not cols:
                wrong.append(f"{label}: table {table} does not exist")
            elif ts not in cols:
                wrong.append(f"{label}: {table}.{ts} does not exist (has: {sorted(cols)[:6]}...)")
        assert not wrong, (
            "these surfaces name a non-existent timestamp column, so their query "
            "errors and the surface prints '-', which reads as no usage: " + "; ".join(wrong)
        )
    finally:
        conn.close()


@pytest.fixture
def seeded(request):
    """A connection inside a transaction that is ALWAYS rolled back, carrying one
    row of each provenance state.

    Without fixture rows these tests are vacuous: every existing row is NULL, so
    "fold unknown into chosen" and "estimate the whole table" are both invisible.
    Both mutations passed against the first draft of this file. A check whose
    denominator is zero has not passed, it has not run --
    feedback_zero_denominator_is_not_a_pass.
    """
    from sqlalchemy import text
    import uuid as _uuid

    conn = _conn()
    trans = conn.begin()

    def _fin():
        trans.rollback()
        conn.close()
    request.addfinalizer(_fin)

    uid = conn.execute(text(
        "SELECT id FROM users WHERE email = 'peter@downside-up.net'")).scalar()
    if uid is None:
        pytest.skip("fixture account peter@downside-up.net absent from this database")
    cids = [r[0] for r in conn.execute(text(
        "SELECT id FROM legislative_carriages WHERE id NOT IN "
        "(SELECT carriage_id FROM user_carriage_tracks WHERE user_id = :u) LIMIT 4"),
        {"u": uid})]
    if len(cids) < 4:
        pytest.skip("not enough spare carriages to build the fixture")

    # One 'user', two 'provisioned', one NULL -- all three states, all inside the
    # window, and asymmetric counts so no merge of two buckets can pass by
    # coincidence. The NULL row is what makes the "fold unknown into chosen"
    # mutation visible: without an unknown row IN THE WINDOW the fold is a no-op
    # and the test is vacuous. It was, in the first draft.
    for cid, src in zip(cids, ("user", "provisioned", "provisioned", None)):
        conn.execute(text(
            "INSERT INTO user_carriage_tracks (id, user_id, carriage_id, tracked_since, source) "
            "VALUES (:i, :u, :c, '2026-09-09 12:00:00', :s)"),
            {"i": str(_uuid.uuid4()), "u": uid, "c": cid, "s": src})
    return conn


def test_section_9_keeps_the_three_states_apart(seeded):
    """`unknown` must never be folded into `chosen`. That fold IS the defect."""
    rows = section_meub_tracking(seeded, "2026-09-09", "2026-09-11", include_internal=False)
    files = {r["surface"]: r for r in rows}["My Tracked Files"]
    assert files["chosen"] == 1, f"expected exactly the 1 seeded user row, got {files['chosen']}"
    assert files["provisnd"] == 2, f"expected the 2 seeded provisioned rows, got {files['provisnd']}"
    assert files["unknown"] == 1, (
        f"expected the 1 seeded NULL-source row, got {files['unknown']} -- if this "
        "is 0 and `chosen` is 2, unknown is being folded into chosen"
    )
    assert files["n"] == 4


def test_section_9_marks_unsourced_surfaces_as_n_a(seeded):
    """A surface with no provenance column says so; it never prints a blank that
    could be read as 'all user-chosen'."""
    rows = section_meub_tracking(seeded, "2026-09-09", "2026-09-11", include_internal=False)
    by_surface = {r["surface"]: r for r in rows}
    for label, table, _ in MEUB_TRACK_TABLES:
        row = by_surface[label]
        for col in ("chosen", "provisnd", "unknown"):
            assert col in row, f"{label} missing the {col} column"
            if table in SOURCED_TRACK_TABLES:
                assert row[col] != "n/a", f"{label}.{col} should be a real count"
            else:
                assert row[col] == "n/a", f"{label}.{col} must read n/a, not a number"


def test_provenance_totals_report_all_three_states(seeded):
    out = section_tracking_provenance(seeded, include_internal=False)
    totals = {r["provenance"]: r["items"] for r in out["totals"]}
    assert totals.get("user") == 1, totals
    assert totals.get("provisioned") == 2, totals
    assert totals.get("unknown (pre-230)", 0) > 0, (
        "historic rows must still be reported as unknown, never merged away"
    )


def test_write_shape_estimate_covers_the_unknown_bucket_ONLY(seeded):
    """The estimate is a guess. Guessing about rows whose source is RECORDED
    would be noise at best and a contradiction at worst."""
    out = section_tracking_provenance(seeded, include_internal=False)
    totals = {r["provenance"]: r["items"] for r in out["totals"]}
    est = out["shape_estimate"][0]
    unknown = totals.get("unknown (pre-230)", 0)
    assert est["bulk_items"] + est["accrued_items"] == unknown, (
        f"estimate partitions {est['bulk_items'] + est['accrued_items']} items but the "
        f"unknown bucket holds {unknown} -- it is reaching rows whose source is known"
    )
    assert est["bulk_items"] + est["accrued_items"] != sum(totals.values()), (
        "the estimate spans every row, including the 3 seeded ones whose provenance "
        "is recorded; it must be scoped to source IS NULL"
    )

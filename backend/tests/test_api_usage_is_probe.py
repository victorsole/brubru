"""Tests for `api_usage_events.is_probe` (migration 222).

The column exists so Brubru's own verification traffic stops being counted as a
client's usage -- the 13 Aug 2026 incident where 178 `mcp:ask_dpp` debugging
calls landed on a client's row and inflated her WAPU.

Two properties matter more than the plumbing and are tested explicitly:

  1. An unrecognised header reads as NOT a probe. The failure direction has to be
     "over-report our own traffic as real", never "silently erase traffic from
     every metric".
  2. Marking a call as a probe changes ANALYTICS ONLY. It must not skip the
     debit, or the header becomes a way to call the paid API for free.
"""
import uuid

import pytest

from services.billing.api_meter import is_probe_header


# ---------------------------------------------------------------------------
# 1. Header parsing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", ["1", "true", "TRUE", "True", "yes", "YES", " 1 ", "true "])
def test_recognised_truthy_values_mark_a_probe(value):
    assert is_probe_header(value) is True


@pytest.mark.parametrize(
    "value",
    [None, "", "   ", "0", "false", "no", "off", "probe", "2", "null", "<script>"],
)
def test_everything_else_is_real_traffic(value):
    """Absent, empty, falsey or garbage -- all must read as real traffic.

    A header nobody sent must never be able to hide a call from the metrics.
    """
    assert is_probe_header(value) is False


def test_parser_matches_the_chat_surface():
    """The same header must behave identically on Chat and on the API.

    api/chat.py has used `{"1","true","yes"}` since 19 Aug 2026. If that set ever
    diverges, one probe script marks Chat but not the API and the two audit
    lenses disagree about the same run.
    """
    chat_truthy = {"1", "true", "yes"}
    for v in chat_truthy:
        assert is_probe_header(v) is True
    assert is_probe_header("2") is False  # not in the chat set either


# ---------------------------------------------------------------------------
# 2. Ledger round-trip + the billing invariant
# ---------------------------------------------------------------------------

def _usage_row(db, evt_id):
    from sqlalchemy import text
    return db.execute(
        text("SELECT is_probe, cost_eur_micro FROM api_usage_events WHERE id = :i"),
        {"i": evt_id},
    ).fetchone()


@pytest.fixture
def db():
    from core.database import SessionLocal
    s = SessionLocal()
    yield s
    s.close()


def test_probe_and_real_rows_round_trip_and_probe_is_not_free(db):
    """A probe row stores is_probe=TRUE, a normal row FALSE, and BOTH are billed
    the same amount. Written as one test because the invariant is the comparison.
    """
    from sqlalchemy import text
    from services.billing.api_meter import record_usage

    cost = 5000
    made = []
    try:
        probe = record_usage(
            db, user_id=None, api_key_id=None, endpoint="/test/probe",
            method="GET", cost_micro=cost, request_id=None, status_code=200,
            is_probe=True,
        )
        made.append(probe.id)
        real = record_usage(
            db, user_id=None, api_key_id=None, endpoint="/test/real",
            method="GET", cost_micro=cost, request_id=None, status_code=200,
        )
        made.append(real.id)

        p_row, r_row = _usage_row(db, probe.id), _usage_row(db, real.id)
        assert p_row.is_probe is True
        assert r_row.is_probe is False, "default must be False, not NULL or True"
        # The point of the whole test: probes are excluded from METRICS, not from
        # BILLING. Equal cost is what stops the header being a free-call switch.
        assert p_row.cost_eur_micro == r_row.cost_eur_micro == cost
    finally:
        if made:
            db.execute(
                text("DELETE FROM api_usage_events WHERE id = ANY(:ids)"), {"ids": made}
            )
            db.commit()


def test_column_default_is_false_for_rows_written_without_the_kwarg(db):
    """Pre-existing rows and any writer that never passes is_probe stay countable.

    A NULL here would break `AND NOT is_probe` in the WAPU query (NULL propagates
    and silently drops the row) -- the exact NULL-propagation trap recorded in
    feedback_null_propagation_and_silent_fallback_hide_failures.
    """
    from sqlalchemy import text
    nulls = db.execute(
        text("SELECT count(*) FROM api_usage_events WHERE is_probe IS NULL")
    ).scalar()
    assert nulls == 0, f"{nulls} NULL is_probe rows would vanish from `AND NOT is_probe`"


# ---------------------------------------------------------------------------
# 3. The consumer -- or the column ships dead
# ---------------------------------------------------------------------------

def test_wapu_query_excludes_probes():
    """`/users` WAPU must not count a probe as a core action.

    Without this the column is inert: the write path is correct and every report
    still reads the same inflated number.
    """
    from pathlib import Path
    src = Path(__file__).resolve().parents[1] / "scripts" / "user_activity_report.py"
    text_ = src.read_text()
    idx = text_.find("SELECT user_id, 'api' FROM api_usage_events")
    assert idx != -1, "WAPU api branch not found -- did the query move?"
    window = text_[idx: idx + 320]
    # Strip SQL line-comments first: `-- our own verification traffic is not a
    # user action` sits on the same line as the filter, and a version of this
    # test that grepped the raw window could be satisfied by the comment alone.
    sql_only = "\n".join(line.split("--")[0] for line in window.splitlines())
    assert "NOT is_probe" in sql_only, "WAPU still counts probe calls (filter not in the SQL)"


@pytest.mark.parametrize("rel", ["api/v1/_deps.py", "api/mcp_http.py"])
def test_both_write_paths_pass_is_probe_to_record_usage(rel):
    """REST and MCP must BOTH pass is_probe into `record_usage` itself.

    The 13 Aug incident was on the MCP path -- the same path that was missed when
    `api_keys.last_used_at` was wired -- so pin both rather than assume symmetry
    between them.

    Checked by walking the AST to the `record_usage(...)` call rather than by
    grepping the file. The first version of this test grepped for `is_probe=`
    anywhere in the source, and passed against a deliberately broken mcp_http.py
    because an unrelated `is_probe=is_probe_header(...)` argument elsewhere in the
    file satisfied it. A test that cannot fail is not a test.
    """
    import ast
    from pathlib import Path

    tree = ast.parse((Path(__file__).resolve().parents[1] / rel).read_text())
    calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "record_usage"
    ]
    assert calls, f"{rel} has no record_usage() call -- did the write path move?"
    for call in calls:
        kwargs = {k.arg for k in call.keywords}
        assert "is_probe" in kwargs, (
            f"{rel}: record_usage() at line {call.lineno} does not pass is_probe, "
            "so every call on this path records as real user traffic"
        )

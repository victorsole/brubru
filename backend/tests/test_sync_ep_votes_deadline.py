"""Tests for the `votes_ep` wall-clock deadline (25 Aug 2026).

`votes_ep` failed 49 consecutive runs on `timeout_1200s`, and was still failing
3/3 after a `--max-sittings 6` cap was added on 24 August. The cap could not
work: it bounds the RCV page fetches only, while a SECOND loop fetches one
committee report per target inside those sittings and was uncapped. Six sittings
held 80 targets, so the real worst case was ~98 browser fetches, not 18.

Being killed by the cron timeout loses the whole run. These tests pin the two
properties that make a bounded run useful instead:

  1. The deadline is checked in BOTH loops -- the sitting loop and the
     committee-report loop. Guarding only the first would reproduce the exact
     failure the `--max-sittings` cap already had.
  2. Nothing is dropped silently. A skipped sitting or report must be reported,
     per the standing rule that produced the `all_items[:20]` incident.
"""
import ast
import inspect
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "scripts" / "sync_ep_votes.py"


def code_only(text_: str) -> str:
    """The source with COMMENTS removed.

    Grepping raw source for a token lets a COMMENT satisfy the assertion. That is
    not hypothetical here: the first version of
    `test_a_skipped_report_is_not_counted_as_a_missing_one` passed against broken
    code because the word it searched for appeared in the comment explaining why
    the code should be there. Any text assertion about BEHAVIOUR runs through this.
    """
    import io, tokenize
    out, last = [], (1, 0)
    for tok in tokenize.generate_tokens(io.StringIO(text_).readline):
        if tok.type == tokenize.COMMENT:
            continue
        if tok.start[0] > last[0]:
            out.append("\n" * (tok.start[0] - last[0]))
        out.append(tok.string)
        last = tok.end
    return "".join(out)


@pytest.fixture(scope="module")
def source():
    return SRC.read_text()


@pytest.fixture(scope="module")
def run_fn():
    import sys
    sys.path.insert(0, str(SRC.parents[1]))
    from scripts.sync_ep_votes import run
    return run


# ---------------------------------------------------------------------------
# The flag exists and reaches the function (CLI wrapper parity)
# ---------------------------------------------------------------------------

def test_run_accepts_a_deadline(run_fn):
    assert "deadline_seconds" in inspect.signature(run_fn).parameters


def test_deadline_defaults_to_none(run_fn):
    """No deadline unless asked for -- an interactive run must not self-truncate."""
    assert inspect.signature(run_fn).parameters["deadline_seconds"].default is None


def test_cli_exposes_and_forwards_the_flag(source):
    """A flag the CLI accepts but never passes on ships the feature dead.

    This is `feedback_cli_wrapper_parity`: a parameter added to a function while
    its CLI wrapper is left alone silently does nothing.
    """
    assert "--deadline-seconds" in source, "flag not exposed"
    assert "deadline_seconds=args.deadline_seconds" in source, "flag never forwarded to run()"


def test_cron_registry_passes_a_deadline_below_the_timeout():
    """The budget must leave headroom, or the deadline never fires first."""
    import re
    reg = (SRC.parents[1] / "services" / "sync" / "source_registry.py").read_text()
    line = next(l for l in reg.splitlines() if '"votes_ep"' in l)
    assert "--deadline-seconds" in line, "cron still runs votes_ep unbounded"
    m_budget = re.search(r'"--deadline-seconds",\s*"(\d+)"', line)
    m_timeout = re.search(r"timeout=(\d+)", line)
    assert m_budget and m_timeout, f"could not parse votes_ep spec: {line.strip()}"
    budget, timeout = int(m_budget.group(1)), int(m_timeout.group(1))
    assert budget < timeout, f"deadline {budget}s >= cron timeout {timeout}s: the kill still wins"
    assert timeout - budget >= 120, (
        f"only {timeout - budget}s of headroom; a slow final fetch would still be killed"
    )


# ---------------------------------------------------------------------------
# The deadline guards BOTH loops -- the actual defect
# ---------------------------------------------------------------------------

def _out_of_time_call_count(source):
    """Count `out_of_time()` calls inside run(), via the AST rather than a grep."""
    tree = ast.parse(source)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "run")
    return sum(
        1 for n in ast.walk(fn)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == "out_of_time"
    )


def test_deadline_is_checked_in_both_loops(source):
    """Two checks minimum: the sitting loop AND the committee-report loop.

    One check is not enough and is precisely why `--max-sittings 6` failed --
    it bounded the outer loop while the inner one ran free.
    """
    n = _out_of_time_call_count(source)
    assert n >= 2, (
        f"out_of_time() called {n} time(s); the committee-report loop is the "
        "uncapped one that caused the timeouts and must be guarded too"
    )


def test_committee_loop_guard_sits_before_the_fetch(source):
    """The guard must precede `committee_report_url(...)`, not follow it.

    Checking after the fetch would still pay for the fetch that blows the budget.
    """
    idx_guard = source.find("elif out_of_time():")
    idx_fetch = source.find("curl = committee_report_url(rep)")
    assert idx_guard != -1, "no guard in the committee branch"
    assert idx_guard < idx_fetch, "guard runs after the fetch it is meant to prevent"


# ---------------------------------------------------------------------------
# No silent caps
# ---------------------------------------------------------------------------

def test_skips_are_reported_not_swallowed(source):
    """A truncated run must say so, with counts, or it reads as a complete one."""
    code = code_only(source)
    assert "skipped_sittings" in code and "skipped_reports" in code
    assert "[WARN] deadline" in code, "no warning line when work is dropped"
    for token in ("sitting(s) not fetched", "committee report(s) skipped"):
        assert token in code, f"summary does not report {token!r}"


def test_a_complete_run_says_so_explicitly(source):
    """The other half: 'nothing skipped' must be stated, not inferred from silence."""
    assert "nothing skipped" in code_only(source)


def test_partial_progress_is_committed(source):
    """A deadline that discards the work it did is no better than the SIGKILL.

    The commit must live outside the sitting loop so it still runs after a break.
    """
    tail = source[source.find("if apply:\n            db.commit()   # persist"):]
    assert tail.startswith("if apply:"), "no post-loop commit of partial progress"


# ---------------------------------------------------------------------------
# The measured settle time
# ---------------------------------------------------------------------------

def test_settle_time_is_the_measured_value(source):
    """9000ms was costing ~6s per fetch for byte-identical HTML (measured on two
    RCV dates and a committee report). Pinned so it is not restored by reflex."""
    code = code_only(source)
    assert "settle_ms=3000" in code, "the measured settle value is not in the CODE"
    assert "settle_ms=9000" not in code, "the 9000ms settle was restored"


def test_a_skipped_report_is_not_counted_as_a_missing_one(source):
    """A deadline-skip must NOT fall through into the `no_committee` counter.

    Caught in the second audit pass. The first version set `cpv = None` and fell
    through to `if cpv: ... else: counts["no_committee"] += 1`, so a committee
    report we never LOOKED at was recorded as a report that does not EXIST. Two
    different facts, only one of them about the upstream site -- and the summary
    would have understated the skips while overstating a data gap.

    The guard branch must `continue`.

    Asserted over the AST, not the text. The first version of this test searched
    the branch source for the word "continue" -- and passed against a deliberately
    broken fall-through, because the word appears in the explanatory COMMENT above
    the statement. A test that matches its own documentation cannot fail.
    """
    tree = ast.parse(source)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "run")

    guards = [
        n for n in ast.walk(fn)
        if isinstance(n, ast.If)
        and isinstance(n.test, ast.Call)
        and isinstance(n.test.func, ast.Name)
        and n.test.func.id == "out_of_time"
    ]
    assert guards, "no out_of_time() guard found in run()"

    # The committee guard is the one whose body records a skipped REPORT.
    committee_guard = [
        g for g in guards
        if any(
            isinstance(c, ast.Attribute) and c.attr == "add"
            and isinstance(c.value, ast.Name) and c.value.id == "skipped_reports"
            for c in ast.walk(g)
        )
    ]
    assert committee_guard, "no guard records a skipped committee report"
    assert any(isinstance(n, ast.Continue) for n in ast.walk(committee_guard[0])), (
        "the deadline branch falls through to the no_committee counter, "
        "reporting an unfetched report as a missing one"
    )


def test_skipped_reports_are_counted_distinctly(source):
    """The same report_ref recurs across targets in a sitting; counting fetch
    attempts instead of distinct reports would inflate the number in the summary."""
    assert "skipped_reports: set = set()" in source, "skipped_reports is not a set"
    assert "len(skipped_reports)" in source, "the summary prints the container, not its size"

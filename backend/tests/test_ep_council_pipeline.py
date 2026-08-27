"""The EP + Council corpora must maintain themselves, and say when they cannot.

Everything fixed on 27 August 2026 was done by hand, and `sync_texts_adopted` had
**never been scheduled at all** -- which is why `texts_adopted` sat frozen at 251
rows opening on 20 January 2026, and the EP's November 2025 resolution on
protecting minors online was invisible to every search.

Two things are tested here:

  1. The whole chain is registered on a cron tier, IN DEPENDENCY ORDER, and every
     script accepts the arguments the registry passes it.
  2. A completeness detector runs LAST and exits non-zero on a real gap.

That second point is the durable half. A backfill reporting "292 dates, 0 errors"
is true and useless when the range itself was wrong -- which is exactly how an
eight-week hole across December 2025 and February 2026 survived a run that looked
clean. The detector asks the opposite question: what is MISSING?
"""
import subprocess
import sys

import pytest
from sqlalchemy import text

from services.sync.source_registry import sources_for_tier

# The chain, in the order the tier runner must execute it.
EXPECTED_ORDER = [
    "council_documents",
    "texts_adopted",
    "texts_adopted_bodies",
    "oeil_roles",
    "resolution_dates",
    "resolutions_corpus",
    "ep_enrich",
    "ep_council_gaps",
]


@pytest.fixture(scope="module")
def warm():
    return sources_for_tier("warm")


@pytest.fixture(scope="module")
def db():
    from core.database import SessionLocal
    s = SessionLocal()
    yield s
    s.close()


# ---------------------------------------------------------------------------
# 1. Registered, and in the right order
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", EXPECTED_ORDER)
def test_every_pipeline_step_is_scheduled(warm, key):
    """A step that is not registered runs only when a human remembers it."""
    assert key in [s.key for s in warm], f"{key} is not on the warm tier"


def test_the_chain_runs_in_dependency_order(warm):
    """The tier runner executes the registry list in order, so the order IS the
    dependency graph: fetch texts before their bodies, parse roles before the
    resolutions that reuse them, and check for gaps only after all of it."""
    got = [s.key for s in warm if s.key in EXPECTED_ORDER]
    assert got == EXPECTED_ORDER, f"pipeline order is wrong: {got}"


def test_the_gap_check_runs_last(warm):
    """It answers 'what is still missing AFTER everything ran'. Running it first
    would report gaps the same run was about to close."""
    keys = [s.key for s in warm]
    assert keys.index("ep_council_gaps") > max(
        keys.index(k) for k in EXPECTED_ORDER if k != "ep_council_gaps"
    ), "the completeness check does not run after the backfills"


@pytest.mark.parametrize("key", EXPECTED_ORDER)
def test_each_script_accepts_the_arguments_the_cron_passes(warm, key):
    """`feedback_cli_wrapper_parity`: a flag the registry passes that the script
    does not define makes the job fail on every run, silently as far as the
    corpus is concerned."""
    spec = next(s for s in warm if s.key == key)
    proc = subprocess.run([sys.executable, spec.script, "--help"],
                          capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, f"{spec.script} --help failed: {proc.stderr[-300:]}"
    missing = [a for a in spec.args if a.startswith("--") and a not in proc.stdout]
    assert not missing, f"{spec.script} does not define {missing}"


def test_the_warm_tier_is_actually_dispatched():
    """A registry entry nothing calls is decoration."""
    import datetime
    sys.path.insert(0, "scripts")
    import cron_dispatch as d
    fired = set()
    for hour in range(24):
        fired |= {path for _, path in d.decide_tiers(datetime.datetime(2026, 8, 18, hour, 0))}
    assert any("tier/warm" in p for p in fired), (
        "no hour of the day dispatches the warm tier, so the pipeline never runs"
    )


# ---------------------------------------------------------------------------
# 2. The detector
# ---------------------------------------------------------------------------

def test_the_detector_reports_no_gaps_right_now(db):
    from scripts.ep_council_completeness import run_checks
    gaps = [c for c in run_checks(db.connection()) if c["gap"]]
    assert not gaps, "open gaps: " + "; ".join(f"{g['check']}: {g['detail']}" for g in gaps)


def test_every_check_names_a_fix(db):
    """A gap report that does not say what to run is an investigation, not an alert."""
    from scripts.ep_council_completeness import run_checks
    for c in run_checks(db.connection()):
        assert c["fix"], f"{c['check']} has no remediation command"


def test_august_recess_is_encoded_not_alerted_on():
    """The Parliament does not sit in August. Without the calendar the month check
    would fire every summer, and a monitor that cries wolf gets switched off."""
    from scripts.ep_council_completeness import RECESS_MONTHS
    assert 8 in RECESS_MONTHS


def test_the_detector_exits_non_zero_on_a_gap():
    """Proven by construction rather than trusted: the script must return 1 so the
    cron records a FAILED run instead of a quiet success."""
    import inspect
    from scripts import ep_council_completeness as m
    src = inspect.getsource(m.main)
    assert "return 1 if gaps else 0" in src, (
        "the detector does not signal failure through its exit code"
    )


def test_health_endpoint_exposes_the_corpora_verdict():
    """A verdict that reaches only a log is not a monitor -- the same reason the
    scraper canary was made visible in this endpoint."""
    from fastapi.testclient import TestClient
    from main import app
    body = TestClient(app).get("/api/sync/health").json()
    assert "corpora" in body, "/api/sync/health does not report corpus completeness"
    assert body["corpora"].get("checks", 0) > 0
    # Three-state, like `healthy` on the tiers: True / False / None-when-unknown.
    assert body["corpora"].get("healthy") in (True, False, None)


def test_an_unreadable_check_is_an_error_not_a_clean_bill(db):
    """If the checks cannot run, the payload must say so rather than render
    identically to a corpus with nothing missing."""
    import inspect
    import api.sync_status as ss
    src = inspect.getsource(ss)
    assert '"error"' in src and "completeness checks failed" in src, (
        "a failed completeness check would report as healthy"
    )

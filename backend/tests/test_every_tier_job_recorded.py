"""Every job of a scheduled tier leaves a sync_runs row: by itself, or via the tier (17 Oct 2026).

Until then 35 of the 45 jobs of the 6-hourly, 12-hourly, weekly and monthly tiers wrote no row, so a
failure lived only in a log line: cellar_recent crashed on every run that met a non-sector-3 act from
14 May 2026 and was never seen. Same rule as tests/test_daily_tier_every_job_recorded.py.
"""
import ast
import re
from pathlib import Path

import pytest

from api import cron

BACKEND = Path(__file__).resolve().parents[1]
TREE = ast.parse((BACKEND / "api" / "cron.py").read_text())
TIERS = {
    "cron_sync_hot_6h": ("hot_6h", cron._HOT_TIER_RECORDED),
    "cron_sync_warm_12h": ("warm_12h", cron._WARM_TIER_RECORDED),
    "cron_sync_weekly": ("weekly", cron._WEEKLY_TIER_RECORDED),
    "cron_sync_monthly": ("monthly", cron._MONTHLY_TIER_RECORDED),
}


def _jobs(fn_name):
    """(results key, script or None for an in-process service) of each job the tier runs."""
    fn = next(n for n in TREE.body if getattr(n, "name", "") == fn_name)
    out = []
    for n in ast.walk(fn):
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") in ("_run_script_async", "_run_async_service"):
            key = n.args[0].value
            script = n.args[1].value if n.func.id == "_run_script_async" else None
            out.append((key, script))
    return fn, out


@pytest.mark.parametrize("fn_name", sorted(TIERS))
def test_every_job_is_recorded_exactly_once(fn_name):
    tier, recorded = TIERS[fn_name]
    fn, jobs = _jobs(fn_name)
    assert jobs and len(set(recorded)) == len(recorded)
    for key, script in jobs:
        self_records = bool(script) and bool(re.search(r"record_run|sync_runs|--record", (BACKEND / script).read_text()))
        assert (key in recorded) != self_records, (
            f"{tier}/{key}: recorded {'twice' if key in recorded else 'never'} (tier list={key in recorded}, "
            f"script records itself={self_records})")
    assert set(recorded) <= {k for k, _ in jobs}, "a listed job the tier does not run"


@pytest.mark.parametrize("fn_name", sorted(TIERS))
def test_the_tier_records_its_list_under_its_own_name(fn_name):
    tier, recorded = TIERS[fn_name]
    fn = next(n for n in TREE.body if getattr(n, "name", "") == fn_name)
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_record_tier_results"]
    assert len(calls) == 1 and calls[0].args[0].value == tier
    from api import sync_status
    assert tier in sync_status._JOB_STALE_AFTER_HOURS


def test_the_hot_rss_job_does_not_borrow_the_feed_registrys_name():
    """texts_adopted is the registry's scripts/sync_texts_adopted.py; the hot tier's service is another job."""
    from services.sync.source_registry import sources_for_tier
    registry = {s.key for t in ("fast", "warm") for s in sources_for_tier(t)}
    clash = {k for k in cron._HOT_TIER_RECORDED + cron._WARM_TIER_RECORDED if k in registry}
    assert clash == {"calendar"}  # the same script as the registry's calendar feed, so the same job


class _Db:
    def __init__(self):
        self.rows, self.closed = [], False

    def close(self):
        self.closed = True


def test_the_recorder_writes_one_row_per_listed_job_and_never_raises(monkeypatch):
    db = _Db()
    monkeypatch.setattr(cron, "SessionLocal", lambda: db)
    monkeypatch.setattr("services.sync.freshness.record_run", lambda _db, **k: _db.rows.append(k))
    results = {"cellar_recent": {"status": "failed", "stderr_tail": "AttributeError: PROPOSED"},
               "oeil": {"status": "success"}, "com_register": {"status": "success"}, "eurlex": "not a dict"}
    cron._record_tier_results("hot_6h", results, ("cellar_recent", "oeil", "eurlex", "missing"))
    assert db.closed and [(r["source_key"], r["tier"], r["status"], r["error"]) for r in db.rows] == [
        ("cellar_recent", "hot_6h", "failed", "AttributeError: PROPOSED"), ("oeil", "hot_6h", "success", None)]
    monkeypatch.setattr(cron, "SessionLocal", lambda: (_ for _ in ()).throw(RuntimeError("db down")))
    cron._record_tier_results("hot_6h", results, ("oeil",))  # logged, not raised

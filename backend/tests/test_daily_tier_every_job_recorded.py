"""Every daily-tier job must leave a sync_runs row: by itself, or via the tier.

25 Sep 2026: 11 of the 29 daily jobs (consultations, the Have Your Say sweep,
comitology, sanctions...) wrote no row, so a failure lived only in a log line.
Static check over api/cron.py, so a new daily job cannot ship unrecorded.
"""
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
SRC = (BACKEND / "api" / "cron.py").read_text()

# sync_dg_grow.py records its own row for tris, not for tbt; the shared file
# mentions record_run, so tbt must be recorded by the tier regardless.
SHARED_SCRIPT_NOT_SELF_RECORDING = {"tbt"}


def _tuple(name):
    body = re.search(rf"{name} = \((.*?)\)\n", SRC, re.S).group(1)
    return set(re.findall(r'"([a-z0-9_]+)"', body))


def _daily_jobs():
    start = SRC.index("Daily sync (04:00 UTC)")
    end = SRC.index('return {"status": "success", "tier": "daily"', start)
    return re.findall(r'_run_script_async\(\s*"([a-z0-9_]+)",\s*"(scripts/[a-z0-9_/]+\.py)"',
                      SRC[start:end])


def test_every_daily_job_is_recorded_exactly_once():
    tier = _tuple("_TENDERATOR_CHAIN") | _tuple("_DAILY_TIER_RECORDED")
    jobs = _daily_jobs()
    assert len(jobs) >= 29
    for key, script in jobs:
        self_records = (bool(re.search(r"record_run|sync_runs|--record",
                                        (BACKEND / script).read_text()))
                        and key not in SHARED_SCRIPT_NOT_SELF_RECORDING)
        assert (key in tier) != self_records, (
            f"{key}: recorded {'twice' if key in tier else 'never'} "
            f"(tier={key in tier}, script records itself={self_records})")

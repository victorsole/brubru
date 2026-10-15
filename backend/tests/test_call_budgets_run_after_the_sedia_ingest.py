"""Calls for proposals get their budget every day, after the SEDIA ingest (15 Oct 2026).

/api/v2/funding/ft-calls-for-proposals served no budget on 2,765 of 2,822 calls: the
ingest never writes one, and backfill_call_budgets.py, which reads it from the portal's
topic file, had been run once, for open LIFE calls."""
from __future__ import annotations

from pathlib import Path

CRON = (Path(__file__).resolve().parents[1] / "api" / "cron.py").read_text()


def test_the_budget_job_runs_after_the_ingest_and_before_the_bridge():
    ingest = CRON.index('"scripts/ingest_funding_sedia.py"')
    budgets = CRON.index('"scripts/backfill_call_budgets.py"')
    bridge = CRON.index('"scripts/bridge_ft_tenders_to_tenders.py"')
    assert ingest < budgets < bridge


def test_the_budget_job_reads_every_call_not_only_open_life_ones():
    block = CRON[CRON.index('"scripts/backfill_call_budgets.py"'):][:200]
    assert '"--pattern", "%"' in block and '"--status", "any"' in block and '"--apply"' in block


def test_the_budget_job_is_recorded_by_the_tier():
    chain = CRON.split("_TENDERATOR_CHAIN = (")[1].split(")")[0]
    assert '"ft_call_budgets"' in chain

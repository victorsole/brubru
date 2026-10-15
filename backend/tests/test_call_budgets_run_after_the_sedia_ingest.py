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


# --- the figure itself -------------------------------------------------------------

import sys  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import backfill_call_budgets as budgets  # noqa: E402


def _entry(action, amount, year="2026"):
    return {"action": action, "budgetYearMap": {year: str(amount)}}


def test_one_envelope_listed_per_type_of_action_counts_once():
    # HORIZON-MSCA-2026-DN-01-01: DN, DN-JD and DN-ID under key 113402, each EUR 628,033,846.
    b = {"budgetTopicActionMap": {"113402": [
        _entry("HORIZON-MSCA-2026-DN-01-01 - HORIZON-TMA-MSCA-DN Doctoral Networks", 628033846),
        _entry("HORIZON-MSCA-2026-DN-01-01 - HORIZON-TMA-MSCA-DN-JD Joint Doctorates", 628033846),
        _entry("HORIZON-MSCA-2026-DN-01-01 - HORIZON-TMA-MSCA-DN-ID Industrial Doctorates", 628033846)]}}
    total, matched, _ = budgets.topic_budget(b, "HORIZON-MSCA-2026-DN-01-01")
    assert (total, matched) == (628033846.0, 3)


def test_separate_envelopes_and_years_add_up():
    b = {"budgetTopicActionMap": {
        "1": [_entry("LIFE-X - LIFE-SAP", 1000, "2026"), _entry("LIFE-X - LIFE-SAP", 500, "2027")],
        "2": [_entry("LIFE-X - LIFE-SAP", 200)]}}
    assert budgets.topic_budget(b, "LIFE-X")[0] == 1700.0


def test_a_longer_identifier_is_not_the_topic_and_a_bad_entry_is_skipped():
    b = {"budgetTopicActionMap": {"9": [
        "not an entry", _entry("HORIZON-CL5-2021-D2-01-16 - HORIZON-RIA", 37000000),
        _entry("HORIZON-CL5-2021-D2-01-1 - HORIZON-IA", 5000000)]}}
    total, matched, shared = budgets.topic_budget(b, "HORIZON-CL5-2021-D2-01-1")
    assert (total, matched) == (5000000.0, 1) and shared == ["HORIZON-CL5-2021-D2-01-16"]

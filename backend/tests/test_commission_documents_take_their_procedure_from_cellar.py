"""Commission documents take their procedure from Cellar's dossier (15 Oct 2026).

/api/v2/commission/commission-register-documents served procedure_ref empty on 1,623 of
1,627 documents. Checked against OEIL's own records on 117 proposals both cover: 117 agree."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts import backfill_commission_procedure_refs as job


@pytest.mark.parametrize("cellar,oeil", [
    ("2025/0052/COD", "2025/0052(COD)"),
    ("2026/0275/NLE", "2026/0275(NLE)"),
    ("not a procedure", None),
    ("", None),
])
def test_cellar_reference_is_written_as_oeil_writes_it(cellar, oeil):
    assert job.oeil_form(cellar) == oeil


def test_only_an_empty_procedure_is_written():
    assert "procedure_ref IS NULL" in str(job.STORE)


def test_the_job_runs_after_the_register_sync():
    cron = (Path(__file__).resolve().parents[1] / "api" / "cron.py").read_text()
    assert cron.index('"commission_docs", _commission_docs') < cron.index("backfill_commission_procedure_refs.py")


@pytest.mark.parametrize("celex,looked_up", [
    ("32024R1689R(03)", "32024R1689"),   # a corrigendum: the act it corrects
    ("32024R1689", "32024R1689"),
    ("52025PC0100", "52025PC0100"),
])
def test_a_corrigendum_is_looked_up_through_the_act_it_corrects(celex, looked_up):
    assert job.lookup_celex(celex) == looked_up


def test_adopted_acts_and_proposals_are_both_asked():
    assert job._CELEX.match("32026D0860") and job._CELEX.match("52025PC0100")
    assert not job._CELEX.match("62024CJ0001")

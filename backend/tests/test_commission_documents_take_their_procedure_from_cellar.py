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

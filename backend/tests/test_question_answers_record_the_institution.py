"""A parliamentary question's answer records the institution that gave it (15 Oct 2026).

answering_institution was empty on 2,520 questions, 1,713 of them answered: the answers job
wrote "European Commission" into answering_commissioner and never the institution."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import backfill_parl_question_answers as job  # noqa: E402


@pytest.mark.parametrize("text,code", [
    ("E-002605/2026\nAnswer given by Mr Brunner \non behalf of the European Commission\n(31.8.2026)", "COMMISSION"),
    ("Answer given by the High Representative/Vice-President Kallas on behalf of the European Commission", "COMMISSION"),
    ("Reply ... on behalf of the Council (12.3.2026)", "COUNCIL"),
    ("Answer given by President Lagarde on behalf of the European Central Bank", "ECB"),
    ("no answer yet", None),
    (None, None),
])
def test_the_answer_names_its_institution(text, code):
    assert job.answering_institution_from_text(text) == code


def test_the_job_writes_the_institution_only_where_empty():
    src = inspect.getsource(job)
    assert "answering_institution = COALESCE(answering_institution, %s)" in src

"""text_answer stopped being filled on 7 May 2026 and nothing said so.

`backfill_parl_question_answers.py` knows the correct EP manifestation path and
works. It was registered in no scheduler, so it only ever ran when someone ran it
by hand, and the last hand-run was in May: 1,374 answered questions since June had
no answer text. Meanwhile the job that IS scheduled,
`backfill_parl_question_text.py`, selected those same rows and spent one EP fetch
on each to fill nothing, because its `fetch_answer_docx_url()` was a stub that
returned None. Both halves reported success throughout.

A MANDATORY line in a docstring is a reminder; only a scheduler runs anything.
"""
import ast
import pathlib
import re

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
REGISTRY = BACKEND / "services" / "sync" / "source_registry.py"
ANSWERS = BACKEND / "scripts" / "backfill_parl_question_answers.py"
TEXT = BACKEND / "scripts" / "backfill_parl_question_text.py"


def test_the_answers_job_is_actually_scheduled():
    assert "backfill_parl_question_answers.py" in REGISTRY.read_text(), (
        "backfill_parl_question_answers.py fills text_answer, which /parliament/questions "
        "serves, but no scheduler runs it. That is how text_answer went five months "
        "unfilled while every job reported success.")


def test_the_answers_job_can_be_scheduled_safely():
    """A scheduled run must be bounded and must record a verdict."""
    src = ANSWERS.read_text()
    assert "--max-seconds" in src, "a scheduled job needs a budget or the runner kills it mid-flight"
    assert "[SYNC_STATUS] degraded" in src, "leftovers must be reported, not left silent"
    assert "[ERROR]" in src, "a source that returns nothing must not read as success"
    tree = ast.parse(src)
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    returns = [n for n in ast.walk(main) if isinstance(n, ast.Return) and n.value is not None]
    assert returns, "main() must return an exit status so the runner can judge the run"


def test_each_job_owns_one_field():
    """The text job must not select rows it cannot fill."""
    src = TEXT.read_text()
    where = re.search(r'where\s*=\s*\(?["\'](.+?)["\']\s*\)?\n', src, re.S)
    assert where, "could not find the row selection in backfill_parl_question_text.py"
    clause = where.group(1)
    assert "text_answer" not in clause, (
        "backfill_parl_question_text.py selects rows missing text_answer but cannot fill "
        "them; that cost one EP fetch per row and filled nothing for 1,563 rows every run")
    assert "text_question" in clause


def test_the_dead_answer_stub_is_gone():
    src = TEXT.read_text()
    assert "fetch_answer_docx_url" not in src, (
        "the stub returned None unconditionally, so every answer it was asked for was "
        "silently dropped")

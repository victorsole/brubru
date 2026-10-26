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


# Bounded since 26 Oct 2026: every run from 23 Oct 18:19 was killed at the tier's 600 s timeout,
# because Cellar left two batches hanging for 150 s and a batch could take 120 s x 3 plus waits.

def test_a_question_gets_one_retry_inside_the_timeout(monkeypatch):
    calls, waits = [], []

    def _hang(req, timeout):
        calls.append(timeout)
        raise TimeoutError("timed out")
    monkeypatch.setattr(job.urllib.request, "urlopen", _hang)
    monkeypatch.setattr(job.time, "sleep", waits.append)
    with pytest.raises(TimeoutError):
        job.query(["52025PC0100"])
    assert calls == [job.QUERY_TIMEOUT, job.QUERY_TIMEOUT] and waits == [5]


def test_the_worst_batch_after_the_budget_still_ends_before_the_tier_kills_the_job():
    cron = (Path(__file__).resolve().parents[1] / "api" / "cron.py").read_text()
    call = cron[cron.index('"commission_doc_procedures", "scripts/backfill_commission_procedure_refs.py"'):]
    call = call[:call.index(")")]
    budget = int(call.split('"--max-seconds", "')[1].split('"')[0])
    assert budget + 2 * job.QUERY_TIMEOUT + 5 < 600


class _Engine:
    def __init__(self, rows):
        self.rows = rows

    def connect(self):
        engine = self

        class _C:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def execute(self, stmt, params=None):
                return type("R", (), {"fetchall": lambda s: engine.rows})()
        return _C()


def _run(monkeypatch, n, answer, argv=()):
    rows = [type("Row", (), {"id": i, "celex": f"52025PC{i:04d}"})() for i in range(n)]
    monkeypatch.setenv("DATABASE_URL", "postgresql://ci")
    monkeypatch.setattr(job, "create_engine", lambda url, **kw: _Engine(rows))
    monkeypatch.setattr(job.time, "sleep", lambda s: None)
    monkeypatch.setattr(job, "query", answer)
    return job.main(list(argv))


def test_unanswered_batches_are_degraded_not_a_failure(monkeypatch, capsys):
    seen = []

    def _answer(celexes):
        seen.append(len(celexes))
        if len(seen) == 2:
            raise TimeoutError("hung")
        return {}
    assert _run(monkeypatch, 100, _answer) == 0
    out = capsys.readouterr().out
    assert seen == [20] * 5 and "[SYNC_STATUS] degraded: Cellar did not answer 1 of 5 batch(es)" in out


def test_no_answer_at_all_is_still_a_failure(monkeypatch, capsys):
    def _never(celexes):
        raise TimeoutError("down")
    assert _run(monkeypatch, 60, _never) == 1 and "[ERROR] Cellar answered no batch" in capsys.readouterr().out


def test_the_run_stops_between_batches_at_its_budget(monkeypatch, capsys):
    clock = iter(range(0, 10_000, 200))                     # each look at the clock: +200 s
    monkeypatch.setattr(job.time, "monotonic", lambda: next(clock))
    assert _run(monkeypatch, 100, lambda celexes: {}, ["--max-seconds", "480"]) == 0
    out = capsys.readouterr().out
    assert "time budget of 480s reached; 3 batch(es) left" in out and "2 of 2 batch" not in out
    assert "degraded: Cellar did not answer 0 of 2 batch(es); 3 not asked (time budget)" in out

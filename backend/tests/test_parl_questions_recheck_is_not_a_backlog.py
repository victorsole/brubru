"""The answer re-check is rolling work: it neither makes a run "degraded" nor starves the
newest unanswered questions.

18 Oct 2026: every warm run of parl_questions said "degraded: 385-473 question(s) left for
the next run", which read as a stalled ingestion. It was not: EP Open Data listed 3,904
questions for 2026 and every one was held ("new 0"). The count was the re-check of ~730
unanswered questions, which ran OLDEST first and stopped after ~400 per run, so the newest
~300 were never re-checked for an answer, run after run.

main() runs here against fakes for the database, the EP listing and the clock.
"""
import importlib
import pathlib
import sys
import types

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
mod = importlib.import_module("scripts.ingest_parl_questions")


def _ident(n):            # E-10-2026-00NNNN  ->  reference E-00NNNN/2026
    return f"E-10-2026-{n:06d}"


class _Cur:
    def __init__(self, held, stale):
        self.held, self.stale, self._last = held, stale, None
    def execute(self, sql, params=None):
        self._last = sql
    def fetchall(self):
        if "FROM parliamentary_questions" in self._last and "answered_date IS NULL" in self._last:
            return [(r,) for r in self.stale]
        if "FROM parliamentary_questions" in self._last:
            return [(r,) for r in self.held]
        return []


class _Conn:
    def __init__(self, held, stale): self.c = _Cur(held, stale)
    def cursor(self): return self.c
    def close(self): pass


class _Client:
    def __init__(self, *a, **k): pass
    def __enter__(self): return self
    def __exit__(self, *a): return False


def _run(monkeypatch, capsys, *, listed, held, stale, fetch_budget):
    fetched = []
    clock = {"t": 0.0}

    def monotonic():
        return clock["t"]

    def fetch_item(client, identifier):
        fetched.append(identifier)
        clock["t"] += 1.0
        return None                      # "missing upstream": nothing to write

    monkeypatch.setattr(mod, "list_ids", lambda client, year, deadline: list(listed))
    monkeypatch.setattr(mod, "fetch_item", fetch_item)
    monkeypatch.setattr(mod, "_flush", lambda url, rows: None)
    monkeypatch.setattr(mod.psycopg2, "connect", lambda url: _Conn(held, stale))
    monkeypatch.setattr(mod.httpx, "Client", _Client)
    monkeypatch.setattr(mod.time, "monotonic", monotonic)
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    db_url = importlib.import_module("scripts._db_url")
    monkeypatch.setattr(db_url, "get_database_url", lambda: "postgresql://fake")
    monkeypatch.setattr(sys, "argv", ["ingest_parl_questions.py", "--year", "2026",
                                      "--max-seconds", str(fetch_budget)])
    rc = mod.main()
    return rc, capsys.readouterr().out, fetched


def test_nothing_new_and_a_recheck_backlog_is_a_clean_run(monkeypatch, capsys):
    ids = [_ident(n) for n in range(1, 21)]
    held = [mod.reference(i) for i in ids]
    rc, out, fetched = _run(monkeypatch, capsys, listed=ids, held=held, stale=held[:12], fetch_budget=4)
    assert rc == 0
    assert "[SYNC_STATUS] degraded" not in out, out
    assert "rechecks_left=" in out


def test_unread_new_questions_still_degrade_the_run(monkeypatch, capsys):
    ids = [_ident(n) for n in range(1, 21)]
    held = [mod.reference(i) for i in ids[:10]]           # ten new, budget for four
    rc, out, fetched = _run(monkeypatch, capsys, listed=ids, held=held, stale=[], fetch_budget=4)
    assert rc == 0
    assert "degraded:" in out and "new question(s) left" in out, out


def test_the_recheck_is_shuffled_so_the_newest_are_reached(monkeypatch, capsys):
    ids = [_ident(n) for n in range(1, 21)]
    held = [mod.reference(i) for i in ids]
    stale = held[:12]                                       # oldest first, as the query returns
    monkeypatch.setattr(mod.random, "shuffle", lambda xs: xs.reverse())
    rc, out, fetched = _run(monkeypatch, capsys, listed=ids, held=held, stale=stale, fetch_budget=4)
    assert fetched and fetched[0] == ids[11], f"re-check did not start from the shuffled order: {fetched}"

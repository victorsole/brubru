"""The hot tier's body fetcher re-checks the acts of new corrigenda (register O65, 23 Oct 2026).

The daily Cellar sync inserts a corrigendum without text; fetch_eu_law_bodies stores the text. A corrigendum can
correct its act's title date ("for: 4 April 2006, read: 4 April 2005", 32006D0635R(01)), so every run re-checks the
acts of the corrigenda whose text arrived in the last RECHECK_DAYS days. No database, no network: a fake connection
answers the statements, Cellar is stubbed.
"""
import importlib.util
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("fetch_eu_law_bodies_recheck", BACKEND / "scripts" / "fetch_eu_law_bodies.py")
feb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(feb)
import scripts.fix_eu_laws_dates as fx  # noqa: E402  (the module the fetcher imports when it re-checks)

TITLE = "Commission Decision 2006/635/Euratom of 4 April 2006 on the conclusion, by way of signature, of an Agreement"
BODY = ("Corrigendum to " + TITLE + " ( Official Journal of the European Union L 261 of 22 September 2006 ) On the "
        "cover in the contents and on page 26 in the title and the signature: for: 4 April 2006 , read: 4 April 2005 .")


class _Result:
    def __init__(self, rows, one=None):
        self.rows, self.rowcount, self._one = rows, len(rows), one

    def fetchall(self):
        return self.rows

    def __iter__(self):
        return iter(self.rows)

    def one(self):
        return self._one


class _Conn:
    """eu_laws as the statements of the fetcher and of recheck_acts see it."""

    def __init__(self, recent, acts, corrigenda, picked=()):
        self.recent, self.acts, self.corrigenda, self.picked = recent, acts, corrigenda, list(picked)
        self.updates, self.commits = [], 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, stmt, params=None):
        q = " ".join(str(stmt).split())
        if "body_fetched_at > now()" in q:
            assert params == {"days": feb.RECHECK_DAYS}
            return _Result([SimpleNamespace(celex=c) for c in self.recent])
        if q.startswith("SELECT id, celex, uuid, date::text"):
            return _Result([r for r in self.acts if r[1] in params["a"]])
        if "regexp_replace" in q:
            return _Result([(c, "no-folder-" + c) for c in self.corrigenda
                            if re.sub(r"R\(\d\d\)$", "", c) in params["a"]])
        if q.startswith("SELECT celex, body_txt"):
            return _Result([(c, self.corrigenda[c]) for c in params["c"]])
        if q.startswith("UPDATE eu_laws SET date"):
            self.updates.append((params["i"], params["new"]))
            return _Result([params["i"]])
        if q.startswith("SELECT count(*) AS total"):
            return _Result([], one=SimpleNamespace(total=2, fetched=1, real_bodies=1, avg_chars=900))
        if q.startswith("SELECT id, celex FROM eu_laws"):
            return _Result(self.picked)
        raise AssertionError(q)

    def commit(self):
        self.commits += 1


class _Engine:
    def __init__(self, conn):
        self.conn = conn

    def connect(self):
        return self.conn

    def dispose(self):
        pass


def _conn(**kw):
    return _Conn(recent=kw.get("recent", ["32006D0635R(01)"]),
                 acts=kw.get("acts", [(1, "32006D0635", "u-act", "2006-04-04", TITLE, "OJ_2026-10")]),
                 corrigenda=kw.get("corrigenda", {"32006D0635R(01)": BODY}), picked=kw.get("picked", ()))


def test_the_act_of_a_new_corrigendum_takes_the_date_it_corrects_to(monkeypatch):
    monkeypatch.setattr(fx, "cellar_dates", lambda celexes: {"32006D0635": "2005-04-04"})
    conn = _conn()
    assert feb.recheck_corrected_acts(_Engine(conn)) == (1, 1)
    assert conn.updates == [(1, "2005-04-04")] and conn.commits == 1


def test_cellar_not_yet_corrected_leaves_the_title_date(monkeypatch):
    # the next runs within RECHECK_DAYS read Cellar again
    monkeypatch.setattr(fx, "cellar_dates", lambda celexes: {"32006D0635": "2006-04-04"})
    conn = _conn()
    assert feb.recheck_corrected_acts(_Engine(conn)) == (1, 0)
    assert conn.updates == []


def test_a_corrigendum_of_another_part_of_the_text_moves_nothing(monkeypatch):
    monkeypatch.setattr(fx, "cellar_dates", lambda celexes: pytest.fail("Cellar read without a date correction"))
    # a date is corrected, but not the title's: Cellar is not even asked
    conn = _conn(corrigenda={"32006D0635R(01)": "On page 27, Article 3: for: 1 January 2007 , read: 1 July 2007 ."})
    assert feb.recheck_corrected_acts(_Engine(conn)) == (1, 0)
    assert conn.updates == []


def test_no_new_corrigendum_no_work(monkeypatch):
    monkeypatch.setattr(fx, "cellar_dates", lambda celexes: pytest.fail("Cellar read with nothing to check"))
    conn = _conn(recent=[])
    assert feb.recheck_corrected_acts(_Engine(conn)) == (0, 0)
    assert conn.updates == [] and conn.commits == 0


def _run_main(monkeypatch, recheck):
    conn = _conn(picked=[SimpleNamespace(id=7, celex="32026R0001")])
    monkeypatch.setattr(feb, "create_engine", lambda *a, **k: _Engine(conn))
    monkeypatch.setattr(feb, "_database_url", lambda: "postgresql://fake")
    monkeypatch.setattr(feb, "_fetch", lambda celex, ctx: ("<p>act</p>", "x" * 700))
    stored = []
    monkeypatch.setattr(feb, "store", lambda engine, rid, html, txt: stored.append(rid))
    monkeypatch.setattr(feb, "recheck_corrected_acts", recheck)
    monkeypatch.setattr(sys, "argv", ["fetch_eu_law_bodies.py", "--apply", "--limit", "1", "--pause", "0"])
    return feb.main(), stored


def test_every_run_ends_with_the_recheck(monkeypatch):
    calls = []
    rc, stored = _run_main(monkeypatch, lambda engine: calls.append(engine) or (0, 0))
    assert rc == 0 and stored == [7] and len(calls) == 1


def test_a_failed_recheck_fails_the_run_after_the_bodies_are_stored(monkeypatch, capsys):
    def boom(engine):
        raise TimeoutError("Cellar SPARQL")
    rc, stored = _run_main(monkeypatch, boom)
    assert rc == 1 and stored == [7]
    assert "re-check of the acts of new corrigenda failed" in capsys.readouterr().out

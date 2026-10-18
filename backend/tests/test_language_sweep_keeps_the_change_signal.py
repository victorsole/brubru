"""Filling a notice's language does not make the notice look changed.

18 Oct 2026, brubru_change_log: every night ~100 TED tenders had updated_at moved by the
Tenderator language sweep (scripts/backfill_tenderator_translations.py) and nothing else:
detected_lang filled for the first time on rows ingested the day before. GovClipping's
/funding/tenders window that morning held 101 rows, 100 of them only that. The language
is a fact the notice always had; the sweep now writes inside the keep-change-signal
switch (brubru.keep_change_signal = this transaction's id, migrations 293/302/303).

The test runs the real _write_batch against a recording connection.
"""
import importlib
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
mod = importlib.import_module("scripts.backfill_tenderator_translations")


class _Cur:
    def __init__(self, log): self.log = log
    def execute(self, sql, params=None): self.log.append(" ".join(str(sql).split()))


class _Conn:
    def __init__(self): self.log = []; self.committed = False
    def cursor(self, *a, **k): return _Cur(self.log)
    def commit(self): self.committed = True
    def rollback(self): pass
    def close(self): pass


def test_the_switch_is_set_before_the_language_is_written(monkeypatch):
    conn = _Conn()
    monkeypatch.setattr(mod, "_db", lambda: conn)
    table = "tenders"
    spec = mod.SOURCES[table]
    mod._write_batch(spec, table, [("57515", "de", [])])
    switch = [i for i, s in enumerate(conn.log) if "brubru.keep_change_signal" in s and "txid_current()" in s]
    update = [i for i, s in enumerate(conn.log) if s.startswith(f"UPDATE {table} SET detected_lang")]
    assert switch and update, conn.log
    assert switch[0] < update[0], "the language was written before the switch was set"
    assert "true)" in conn.log[switch[0]], "the switch must be local to the transaction"
    assert conn.committed

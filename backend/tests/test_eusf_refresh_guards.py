"""The EUSF refresh upserts on case_key (migration 284) so a case keeps its id; until
9 Oct 2026 it deleted the table and re-inserted every case weekly. An empty fetch must
fail loudly and never reach the database. Non-live: runs in CI."""
import importlib.util
import pathlib
import sys

import pytest


def _module():
    path = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "backfill_eusf.py"
    spec = importlib.util.spec_from_file_location("_eusf", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_an_empty_fetch_exits_non_zero_before_any_write(monkeypatch):
    mod = _module()
    monkeypatch.setattr(mod, "fetch", lambda: [])
    monkeypatch.setattr(mod, "ChunkedDb", lambda *a, **k: pytest.fail("touched the database on an empty fetch"))
    monkeypatch.setattr(sys, "argv", ["backfill_eusf.py", "--apply"])
    with pytest.raises(SystemExit) as e:
        mod.main()
    assert e.value.code == 1


def test_the_refresh_no_longer_wipes_the_table():
    src = (pathlib.Path(__file__).resolve().parents[1] / "scripts" / "backfill_eusf.py").read_text()
    assert 'DELETE FROM eu_solidarity_fund")' not in src, "the full-table delete is back"
    assert "ON CONFLICT (case_key)" in src

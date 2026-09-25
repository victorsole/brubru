"""A throttled EP Open Data must stop the text job early, not record 400 failures.

25 Sep 2026: 761 of 761 failures in a drain were HTTP 429. Real DB read, no writes
(dry run), the EP fetch patched to always fail.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "backfill_parl_question_text", HERE.parent / "scripts" / "backfill_parl_question_text.py")
bt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bt)


def test_stops_after_ten_consecutive_failures(monkeypatch, capsys):
    monkeypatch.setattr(bt, "fetch_question_payload", lambda ref: None)
    monkeypatch.setattr(bt.time, "sleep", lambda s: None)
    monkeypatch.setattr(sys, "argv", ["x", "--limit", "40", "--throttle", "0"])
    rc = bt.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert out.count("[MISS]") == 10
    assert "[STOP]" in out and "degraded: throttled" in out

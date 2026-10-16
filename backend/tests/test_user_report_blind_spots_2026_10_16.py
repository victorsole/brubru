"""Blind-spot checks rewritten on 16 Oct 2026: each one can tell a traffic fact from a broken instrument.

- analytics join: scoped to the window, harness rows (no conversation) named, not failed;
- notifications: read rate measured against recipients who came back;
- anonymous pre_user_id: widened when the window is empty;
- probe share: split into "marker in use" and "real chats in window".
"""
import datetime as dt

import pytest

import scripts.user_activity_report as rpt

END = dt.datetime(2026, 10, 16, tzinfo=dt.timezone.utc)
START = END - dt.timedelta(days=2)


def _fake_q(answers):
    """answers: list of (substring, rows, wide_rows). The first matching substring wins;
    `wide_rows` is returned when the query is for the widened window."""
    def q(conn, sql, **params):
        for needle, rows, wide in answers:
            if needle in sql:
                widened = params.get("start") is not None and params["start"] < START
                return wide if (widened and wide is not None) else rows
        return [{"__error__": "not stubbed"}]
    return q


def _checks(monkeypatch, answers):
    monkeypatch.setattr(rpt, "q", _fake_q(answers))
    return {c["check"]: c for c in rpt.section_blind_spots(None, START, END)}


BASE = [
    ("AS harness", [{"n": 3, "harness": 2, "with_conv": 1, "resolves": 1}], None),
    ("abandoned_streams", [{"empty": 0, "abandoned": 0}], None),
    ("read_seeable", [{"sent": 5, "read": 0, "seeable": 0, "read_seeable": 0}], None),
    ("AS orphaned", [{"orphaned": 0, "linked": 0}], [{"orphaned": 0, "linked": 4}]),
    ("AS marked", [{"total": 7, "synthetic": 7, "marked": 7}], None),
]


def test_harness_rows_do_not_fail_the_join_check(monkeypatch):
    c = _checks(monkeypatch, BASE)["chat_analytics rows join to the answer they describe"]
    assert c["ok"] and not c["unproven"]
    assert "2 harness rows" in c["detail"]


def test_an_unresolved_id_still_fails(monkeypatch):
    answers = [("AS harness", [{"n": 2, "harness": 0, "with_conv": 2, "resolves": 1}], None)] + BASE[1:]
    c = _checks(monkeypatch, answers)["chat_analytics rows join to the answer they describe"]
    assert not c["ok"]


def test_notifications_nobody_could_see_are_unproven_not_failed(monkeypatch):
    c = _checks(monkeypatch, BASE)["notifications get read (by recipients who came back)"]
    assert c["unproven"] and "came back" in c["unproven_means"]


def test_notifications_seen_and_unread_fail(monkeypatch):
    answers = BASE[:2] + [("read_seeable", [{"sent": 5, "read": 0, "seeable": 3, "read_seeable": 0}], None)] + BASE[3:]
    c = _checks(monkeypatch, answers)["notifications get read (by recipients who came back)"]
    assert not c["ok"] and not c["unproven"]


def test_anonymous_check_widens_an_empty_window(monkeypatch):
    c = _checks(monkeypatch, BASE)["anonymous chats carry a pre_user_id"]
    assert c["ok"] and not c["unproven"] and "widened" in c["detail"]


def test_probe_share_split_marker_ok_real_traffic_unproven(monkeypatch):
    checks = _checks(monkeypatch, BASE)
    assert checks["probe marker in use (probes are told apart from users)"]["ok"]
    real = checks["real (non-probe) chats in window"]
    assert real["unproven"] and real["detail"] == "0 real of 7 chats"


def test_unmarked_probes_still_fail_the_marker_check(monkeypatch):
    answers = BASE[:4] + [("AS marked", [{"total": 7, "synthetic": 0, "marked": 0}], None)]
    assert not _checks(monkeypatch, answers)["probe marker in use (probes are told apart from users)"]["ok"]


def test_each_unproven_check_explains_itself(monkeypatch):
    unproven = [c for c in _checks(monkeypatch, BASE).values() if c.get("unproven")]
    assert unproven and all(c.get("unproven_means") for c in unproven)
    assert any("traffic fact" in c["unproven_means"] for c in unproven)

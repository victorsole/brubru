"""Unclaimed pre-provisioned shells receive no notifications (16 Oct 2026)."""
import datetime as dt
import pathlib
from types import SimpleNamespace

from services.notifications.recipients import ShellFilter, is_unclaimed_shell, unclaimed_shell_sql

NOW = dt.datetime(2026, 10, 16, tzinfo=dt.timezone.utc)
ROOT = pathlib.Path(__file__).resolve().parents[1]


def _user(pre=None, claimed=None, login=None):
    return SimpleNamespace(pre_provisioned_at=pre, claimed_at=claimed, last_login=login)


def test_shell_is_provisioned_unclaimed_and_never_signed_in():
    assert is_unclaimed_shell(_user(pre=NOW)) is True


def test_a_claimed_or_signed_in_profile_is_a_real_account():
    assert is_unclaimed_shell(_user(pre=NOW, claimed=NOW)) is False
    assert is_unclaimed_shell(_user(pre=NOW, login=NOW)) is False  # GBSB staff signed into a shell
    assert is_unclaimed_shell(_user()) is False                    # an ordinary signup


def test_sql_predicate_matches_the_users_report_definition():
    sql = unclaimed_shell_sql("u")
    report = (ROOT / "scripts" / "user_activity_report.py").read_text()
    assert "u.pre_provisioned_at IS NOT NULL AND u.claimed_at IS NULL" in sql
    assert "u.last_login IS NULL" in sql
    assert "u.pre_provisioned_at IS NOT NULL AND u.claimed_at IS NULL" in report


def test_shell_filter_queries_once():
    calls = []

    class FakeDB:
        def execute(self, *_a, **_k):
            calls.append(1)
            return SimpleNamespace(fetchall=lambda: [("11111111-1111-1111-1111-111111111111",)])

    f = ShellFilter(FakeDB())
    assert f("11111111-1111-1111-1111-111111111111") is True
    assert f("22222222-2222-2222-2222-222222222222") is False
    assert len(calls) == 1


def test_every_live_producer_applies_the_guard():
    for rel in ("services/alerts/saved_search_runner.py", "services/alerts/gac_agenda_hawk.py",
                "services/notifications/carriage_status_notifier.py", "services/tenders/tender_notifications.py"):
        src = (ROOT / rel).read_text()
        assert ("unclaimed_shell" in src) or ("pre_provisioned_at" in src and "claimed_at" in src), rel

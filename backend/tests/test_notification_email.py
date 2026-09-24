"""The notification email channel (24 Sep 2026): gated, once-only, honest counts."""
from datetime import datetime, timezone

import pytest

import services.notifications.notification_email as ne


class _DB:
    def __init__(self):
        self.stamped = []
        self.commits = 0

    def execute(self, stmt, params=None):
        self.stamped.append(list(params["ids"]))

    def commit(self):
        self.commits += 1


def _rec(email, types=("status_change",), name="Anna"):
    items = [ne.Item(f"00000000-0000-0000-0000-00000000000{i}", t, f"File {i} moved",
                     "Status: close to adoption", "/my-eu-bubble", datetime(2026, 9, 24, tzinfo=timezone.utc))
             for i, t in enumerate(types)]
    return ne.Recipient(user_id="u", email=email, name=name, items=items)


@pytest.fixture
def recipients(monkeypatch):
    box = []
    monkeypatch.setattr(ne, "collect", lambda db, window_days=7: [r for r in box])
    return box


def test_disabled_sends_nothing_and_stamps_nothing(recipients):
    recipients.append(_rec("client@firm.eu"))
    sent = []
    db = _DB()
    s = ne.run(db, enabled=False, only=None, send=lambda *a: sent.append(a) or True)
    assert sent == [] and db.stamped == []
    assert s.recipients == 1 and s.emails_sent == 0
    assert s.would_send == ["client@firm.eu: 1 item(s)"]
    assert "CHANNEL DISABLED" in s.line()


def test_enabled_sends_once_and_stamps_after_success(recipients):
    recipients.append(_rec("client@firm.eu", types=("status_change", "tender_digest")))
    db = _DB()
    s = ne.run(db, enabled=True, only=None, send=lambda *a: True)
    assert s.emails_sent == 1 and len(db.stamped) == 1 and len(db.stamped[0]) == 2


def test_failed_send_is_counted_and_never_stamped(recipients):
    recipients.append(_rec("client@firm.eu"))
    db = _DB()
    s = ne.run(db, enabled=True, only=None, send=lambda *a: False)
    assert s.send_failures == 1 and s.emails_sent == 0 and db.stamped == []


def test_synthetic_and_prospect_recipients_never_get_email(recipients):
    for e in ("prospect+x@brubru.beresol.eu", "demo@example.com", "a@b.invalid"):
        recipients.append(_rec(e))
    sent = []
    s = ne.run(_DB(), enabled=True, only=None, send=lambda *a: sent.append(a) or True)
    assert sent == [] and s.skipped_synthetic == 3


def test_allowlist_limits_a_staged_rollout(recipients):
    recipients += [_rec("hello@beresol.eu"), _rec("client@firm.eu")]
    sent = []
    s = ne.run(_DB(), enabled=True, only={"hello@beresol.eu"}, send=lambda to, *a: sent.append(to) or True)
    assert sent == ["hello@beresol.eu"] and s.skipped_not_allowed == 1


def test_tender_optout_items_are_dropped(recipients):
    r = _rec("client@firm.eu", types=("__tender_optout__",))
    recipients.append(r)
    sent = []
    s = ne.run(_DB(), enabled=True, only=None, send=lambda *a: sent.append(a) or True)
    assert sent == [] and s.skipped_tender_optout == 1


def test_render_is_plain_british_and_linked():
    subject, html_body, text_body = ne.render(_rec("client@firm.eu", types=("status_change", "tender_digest")))
    assert subject == "Brubru: 2 updates since your last visit"
    assert "https://brubru.beresol.eu/my-eu-bubble" in html_body and "hello@beresol.eu" in text_body
    assert "—" not in html_body + text_body  # no em-dashes, house rule


def test_channel_is_off_unless_explicitly_enabled(monkeypatch):
    monkeypatch.delenv("NOTIFICATION_EMAIL_ENABLED", raising=False)
    assert ne.channel_enabled() is False
    monkeypatch.setenv("NOTIFICATION_EMAIL_ENABLED", "true")
    assert ne.channel_enabled() is True

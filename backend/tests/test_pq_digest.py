"""Weekly Parliamentary Questions digest (28 Sep 2026)."""
from datetime import date
from types import SimpleNamespace

import pytest

import services.notifications.pq_digest as d


def _row(subject, text=""):
    return SimpleNamespace(subject=subject, text_question=text)


def test_scoring_is_whole_word_and_needs_two_points():
    kws = ["reach", "border", "energy", "carbon"]
    assert d._score(_row("Breach of data rules in Member States"), kws) == 0          # not "reach"
    assert d._score(_row("Cross-border recognition of qualifications"), kws) == 0     # not "border"
    assert d._score(_row("Energy prices for SMEs"), kws) == 2                         # subject hit
    assert d._score(_row("Prices", "energy and carbon costs"), kws) == 2             # two in the text
    assert d._score(_row("Prices", "energy costs only"), kws) < d.MIN_SCORE          # one in the text


def test_stale_feed_is_refused(monkeypatch):
    monkeypatch.setattr(d, "feed_problem", lambda db, today: "last clean run 50 h ago")
    with pytest.raises(d.StaleFeed):
        d.run(object(), apply=False, today=date(2026, 9, 28))


def test_ep_lag_of_a_week_is_normal_but_three_weeks_is_not(monkeypatch):
    class DB:          # only the sync_runs lookup reaches the database (feed_newest is patched)
        def __init__(self, _unused, ok):
            self.vals = [ok]
        def execute(self, *a, **k):
            v = self.vals.pop(0) if self.vals else None
            return type("R", (), {"scalar": lambda _s: v})()
    from datetime import datetime, timedelta, timezone
    fresh = datetime.now(timezone.utc) - timedelta(hours=3)
    monkeypatch.setattr(d, "feed_newest", lambda db: date(2026, 9, 18))
    assert d.feed_problem(DB(None, fresh), date(2026, 9, 28)) is None       # EP 10 days behind: normal
    monkeypatch.setattr(d, "feed_newest", lambda db: date(2026, 9, 1))
    assert "days old" in d.feed_problem(DB(None, fresh), date(2026, 9, 28))


@pytest.mark.parametrize("lang", ["en", "es", "ca", "fr", "it", "nl"])
def test_wording_singular_plural_every_language(lang):
    one = d.WeekSet(asked_total=1, answered_total=1, asked=[{"subject": "E-003700/2026 - Safety of e-scooters"}])
    many = d.WeekSet(asked_total=5, answered_total=3, asked=[{"subject": "Safety of e-scooters"}])
    t1, m1 = d.compose(one, lang)
    t5, m5 = d.compose(many, lang)
    assert "1" in t1 and "5" in t5 and t1 != t5
    assert "E-003700" not in m1                     # no institutional codes in prose
    assert "—" not in t1 + m1 + t5 + m5             # no em-dashes


def test_catalan_plural_is_catalan():
    t, m = d.compose(d.WeekSet(asked_total=5, answered_total=3), "ca")
    assert "preguntes parlamentàries noves" in t and "preguntas" not in t + m


def test_this_week_route_precedes_the_catch_all():
    from api.parliamentary_questions import router
    paths = [r.path for r in router.routes]
    assert paths.index("/api/parliamentary-questions/this-week") < paths.index(
        "/api/parliamentary-questions/{reference:path}")


def test_email_channel_carries_the_digest():
    from services.notifications.notification_email import EMAIL_TYPES
    assert "pq_digest" in EMAIL_TYPES


def test_broad_body_phrases_alone_are_not_enough():
    kws = ["internal market", "free movement", "competitiveness", "telecom"]
    assert not d.relevant(_row("European seed sovereignty", "internal market and competitiveness"), kws)
    assert d.relevant(_row("Telecom spectrum auctions", ""), kws)
    assert d.relevant(_row("Seeds", "internal market, free movement and competitiveness"), kws)


def test_scheduled_run_is_off_until_enabled(monkeypatch):
    import services.schedulers.notification_scheduler as ns
    calls, rows = {}, []
    import services.notifications.pq_digest as pqd
    def fake_run(db, *, apply, **_):
        calls["apply"] = apply
        return pqd.RunResult(users=2, with_interests=2, previews=[{"email": "a@x.eu"}])
    monkeypatch.setattr(pqd, "run", fake_run)
    monkeypatch.setattr("services.sync.freshness.record_run", lambda db, **k: rows.append(k))
    class _DB:
        def rollback(self): pass
        def close(self): pass
    monkeypatch.setattr("core.database.SessionLocal", lambda: _DB())
    monkeypatch.delenv("PQ_DIGEST_ENABLED", raising=False)
    out = ns._run_pq_digest()
    assert calls["apply"] is False and out["enabled"] is False
    assert rows[-1]["status"] == "skipped" and "a@x.eu" in rows[-1]["error"]

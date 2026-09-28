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
    monkeypatch.setattr(d, "feed_newest", lambda db: date(2026, 9, 18))
    with pytest.raises(d.StaleFeed):
        d.run(object(), apply=False, today=date(2026, 9, 28))


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

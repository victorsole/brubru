"""Calendar events are stored once and a past event is not 'scheduled' (16 Oct 2026)."""
from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

from api.v2.calendar import served_status
from scripts.dedupe_calendar_events import plan
from services.scrapers.euagenda_scraper import _best_card_title, drop_suffixed_twins

T = datetime(2026, 6, 6, 0, 3)


def _r(id_, source, ext, title, d=date(2026, 6, 6), first=T, last=T, typ="commissioner_meeting", url=""):
    return {"id": id_, "source": source, "external_id": ext, "event_type": typ, "t": title.lower(),
            "d": d, "first_seen": first, "last_updated": last, "source_url": url}


def test_the_copies_on_other_commissioners_agendas_go_and_the_hosts_stays():
    title = "Commissioner Dombrovskis meets with Mr Yassine Jaber, Minister of Finance of Lebanon"
    rows = [_r("own", "commissioner_agenda", "commissioner:valdis-dombrovskis:2026-06-06:a", title),
            _r("c1", "commissioner_agenda", "commissioner:apostolos-tzitzikostas:2026-06-06:a", title),
            _r("c2", "commissioner_agenda", "commissioner:marta-kos:2026-06-06:a", title)]
    assert sorted((g, k) for g, k, _ in plan(rows)) == [("c1", "own"), ("c2", "own")]


def test_other_sources_twins():
    later = datetime(2026, 10, 9)
    rows = [_r("e1", "euagenda", "euagenda:2026-06-01-data-week-leipzig", "Data Week Leipzig", typ="webinar"),
            _r("e2", "euagenda", "euagenda:2026-06-01-data-week-leipzig-2026-06", "Data Week Leipzig", typ="webinar"),
            _r("f_old", "ft_portal", "484101", "Connecting Europe Days", d=date(2026, 9, 28),
               first=datetime(2026, 6, 15), last=datetime(2026, 6, 15), typ="conference"),
            _r("f_new", "ft_portal", "6810670", "Connecting Europe Days", d=date(2026, 9, 28),
               first=later, last=later, typ="conference"),
            _r("p", "ep_calendar_json", "ep_2026_plenary_2026-02-23", "EP Committee Week", d=date(2026, 2, 23), typ="committee_week"),
            _r("w", "ep_calendar_json", "ep_2026_2026-02-23_committee_week", "EP Committee Week", d=date(2026, 2, 23), typ="committee_week")]
    got = sorted((g, k) for g, k, _ in plan(rows))
    assert got == [("e2", "e1"), ("f_old", "f_new"), ("p", "w")]


def test_two_portal_sessions_both_still_listed_stay():
    seen = datetime(2026, 10, 13)
    rows = [_r("b1", "ft_portal", "4292247", "Booster Info Session", typ="conference", first=datetime(2026, 9, 8), last=seen),
            _r("b2", "ft_portal", "4292248", "Booster Info Session", typ="conference", first=datetime(2026, 9, 8), last=seen)]
    assert plan(rows) == []


def test_euagenda_badge_titles_and_suffixed_twins():
    assert _best_card_title("Broadband", "berec-external-workshop-on-combating-fraud") == \
        "BEREC External Workshop on Combating Fraud"
    assert _best_card_title("SMEs", "ebrd-launch-event-in-romania") == "EBRD Launch Event in Romania"
    ev = [SimpleNamespace(external_id="euagenda:2026-06-02-clld-seminar"),
          SimpleNamespace(external_id="euagenda:2026-06-02-clld-seminar-2026-06"),
          SimpleNamespace(external_id="euagenda:2026-06-03-other-2026-06")]
    assert [e.external_id for e in drop_suffixed_twins(ev)] == [
        "euagenda:2026-06-02-clld-seminar", "euagenda:2026-06-03-other-2026-06"]


def test_a_past_event_is_completed_and_a_future_one_keeps_its_status():
    today = date(2026, 10, 16)
    assert served_status("scheduled", date(2026, 9, 28), None, today) == "completed"
    assert served_status("confirmed", date(2026, 10, 12), date(2026, 10, 16), today) == "confirmed"
    assert served_status("scheduled", date(2026, 10, 19), None, today) == "scheduled"
    assert served_status("cancelled", date(2026, 9, 1), None, today) == "cancelled"

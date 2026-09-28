"""EBA consultation listing parser and JRC Product Bureau workshop events (28 Sep 2026)."""
from datetime import date, datetime, time, timezone

import pytest

from services.scrapers.agency_consultations import _eba_row, ingest_eba_consultations
from services.scrapers.eu_calendar_sync_service import jrc_workshop_event

NOW = datetime(2026, 9, 28, tzinfo=timezone.utc)

_ROW = """<article class="teaser-event-calendar teaser-event-calendar--consultation" data-element="event-teaser">
 <a href="/publications-and-media/events/consultation-x" class="teaser-event-calendar__calendar">
 <div class="teaser-event-calendar__calendar-day-month" data-field="month">
 <div> <span class="teaser-event-calendar__calendar-day">25</span> <span class="teaser-event-calendar__calendar-month">Sep</span> </div>
 <div> <span class="teaser-event-calendar__calendar-day">4</span> <span class="teaser-event-calendar__calendar-month">Jan</span> </div>
 </div> <div class="teaser-event-calendar__calendar-year" data-field="year"> 2026 - 2027 </div> </a>
 <div class="teaser-event-calendar__content"> <h3 class="h4 teaser-event-calendar__title" data-field="title">
 <a href="/publications-and-media/events/consultation-x" rel="bookmark"> <span>Consultation on joint decisions</span> </a>
 <small>(EBA/CP/2026/19)</small></h3> </div> </article>"""


def test_eba_row_spans_the_year_boundary():
    it = _eba_row(_ROW, NOW)
    assert it.title == "Consultation on joint decisions"
    assert it.document_date.date() == date(2027, 1, 4)      # closing date in the SECOND year
    assert it.summary.startswith("Open · 2027-01-04 · EBA/CP/2026/19")
    assert it.public_url == "https://www.eba.europa.eu/publications-and-media/events/consultation-x"


def test_eba_row_single_year_closed():
    row = _ROW.replace("2026 - 2027", "2025").replace(">Jan<", ">Oct<")
    it = _eba_row(row, NOW)
    assert it.document_date.date() == date(2025, 10, 4)
    assert it.summary.startswith("Closed")


def test_eba_empty_listing_fails_loudly(monkeypatch):
    monkeypatch.setattr("services.scrapers.agency_consultations._fetch", lambda url: "<html>challenge</html>")
    with pytest.raises(RuntimeError):
        ingest_eba_consultations()


def test_jrc_workshop_event_reads_time_and_topic():
    row = {"title": "JRC ESPR methodology consultation workshop, 23 October 2026, 9:00-13:00 CET: "
                    "Method for the identification and tracking of substances of concern",
           "d": date(2026, 10, 23), "public_url": "https://susproc.jrc.ec.europa.eu/x#a", "summary": "Online workshop."}
    ev = jrc_workshop_event(row, date(2026, 9, 28))
    assert ev["event_type"] == "workshop" and ev["status"] == "scheduled"
    assert ev["start_time"] == time(9, 0) and ev["end_time"] == time(13, 0) and ev["all_day"] is False
    assert ev["title"] == "JRC ESPR methodology workshop: Method for the identification and tracking of substances of concern"
    # Stable identity: the same URL always maps to the same event.
    assert ev["external_id"] == jrc_workshop_event(row, date(2026, 10, 30))["external_id"]

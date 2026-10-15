"""Agency consultations carry the dates their own pages label (15 Oct 2026).

GovClipping's contract is publication date, feedback opens, feedback closes on every
consultation. That day 121 ACER, 109 EASA, 140 BEREC and 2 ERA rows had no closing date
and 138 BEREC rows no opening date: the 2 Oct backfill read openings only, missed BEREC's
prose, and neither it nor the page-text job was scheduled, so later rows had neither."""
from __future__ import annotations

from datetime import date

import pytest

from scripts import backfill_agency_consultation_dates as job


def _d(dt):
    return dt.date() if dt else None


@pytest.mark.parametrize("text,opens,closes", [
    # The wordings found on BEREC's pages, each checked against its page.
    ("The public consultation  ran from 11 October to 8 November 2017.", date(2017, 10, 11), date(2017, 11, 8)),
    ("Run from 1 to 30 March 2012 In 2012 BEREC will review", date(2012, 3, 1), date(2012, 3, 30)),
    ("Run from 14May to 3 June 2013 On 14 May 2013 BEREC launched", date(2013, 5, 14), date(2013, 6, 3)),
    ("The public consultation will run from 16 of March until 21 of April 2021", date(2021, 3, 16), date(2021, 4, 21)),
    ("was open from Wednesday, 12 December 2018, at 14:00 CET to Friday, 18 January 2019, at 17:00 CET",
     date(2018, 12, 12), date(2019, 1, 18)),
    ("will run from 6 June 14:00 (CET) to 18 July 14:00 (CET) 2016", date(2016, 6, 6), date(2016, 7, 18)),
    ("Run from 9 December 2010 to 13 January 2011", date(2010, 12, 9), date(2011, 1, 13)),
    ("consultations in the period between 7 June and 5 July 2017 (17:00 CET)", date(2017, 6, 7), date(2017, 7, 5)),
    # An opening without a year in a later month than the closing is the year before.
    ("The consultation ran from 16 December to 20 January 2012.", date(2011, 12, 16), date(2012, 1, 20)),
    # A deadline alone is the closing date; the opening stays unknown.
    ("Please provide your input to x by 15 July 2019 17:00 CET", None, date(2019, 7, 15)),
    # No year anywhere: nothing is guessed.
    ("The public consultation ran from 31 October to 28 November.", None, None),
    ("projects from 2021 and beyond", None, None),
    # A plenary meeting is not the consultation period.
    ("During its 39th plenary meeting (13-14 June 2019, Ghent) the Board approved it", None, None),
])
def test_berec_reads_its_one_sentence(text, opens, closes):
    s, e = job.berec_range(text)
    assert (_d(s), _d(e)) == (opens, closes)


@pytest.mark.parametrize("agency,text,closes", [
    ("ACER", "Status Closed Open: 28.06.2024 Close: 16.09.2024 Policy area REMIT", date(2024, 9, 16)),
    ("EASA", "Closing date of consultation 19/08/2024 Extended closing date of consultation 30/09/2024",
     date(2024, 9, 30)),
    ("EASA", "Validity Not superseded Closing date of consultation 08/12/2022 Downloads", date(2022, 12, 8)),
    ("EASA", "Procedure Consultations Deadline for comments 15/05/2018 Downloads", date(2018, 5, 15)),
    ("ERA", "Consultation details Opening date 22 December 2017 Closing date 20 February 2018", date(2018, 2, 20)),
])
def test_each_agency_label_gives_the_closing_date(agency, text, closes):
    assert _d(job._date(text, agency, job.END_PATTERNS)) == closes


def test_only_empty_dates_are_written():
    store = str(job.STORE)
    assert "start_date = coalesce(start_date, :s)" in store and "end_date = coalesce(end_date, :e)" in store


def test_the_page_and_date_jobs_run_after_the_agency_sync_in_that_order():
    from services.sync.source_registry import sources_for_tier
    keys = [s.key for s in sources_for_tier("warm")]
    sync, pages, dates = (keys.index(k) for k in
                          ("agency_consultations", "agency_consultation_text", "agency_consultation_dates"))
    assert sync < pages < dates

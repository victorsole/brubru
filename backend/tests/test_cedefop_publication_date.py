"""A Cedefop procedure's publication date is never later than its own deadline (16 Oct 2026).

API audit, step 2: 92 Cedefop procedures were served with an "Official Publication Date"
after their closing date: 77 the site-migration stamp (27/11/2009), 15 with day and month
swapped. The page's own Official Journal sentence gives the real day for 9 of them; the
others carry no date rather than a wrong or inferred one.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.scrapers import agency_procurement as ap  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "cedefop"
NOW = datetime(2026, 10, 16, tzinfo=timezone.utc)
D = lambda y, m, d: datetime(y, m, d, tzinfo=timezone.utc)  # noqa: E731

OJ = ("This call has been published in the Supplement to the Official Journal of the "
      "European Union 2014/S 156-279480 of 16/08/2014.")


@pytest.mark.parametrize("page_date, deadline, description, expected", [
    ("27/04/2026", D(2026, 9, 1), [], D(2026, 4, 27)),            # ordinary: kept
    ("01/10/2014", D(2014, 10, 1), [], D(2014, 10, 1)),           # same day as closing: kept
    ("27/11/2009", D(2008, 1, 16), [], None),                     # migration stamp, no OJ
    ("27/11/2009", D(2026, 1, 1), [], None),                      # the stamp is never a date
    ("27/05/2015", D(2014, 10, 1), [OJ], D(2014, 8, 16)),         # after deadline: OJ day
    ("09/12/2009", D(2009, 10, 23), [], None),                    # award date, no OJ: empty
    ("27/11/2009", D(2006, 10, 16),
     ["published in the Official Journal of the European Communities 2006/S 168-179564 "
      "of 05/09/2006."], D(2006, 9, 5)),
    ("27/11/2009", D(2006, 11, 1),
     ["Official Journal of the European Communities 2006/S 177-187996 dated 16.09.2006."],
     D(2006, 9, 16)),
    ("27/05/2015", D(2014, 10, 1),                                # an OJ day after the deadline
     ["Official Journal of the European Union 2015/S 1-1 of 27/05/2015."], None),
    ("", None, [OJ], D(2014, 8, 16)),                             # no page date: the OJ day
    ("27/04/2026", None, [], D(2026, 4, 27)),                     # no deadline to check against
])
def test_publication_date_is_never_after_the_deadline(page_date, deadline, description, expected):
    detail = {"Official Publication Date": page_date, "description": description}
    assert ap._cedefop_published(detail, deadline) == expected


def test_item_carries_the_vetted_date_in_document_date_and_body():
    row = {"title": "Travel Agency Services", "url": "https://x/travel", "reference": "AO/011/14",
           "closing": D(2014, 10, 1), "status_raw": "Completed"}
    detail = {"Procurement type": "Call for tenders", "Official Publication Date": "27/05/2015",
              "Closing date": "01/10/2014", "description": [OJ], "documents": []}
    item = ap._cedefop_item(row, detail, NOW)
    assert item.document_date == D(2014, 8, 16)
    assert "Official publication date: 2014-08-16" in item.body_txt
    assert item.extras["deadline"] == D(2014, 10, 1)


def test_item_with_a_rejected_date_and_no_oj_sends_no_date():
    row = {"title": "Loans", "url": "https://x/loans", "reference": "AO/016/09",
           "closing": D(2009, 10, 23), "status_raw": "Completed"}
    detail = {"Procurement type": "Call for tenders", "Official Publication Date": "09/12/2009",
              "Closing date": "23/10/2009", "description": ["Deadline: 23 October 2009"], "documents": []}
    item = ap._cedefop_item(row, detail, NOW)
    assert item.document_date is None
    assert "Official publication date" not in item.body_txt


def test_the_2009_fixture_page_yields_its_oj_day(monkeypatch):
    """The saved 2009 page states 'Official Journal ... 2009/S 81-115981 of 28.04.2009'."""
    monkeypatch.setattr(ap, "_get_ok", lambda url: (FIX / "detail_downloads_2009.html").read_text())
    detail = ap._cedefop_detail("https://x/2009")
    closing = ap._parse_date(detail.get("Closing date", ""))
    got = ap._cedefop_published(detail, closing)
    assert got is not None and got <= (closing or got)
    page_date = ap._parse_date(detail.get("Official Publication Date", ""))
    if page_date == ap._CEDEFOP_MIGRATION_STAMP or (closing and page_date and page_date > closing):
        assert got == D(2009, 4, 28)

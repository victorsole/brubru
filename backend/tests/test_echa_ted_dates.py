"""An ECHA procedure without a portal notice is dated by the TED notice its page links
(16 Oct 2026).

API audit, step 2 (ECHA, 106 tenders read in full): 97 carried no date. ECHA publishes
none; the 30 Sep rule took the linked Funding & Tenders notice's date and only 9 pages
link one. 79 pages cite a TED notice (an OJ S publication, with a date TED's API serves
for notices from 2016 on).
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.scrapers import agency_procurement as ap  # noqa: E402

NOW = datetime(2026, 10, 16, tzinfo=timezone.utc)
D = lambda y, m, d: datetime(y, m, d, tzinfo=timezone.utc)  # noqa: E731
TED = "http://ted.europa.eu/udl?uri=TED:NOTICE:{n}:TEXT:{l}:HTML"


def _fake_ted(answers: dict):
    """TED's search API: {number: 'YYYY-MM-DD+02:00'} for the numbers it indexes."""
    calls = []

    def post(url, json=None, headers=None, timeout=None):
        calls.append(json["query"])
        asked = json["query"].split("(")[1].rstrip(")").split()
        notices = [{"publication-number": n, "publication-date": answers[n]} for n in asked if n in answers]
        return SimpleNamespace(status_code=200, raise_for_status=lambda: None,
                               json=lambda: {"notices": notices, "totalNoticeCount": len(notices)})
    return post, calls


def setup_function():
    ap._TED_DATE_CACHE.clear()


def test_numbers_are_read_from_ted_links_once_each():
    links = [TED.format(n="255572-2015", l="BG"), TED.format(n="255572-2015", l="EN"),
             "https://ted.europa.eu/en/notice/-/detail/224671-2023", "https://echa.europa.eu/x"]
    assert ap._ted_notice_numbers(links) == ["255572-2015", "224671-2023"]


def test_dates_come_from_ted_in_one_batched_call(monkeypatch):
    post, calls = _fake_ted({"224671-2023": "2023-04-17+02:00", "249771-2023": "2023-04-26+02:00"})
    monkeypatch.setattr(ap.requests, "post", post)
    got = ap._ted_publication_dates(["224671-2023", "255572-2015", "249771-2023"])
    assert got == {"224671-2023": D(2023, 4, 17), "249771-2023": D(2023, 4, 26)}   # 2015: not indexed
    assert len(calls) == 1 and "publication-number IN (224671-2023 255572-2015 249771-2023)" == calls[0]
    ap._ted_publication_dates(["224671-2023"])
    assert len(calls) == 1                                                      # cached


def test_the_earliest_notice_before_the_deadline_dates_the_procedure(monkeypatch):
    post, _ = _fake_ted({"100-2023": "2023-04-17+02:00", "200-2023": "2023-05-02+02:00",
                         "300-2023": "2023-09-01+02:00"})
    monkeypatch.setattr(ap.requests, "post", post)
    links = [TED.format(n=n, l="EN") for n in ("300-2023", "200-2023", "100-2023")]
    assert ap._ted_published(links, D(2023, 6, 1)) == ("100-2023", D(2023, 4, 17))  # the award (Sep) is out
    assert ap._ted_published(links, D(2023, 1, 1)) == (None, None)                 # nothing before it
    assert ap._ted_published([], None) == (None, None)


def _row(**kw):
    row = {"title": "Security and Reception Services", "url": "https://echa.europa.eu/-/x",
           "reference": "ECHA/2023/103", "kind": "Open", "current": False, "deadline": D(2023, 6, 29)}
    row.update(kw)
    return row


def test_item_takes_the_ted_date_when_no_portal_notice_is_linked(monkeypatch):
    post, _ = _fake_ted({"224671-2023": "2023-04-17+02:00"})
    monkeypatch.setattr(ap.requests, "post", post)
    detail = {"description": ["d"], "links": [TED.format(n="224671-2023", l="EN")], "notices": [],
              "documents": []}
    item = ap._echa_item(_row(), detail, NOW)
    assert item.document_date == D(2023, 4, 17)
    assert "TED notice: 224671-2023" in item.body_txt and "Notice published: 2023-04-17" in item.body_txt


def test_portal_notice_still_wins_and_ted_is_not_asked(monkeypatch):
    monkeypatch.setattr(ap, "_ft_notice_date", lambda n: D(2023, 4, 20))
    post, calls = _fake_ted({})
    monkeypatch.setattr(ap.requests, "post", post)
    detail = {"description": [], "links": [TED.format(n="224671-2023", l="EN")],
              "notices": ["abc-CN"], "documents": []}
    item = ap._echa_item(_row(), detail, NOW)
    assert item.document_date == D(2023, 4, 20) and not calls and "TED notice" not in item.body_txt


def test_a_ted_failure_leaves_the_item_undated_not_broken(monkeypatch):
    def boom(*a, **k):
        raise ap.requests.ConnectionError("ted down")
    monkeypatch.setattr(ap.requests, "post", boom)
    detail = {"description": [], "links": [TED.format(n="224671-2023", l="EN")], "notices": [],
              "documents": []}
    item = ap._echa_item(_row(), detail, NOW)
    assert item.document_date is None and item.body_txt

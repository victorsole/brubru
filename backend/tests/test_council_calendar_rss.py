"""Council calendar from the Council's own RSS feeds (24 Sep 2026).

consilium blocks the Railway address for its HTML pages, so council_calendar
failed every production run. The per-configuration meetings feeds are plain XML.
"""
from datetime import date, timedelta

import services.scrapers.council_calendar_scraper as cc


def test_rss_link_and_html_href_give_the_same_id():
    a = cc._event_from("Competitiveness Council",
                       "https://www.consilium.europa.eu/en/meetings/compet/2026/12/03/")
    b = cc._event_from("Competitiveness Council, 3 December 2026", "/en/meetings/compet/2026/12/03/")
    assert a["external_id"] == b["external_id"] == "council_en_meetings_compet_2026_12_03"


def test_a_meeting_spanning_two_months_ends_in_the_second():
    e = cc._event_from("Informal meeting of health ministers", "/en/meetings/epsco/2026/09/30-01/")
    assert (e["start_date"], e["end_date"]) == (date(2026, 9, 30), date(2026, 10, 1))
    e = cc._event_from("Summit", "/en/meetings/euco/2026/12/31-01/")
    assert e["end_date"] == date(2027, 1, 1)


def _feed(*items):
    body = "".join(f"<item><title>{t}</title><link>{l}</link></item>" for t, l in items)
    return f'<?xml version="1.0"?><rss version="2.0"><channel>{body}</channel></rss>'.encode()


def test_rss_tier_parses_feeds_and_keeps_the_window(monkeypatch):
    soon = date.today() + timedelta(days=10)
    far = date.today() + timedelta(days=400)
    old = date.today() - timedelta(days=90)
    link = lambda d, cfg="compet": f"https://www.consilium.europa.eu/en/meetings/{cfg}/{d:%Y/%m/%d}/"

    class Resp:
        def __init__(self, content, status=200):
            self.content, self.status_code = content, status

    def get(url, **kw):
        if url.endswith("cat=compet"):
            return Resp(_feed(("Competitiveness Council", link(soon)),
                              ("Competitiveness Council", link(far)),
                              ("Competitiveness Council", link(old))))
        if url.endswith("cat=euco"):
            return Resp(_feed(("European Council", link(soon, "euco"))))
        return Resp(b"", 404)

    import requests
    monkeypatch.setattr(requests, "get", get)
    out = cc.CouncilCalendarScraper()._fetch_rss_meetings(months_ahead=6)
    assert sorted(e["title"] for e in out) == ["Competitiveness Council", "European Council"]
    assert next(e for e in out if e["title"] == "European Council")["institution"] == "EUROPEAN_COUNCIL"


def test_no_feed_answering_returns_empty_so_the_caller_falls_back(monkeypatch):
    import requests

    class Resp:
        status_code, content = 503, b""
    monkeypatch.setattr(requests, "get", lambda url, **kw: Resp())
    assert cc.CouncilCalendarScraper()._fetch_rss_meetings() == []

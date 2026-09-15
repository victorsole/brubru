"""Regression tests for the 15 Sep 2026 institutional news ingestion defects.

P-4  EP press room parsed 0 items on every run (different markup from committee pages).
C    Council listing is WAF-walled (403); a block page parsed to 0 and read as "quiet".
D    One Commission story stored twice under presscorner + DG-site URLs.
S    stamp_fetched ran before pending INSERTs were flushed, so new rows had no stamp.
"""
from datetime import date
from types import SimpleNamespace

import pytest

from services.scrapers import bespoke_news_scraper as bns
from services.scrapers.ep_news_scraper import canonical_ep_url, parse_ep
from services.news import same_story
from services.news.fetch_anchor import stamp_fetched


PRESS_ROOM_CARD = """
<article class="ep_gridcolumn ep-m_product ep-layout_linkmode" data-view1200="8">
  <div class="ep_gridcolumn-content">
    <h3 class="ep-a_heading ep-layout_level2">
      <div class="ep_title">
        <a href="https://www.europarl.europa.eu/news/en/press-room/20260910IPR47441/ep-today" title="Read more">
          <div class="ep-p_text"><span class="ep_name">EP TODAY</span><span class="ep_icon">&nbsp;</span></div>
        </a>
      </div>
      <div class="ep_subtitle"><div class="ep-p_text ep-layout_date"><span class="ep_name">
        <time itemprop="datePublished" datetime="2026-09-15T08:30:00">Today</time>
      </span></div></div>
    </h3>
    <div class="ep-a_text" data-visibility480="false"><p>Tuesday 15 September</p></div>
  </div>
</article>
<article class="ep_gridcolumn ep-m_product ep-layout_linkmode">
  <div class="ep_title">
    <a href="https://www.europarl.europa.eu/news/en/press-room/20260914IPR47510/european-parliament-to-establish-an-antenna-office-in-ottawa" title="Read more">
      <div class="ep-p_text"><span class="ep_name">European Parliament to establish an antenna office in Ottawa</span></div>
    </a>
  </div>
</article>
"""

COMMITTEE_ITEM = """
<h3 class="es_document-title es_title-h3 mb-0 a-i">
  <a href="https://www.europarl.europa.eu/news/en/press-room/20260911IPR47465/" class="t-y" target="">
    <span class="t-item">The impact of social media on young people: press conference</span>
  </a>
</h3>
"""


class TestEpPressRoom:
    def test_press_room_cards_parse(self):
        items = parse_ep(PRESS_ROOM_CARD)
        assert [i["title"] for i in items] == [
            "EP TODAY", "European Parliament to establish an antenna office in Ottawa"]

    def test_card_publication_date_beats_id_date(self):
        ep_today = parse_ep(PRESS_ROOM_CARD)[0]
        # ID says 10 Sep (document created); the card says published 15 Sep.
        assert ep_today["news_date"] == date(2026, 9, 15)
        assert ep_today["date_source"] == "published"
        assert ep_today["summary"] == "Tuesday 15 September"

    def test_card_without_time_falls_back_to_id_date(self):
        ottawa = parse_ep(PRESS_ROOM_CARD)[1]
        assert ottawa["news_date"] == date(2026, 9, 14)
        assert ottawa["date_source"] == "id"

    def test_slugged_and_bare_urls_share_one_identity(self):
        slugged = parse_ep(PRESS_ROOM_CARD)[1]["source_url"]
        assert slugged == "https://www.europarl.europa.eu/news/en/press-room/20260914IPR47510/"
        assert canonical_ep_url(
            "https://www.europarl.europa.eu/news/en/press-room/20260911IPR47465/") == \
            "https://www.europarl.europa.eu/news/en/press-room/20260911IPR47465/"

    def test_committee_markup_still_parses(self):
        items = parse_ep(COMMITTEE_ITEM)
        assert len(items) == 1
        assert items[0]["news_date"] == date(2026, 9, 11)
        assert items[0]["date_source"] == "id"

    def test_non_press_room_urls_untouched(self):
        u = "https://www.europarl.europa.eu/delegations/en/d-us/documents/communiques/123"
        assert canonical_ep_url(u) == u


class _FakeExisting(SimpleNamespace):
    pass


class TestEpUpsertDateRule:
    """An ID date from a committee page must never overwrite a card publication date."""

    def _run(self, existing_date, item):
        import scripts.sync_ep_news as sync

        existing = _FakeExisting(title=item["title"], source_url=item["source_url"],
                                 item_type="press", news_date=existing_date,
                                 summary="x", policy_areas=[])

        class Q:
            def filter(self, *a, **k): return self
            def first(self): return existing

        db = SimpleNamespace(query=lambda *a, **k: Q())
        return sync._upsert(db, item), existing

    def _item(self, nd, src):
        return {"entry_key": "k", "title": "T", "source_url": "u", "item_type": "press",
                "news_date": nd, "date_source": src}

    def test_id_date_does_not_overwrite(self):
        res, row = self._run(date(2026, 9, 15), self._item(date(2026, 9, 10), "id"))
        assert row.news_date == date(2026, 9, 15) and res == "skipped"

    def test_published_date_overwrites(self):
        res, row = self._run(date(2026, 9, 10), self._item(date(2026, 9, 15), "published"))
        assert row.news_date == date(2026, 9, 15) and res == "updated"


COUNCIL_RSS = b"""<?xml version="1.0" encoding="utf-8"?><rss xmlns:a10="http://www.w3.org/2005/Atom" version="2.0"><channel>
<item><guid isPermaLink="false">150481</guid><link>https://www.consilium.europa.eu/en/press/press-releases/2026/09/15/kyriakos-pierrakakis-president-of-the-eurogroup-to-visit-germany/</link><title>Kyriakos Pierrakakis, President of the Eurogroup, to visit Germany</title><description>Travelling to Berlin.</description><a10:updated>2026-09-15T08:00:00Z</a10:updated></item>
<item><link>https://www.consilium.europa.eu/en/meetings/eurogroup/2026/09/18/</link><title>Eurogroup meeting</title></item>
</channel></rss>"""


class TestCouncil:
    cfg = bns.BESPOKE_SOURCES[0]

    def test_council_config_is_required_and_has_rss(self):
        assert self.cfg["institution"] == "COUNCIL"
        assert self.cfg["required"] is True
        assert self.cfg["rss"].startswith("https://www.consilium.europa.eu/")

    def test_rss_items_match_listing_identity(self):
        items = bns.parse_rss_items(COUNCIL_RSS, self.cfg)
        assert len(items) == 1  # the meetings link does not match link_re
        it = items[0]
        assert it["entry_key"] == ("https://www.consilium.europa.eu/en/press/press-releases/"
                                   "2026/09/15/kyriakos-pierrakakis-president-of-the-eurogroup-to-visit-germany")
        assert it["news_date"] == date(2026, 9, 15)
        assert it["title"].startswith("Kyriakos Pierrakakis")
        assert it["summary"] == "Travelling to Berlin."
        assert it["institution"] == "COUNCIL"

    def test_malformed_rss_is_empty_not_an_exception(self):
        assert bns.parse_rss_items(b"<html>403</html", self.cfg) == []

    def test_http_error_status_is_unreachable_not_empty(self, monkeypatch):
        monkeypatch.setattr(bns, "_fetch_rss", lambda cfg: [])
        fetcher = SimpleNamespace(fetch=lambda *a, **k: SimpleNamespace(
            html="<html><body>Access denied</body></html>" * 20, nav_status=403))
        with pytest.raises(bns.BespokeFetchError, match="HTTP 403"):
            bns.scrape_bespoke(self.cfg, fetcher)

    def test_error_status_with_a_real_listing_is_kept(self, monkeypatch):
        # ECHA: first response 403, challenge clears, listing renders.
        monkeypatch.setattr(bns, "_fetch_rss", lambda cfg: [])
        page = ('<a href="https://www.consilium.europa.eu/en/press/press-releases/2026/09/15/'
                'some-long-enough-council-press-release-slug/">Some long enough Council press release title</a>')
        fetcher = SimpleNamespace(fetch=lambda *a, **k: SimpleNamespace(html=page, nav_status=403))
        assert len(bns.scrape_bespoke(self.cfg, fetcher)) == 1

    def test_rss_success_skips_the_browser(self, monkeypatch):
        monkeypatch.setattr(bns, "_fetch_rss", lambda cfg: [{"entry_key": "x"}])

        def boom(*a, **k):
            raise AssertionError("browser must not be used when the feed answered")
        assert bns.scrape_bespoke(self.cfg, SimpleNamespace(fetch=boom)) == [{"entry_key": "x"}]


class TestSameStory:
    def test_normalise_ignores_case_punctuation_and_symbols(self):
        a = "Commission approves €52 million Romanian State aid for cattle farmers"
        b = "Commission approves 52 million Romanian State-aid for cattle farmers."
        assert same_story.normalise_title(a) == same_story.normalise_title(b)

    def test_short_or_undated_titles_never_match(self):
        assert not same_story.is_matchable("EP TODAY", date(2026, 9, 15))
        assert not same_story.is_matchable("A long enough title for a real press release", None)
        assert same_story.is_matchable("A long enough title for a real press release", date(2026, 9, 15))

    def test_find_same_story_skips_the_query_when_not_matchable(self):
        db = SimpleNamespace(flush=lambda: (_ for _ in ()).throw(AssertionError("no query")))
        assert same_story.find_same_story(db, institution="COMMISSION", title="EP TODAY",
                                          news_date=date(2026, 9, 15)) is None


def test_stamp_fetched_flushes_before_update():
    calls = []
    db = SimpleNamespace(flush=lambda: calls.append("flush"),
                         execute=lambda *a, **k: (calls.append("update"),
                                                  SimpleNamespace(rowcount=2))[1])
    assert stamp_fetched(db, ["a", "b"]) == 2
    assert calls == ["flush", "update"]

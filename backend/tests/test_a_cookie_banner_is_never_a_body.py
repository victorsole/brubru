"""A cookie banner with nothing after it is never stored as a body.

18 Oct 2026: 98 of 135 Court of Auditors rows in economy_items held the site's consent
banner as their body ("Skip Navigation Links News / Skip to content / ... / We use cookies
... / Refuse / Accept / Title modal"), and /api/v2/news/all served it to GovClipping in
place of the article. The existing guard looked at how a page OPENS, and "Skip Navigation
Links" was new, so the banner passed as text; the upsert's "longer body wins" rule then let
a 334-character banner replace a 307-character one on 77 rows.

The detector judges what is LEFT once the banner's own lines are removed, and needs a
banner sentence to be present. It was run on every stored body under 2,000 characters that
mentions cookies (1,303 outside ECA): no false hit; all 95 ECA banners caught.
"""
import importlib
import pathlib
import sys
from types import SimpleNamespace

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from services.news.rendered_article import looks_like_consent_banner_only  # noqa: E402

ECA_BANNER = ("Skip Navigation Links News\nSkip to content\nSkip to search\nSkip to navigation\n"
              "We use cookies or similar technologies to improve your browsing experience on our website. "
              "This includes remembering your language choice.\nYou can read more information on our "
              "cookie policy by clicking on this link:\nCookie policy\n.\nRefuse\nAccept\nTitle modal\n")
ECA_REPORTS_BANNER = ECA_BANNER.replace("Links News", "Links MultipleReports")
ARTICLE = ("€17 billion of support was made available between 2014 and 2020 to strengthen the innovation "
           "and growth potential of EU businesses, according to a report published today by the European "
           "Court of Auditors. Funding for close-to-market research did not systematically target projects "
           "with the highest commercial or innovation potential.")


class TestBannersAreRecognised:
    @pytest.mark.parametrize("text", [ECA_BANNER, ECA_REPORTS_BANNER, ". " + ECA_BANNER])
    def test_the_court_of_auditors_banner(self, text):
        assert looks_like_consent_banner_only(text)


class TestRealTextIsKept:
    @pytest.mark.parametrize("text", [
        ARTICLE,
        ECA_BANNER + ARTICLE,                               # banner FOLLOWED by the article
        "New EDPS guidance on cookie walls.\n" + ARTICLE,
        # A short real notice whose footer links to "Cookies" (EU Funding & Tenders news).
        "EDF Submission forms: new version of Annex 6 (v1.3) solving validation/export issues now available here."
        "\n\n© 2026 European Commission|\nAbout\n|\nAccessibility\n|\nFree text search\n|\nIT Helpdesk\n|\nCookies\n|",
        # A trade mark named after cookies (EUIPO).
        "Trade mark: The Original* cookies\nOffice: EM (EUIPO)\nApplication number: 004195558\nStatus: Registered",
        "EDPS fines a website for cookie banners\nThe EDPS today issued a decision against an EU agency whose "
        "website placed analytics cookies without consent, ordering compliance within 30 days.",
        "", None,
    ])
    def test_not_a_banner(self, text):
        assert not looks_like_consent_banner_only(text)


class TestTheEconomySyncSendsNoBannerBody:
    """The sync's own per-item guard, called as the run calls it."""

    @pytest.fixture(scope="class")
    def sync(self):
        return importlib.import_module("scripts.sync_economy")

    def test_a_banner_body_goes_out_as_null(self, sync):
        it = SimpleNamespace(body_txt=ECA_BANNER, body_html="<main>banner</main>")
        sync._drop_furniture_bodies(it)
        assert it.body_txt is None and it.body_html is None

    def test_a_real_body_goes_out_untouched(self, sync):
        it = SimpleNamespace(body_txt=ARTICLE, body_html="<p>article</p>")
        sync._drop_furniture_bodies(it)
        assert it.body_txt == ARTICLE and it.body_html == "<p>article</p>"

    def test_the_guard_runs_on_every_item_of_a_run(self, sync):
        import inspect
        src = inspect.getsource(sync)
        assert "_reject_future_news_date(it)\n            _drop_furniture_bodies(it)" in src

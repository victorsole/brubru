"""A site's header, menus and footer are never a news item's body, nor the file it means.

18 Oct 2026, CPVO:
1. A short news page links no file in its content, but the site footer links the newsletter
   privacy statement on every page. The fetcher followed the first PDF anywhere in the page,
   the longest PDF won, and five news items stored that 11,394-character notice as their
   article (eight more were about to). Files are now taken from the content only.
2. The browser route reads the whole page, so a two-sentence announcement came back padded
   past 200 characters with the footer's newsletter form, and an event page holding only
   "title / date / online / Italy" with the main menu and breadcrumb. The page's own
   <nav>/<header> lines are cut from the top and its <footer> from the bottom, then judged.

The page below is the live CPVO markup of 18 Oct 2026, trimmed; the text is what the
browser returned for it.
"""
import importlib
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
F = importlib.import_module("scripts.fetch_institutional_news_bodies")
from services.news.page_widgets import clean_text  # noqa: E402
from services.news.rendered_article import strip_page_furniture  # noqa: E402

PAGE = """<html><body>
<header><nav aria-label="Main navigation"><h2>Main navigation</h2><ul><li>Home</li><li>About Us</li>
<li>News and Events</li><li>FAQ</li><li>Create an account</li></ul></nav></header>
<main><div class="page-header"><nav aria-labelledby="system-breadcrumb"><h2>Breadcrumb</h2>
<ol><li>Home</li><li>News &amp; Events</li><li>News</li><li>Current: Official Publications 5.2026</li></ol></nav></div>
<h1>Official Publications 5.2026</h1>%s
<div class="block-webtools-social-buttons"><h2>Share this</h2></div></main>
<footer class="l-footer"><div class="block-subscribe-newsletter"><h2>Subscription to CPVO newsletter</h2>
<p>Do you want to know more about CPVO's news and activities?</p>
<a href="/sites/default/files/privacy_statement_newsletter-updated.pdf">Privacy Statement</a></div>
<div><a href="/sites/default/files/documents/lex/Ombudsman_European_Code.pdf">Code</a></div></footer>
</body></html>"""
ANNOUNCEMENT = ("<p>15 October 2026</p><p>Official Announcement</p><p>The Official Gazette of the CPVO "
                "has been published.</p><p>You may download the gazette from the Gazette page.</p>")
EVENT = "<p>05 May 2022</p><p>online</p><p>Italy</p>"
RENDERED = ("Main navigation\nHome\nAbout Us\nNews and Events\nFAQ\nCreate an account\nBreadcrumb\nHOME\n"
            " NEWS & EVENTS\n NEWS\nCURRENT:\n OFFICIAL PUBLICATIONS 5.2026\nOfficial Publications 5.2026\n"
            "15 October 2026\nOFFICIAL ANNOUNCEMENT\nImage :\n\nThe Official Gazette of the CPVO has been "
            "published.\n\nYou may download the gazette from the Gazette page.\n\nShare this\nFacebook\nTwitter\n"
            "LinkedIn\nE-mail\nSubscription to CPVO newsletter\n\nDo you want to know more about CPVO's news "
            "and activities? You can sign up to CPVO's digital newsletter which will be sent to you by email "
            "every month.\n\nDisclaimer Subscribe\nManage your newsletter subscriptions\n CPVO Press Releases "
            "and Communications (daily)\nPrivacy Statement\nI am looking for\n- Choose -\nThe basic regulation\n"
            "Submission dates\nTechnical protocols\nOnline forms\nCPVO vacancies\nSearch")


def test_a_footer_file_is_not_followed(monkeypatch):
    asked = []
    monkeypatch.setattr(F, "_read", lambda link, *a, **k: asked.append(link) or b"")
    F._follow_to_pdf(PAGE % ANNOUNCEMENT, "https://cpvo.europa.eu/en/news-and-events/news/official-publications-52026")
    assert asked == []


def test_a_file_in_the_content_is_still_followed(monkeypatch):
    asked = []
    monkeypatch.setattr(F, "_read", lambda link, *a, **k: asked.append(link) or b"")
    page = PAGE % (ANNOUNCEMENT + '<p><a href="/sites/default/files/gazette_5_2026.pdf">Gazette</a></p>')
    F._follow_to_pdf(page, "https://cpvo.europa.eu/en/news-and-events/news/official-publications-52026")
    assert asked == ["https://cpvo.europa.eu/sites/default/files/gazette_5_2026.pdf"]


def test_the_browser_text_loses_menus_and_footer_but_keeps_the_headline():
    out = F._cut_rendered_chrome(RENDERED, PAGE % ANNOUNCEMENT)
    assert "Main navigation" not in out and "Create an account" not in out and "HOME" not in out
    assert "Official Publications 5.2026" in out and "You may download the gazette" in out
    assert "Subscription to CPVO newsletter" not in out and "I am looking for" not in out


def test_a_page_of_a_title_a_date_and_a_place_is_still_too_short():
    rendered = RENDERED.replace("15 October 2026\nOFFICIAL ANNOUNCEMENT\nImage :\n\nThe Official Gazette of the "
                                "CPVO has been published.\n\nYou may download the gazette from the Gazette page.",
                                "05 May 2022\nonline\nItaly\nImage :")
    out = strip_page_furniture(F._cut_rendered_chrome(rendered, PAGE % EVENT))
    assert len(clean_text(out)) < 200, out


def test_without_markup_the_text_is_untouched():
    assert F._cut_rendered_chrome(RENDERED, None) == RENDERED
    assert F._cut_rendered_chrome(RENDERED, "<html><body><p>x</p></body></html>") == RENDERED


def test_a_bare_share_this_line_is_widget_chrome():
    assert clean_text("Headline\nText of the item.\nShare this\nFacebook") == "Headline\nText of the item."


def test_a_sidebar_download_is_still_followed(monkeypatch):
    # Agency record pages put the item's own file in a sidebar or an in-article footer.
    asked = []
    monkeypatch.setattr(F, "_read", lambda link, *a, **k: asked.append(link) or b"")
    page = PAGE.replace("</main>", '<aside><a href="/files/report_2026.pdf">Download</a></aside>'
                                    '<article><footer><a href="/files/annex.pdf">Annex</a></footer></article></main>')
    F._follow_to_pdf(page % ANNOUNCEMENT, "https://cpvo.europa.eu/en/x")
    assert asked == ["https://cpvo.europa.eu/files/report_2026.pdf", "https://cpvo.europa.eu/files/annex.pdf"]


def test_an_article_that_names_the_footer_words_is_not_cut():
    # The footer's first line is matched as a whole line followed by its second, never as
    # words inside the article.
    html = ("<html><body><main><h1>Budget agreement reached</h1></main><footer><p>European Commission</p>"
            "<p>Directorate-General for Budget, Rue de la Loi 200</p></footer></body></html>")
    text = ("Budget agreement reached\nThe European Commission welcomed the deal.\n" + "Detail of the deal. " * 20 +
            "\nEuropean Commission\nPress contacts follow below.")
    assert F._cut_rendered_chrome(text, html) == text

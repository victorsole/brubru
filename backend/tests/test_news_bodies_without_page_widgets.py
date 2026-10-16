"""News bodies carry the article, not the page around it (16 Oct 2026).

509 of 512 Parliament press releases held "Share this page: Facebook X LinkedIn WhatsApp
... Sign up for mail updates PDF version"; 167 body_html held a script or an onclick; 169
Court of Justice releases served a PDF link as body_html; 51 Council titles were rebuilt
from the address; 36 Commission articles were refused because the reader dropped the
page title with the header."""
from __future__ import annotations

from types import SimpleNamespace

from api.v2.news import _news_body
from scripts.backfill_news_titles_from_page import page_title
from services.news.page_widgets import clean_html, clean_text
from services.scrapers.economy_common import extract_html

EP_HTML = """<article><h1>Press briefing on next week's plenary session</h1>
<div class="ep-a_share ep-layout_socialnetwok"><div class="ep_share"><h2 class="ep_title"><span class="ep_name">Share this page:</span></h2>
<ul><li><a href="https://www.facebook.com/share.php?u=https://www.europarl.europa.eu/x" onclick="window.open(this.href)">Facebook</a></li>
<li><a href="https://x.com/intent/tweet?text=x">X</a></li></ul></div>
<div class="ep_links"><a href="/subscription/en">Sign up for mail updates</a><a href="/pdfs/x.pdf">PDF version</a></div></div>
<p onclick="track()">Spokespersons for Parliament will hold a briefing on the 19-22 October plenary session.</p>
<script>var tracking = 1;</script></article>"""


def test_share_widgets_and_scripts_leave_the_html_and_the_text():
    h = clean_html(EP_HTML)
    assert "Share this page" not in h and "facebook.com" not in h and "Sign up for mail" not in h
    assert "<script" not in h and "onclick" not in h
    assert "Spokespersons for Parliament will hold a briefing" in h
    t = clean_text("Press briefing\nPress Releases\nPlenary session\n6 hours ago\nShare this page:\nFacebook\nX\n"
                   "LinkedIn\nWhatsApp\nSpokespersons will hold a briefing.\nSign up for mail updates\nPDF version")
    assert t == "Press briefing\nPress Releases\nPlenary session\nSpokespersons will hold a briefing."
    plain = "<p>An article with no widget.</p>"
    assert clean_html(plain) is plain


def test_the_page_title_is_kept_when_the_header_goes():
    page = ("<html><body><header class='ecl-page-header'><h1>EU tests reveal compliance issues in safety footwear</h1>"
            "</header><main><p>" + "Safety shoes are a basic line of defence in many workplaces. " * 8 + "</p></main></body></html>")
    txt, html = extract_html(page)
    assert txt.startswith("EU tests reveal compliance issues in safety footwear\n")
    assert html.startswith("<h1>EU tests reveal compliance issues in safety footwear</h1>")


def test_a_pdf_link_stub_is_served_as_the_pdf_text():
    r = SimpleNamespace(body_html='<p>PDF document: <a href="https://curia.europa.eu/x.pdf">https://curia.europa.eu/x.pdf</a></p>',
                        body_txt="Press release No 146/26\n\nJudgment of the General Court in Case T-134/24",
                        title="Judgment", summary=None, document_date=None, public_url="https://curia.europa.eu/x.pdf")
    txt, html = _news_body(r, "Court of Justice of the European Union")
    assert "PDF document:" not in html and "Judgment of the General Court in Case T-134/24" in html
    assert txt.startswith("Press release No 146/26")


def test_a_slug_title_takes_the_pages_own():
    url = "https://www.consilium.europa.eu/en/press/press-releases/2026/07/01/mff-2028-2034-council-backs-simpler-and-more-efficient-rules-for-cohesion-funds/"
    slug_title = "Mff 2028 2034 council backs simpler and more efficient rules for cohesion funds"
    body = "MFF 2028-2034: Council backs simpler and more efficient rules for cohesion funds\nThe Council today ..."
    assert page_title(slug_title, url, body, None) == "MFF 2028-2034: Council backs simpler and more efficient rules for cohesion funds"
    assert page_title("A title the page gave", url, body, None) is None


def test_rows_not_yet_cleaned_are_served_clean():
    r = SimpleNamespace(body_html='<div><a href="https://www.facebook.com/sharer.php?u=x">Facebook</a>'
                                  '<script>t()</script><p onclick="x()">Gender equality index 2026.</p></div>',
                        body_txt="Gender equality index 2026.\nShare\nGmail\nTypepad\nFacebook",
                        title="Index", summary=None, document_date=None, public_url="https://eige.europa.eu/x")
    txt, html = _news_body(r, "EIGE")
    assert txt == "Gender equality index 2026."
    assert "facebook" not in html.lower() and "<script" not in html and "onclick" not in html
    assert "Gender equality index 2026." in html


def test_a_site_menu_after_the_article_goes_and_empty_html_is_rebuilt():
    article = "EDA accelerates defence innovation\n" + "\n".join(
        f"Paragraph {i} of the article, with enough words to be a sentence." for i in range(8))
    menu = "\nPARTICIPATING MEMBER STATES\nFollow us\nSubscribe to our newsletter\nNews and Events\nLatest News\nEvents\nSpotlight\nPodcast\nMultimedia\nPress Office"
    assert clean_text(article + menu) == article
    assert clean_text("Follow us\nshort\nlines\nonly\nhere\nat\nthe\ntop\n" + article).endswith("sentence.")
    r = SimpleNamespace(body_html="<article><p>&lt;body&gt;</p><p>&lt;/body&gt;</p></article>", body_txt=article,
                        title="EDA", summary=None, document_date=None, public_url="https://eda.europa.eu/x")
    txt, html = _news_body(r, "EDA")
    assert "Paragraph 3 of the article" in html and "&lt;body&gt;" not in html

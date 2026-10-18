"""A list of OTHER items under an article is not part of it, and does not make it a listing.

18 Oct 2026:
- The Committee of the Regions ends every article with "Related news": three other items,
  each stamped "Press release". With the article's own "Read more on ..." link that is four
  stamps, so the page read as a listing and 6 CoR articles were stored as nothing.
- Where an article was stored, the list came with it: 408 bodies (EESC 245, CoR 70,
  Commission 54, EASA 34) held other articles' headlines and teasers, which a partner's
  full-text search then matched.
- EU-OSHA's pages have no <main>, so the extractor took the first <article>: a 141-character
  related-publication card. The page's own full-view node holds the highlight, followed by
  "Related publications", eight cards each ending "Read more".

The markup is the live pages', trimmed.
"""
import importlib
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from services.news.page_widgets import clean_html, clean_text  # noqa: E402
from services.scrapers.economy_common import extract_html  # noqa: E402

ARTICLE = ("Several members of the European Committee of the Regions participated in this year's EU Covenant "
           "of Mayors Ceremony in Brussels on 15 October. The event highlighted how cooperation between EU and "
           "local leaders is essential to protect Europeans from price shocks and climate risks. ") * 3

COR_PAGE = f"""<html><body><main>
<h1>Mayors meet with EU leaders in Brussels to advance affordable energy and climate resilience</h1>
<p>News</p><p>16 October 2026</p><p>{ARTICLE}</p>
<p><a href="https://eu-mayors.ec.europa.eu">Read more on the EU Covenant of Mayors website</a></p>
<div><h2>Contact</h2><p>Lauri Ouvinen</p></div>
<div class="field--name-extra-field-newsroom-item-related-news field">
 <div class="c-section-title"><h2><div class="c-section-title__text">Related news</div></h2></div>
 <article><h3>Weakened EU budget would make local communities more vulnerable</h3><p>Press release</p><p>12 October 2026</p></article>
 <article><h3>Regions call for climate resilience</h3><p>Press release</p><p>29 September 2026</p></article>
 <article><h3>Next long-term budget must include local climate action</h3><p>Press release</p><p>1 July 2026</p></article>
</div></main></body></html>"""


def test_the_cor_article_is_extracted_without_its_related_news():
    txt, html = extract_html(COR_PAGE)
    assert txt and "Covenant of Mayors Ceremony" in txt and "Lauri Ouvinen" in txt
    assert "Related news" not in txt and "Weakened EU budget" not in txt
    assert "Related news" not in html and "Weakened EU budget" not in html


def test_a_related_list_is_cut_from_stored_text():
    text = ("Headline of the item\n" + ARTICLE + "\nContact\nPress officer\nRelated news\n"
            "Another item about something else\nNews\n14 October 2026\nA third item\nNews\n2 October 2026")
    out = clean_text(text)
    assert out.endswith("Press officer") and "Another item" not in out


def test_eesc_related_events_is_its_own_metadata_and_stays():
    # "Related events" names the plenary that adopted THIS opinion; the other items start at
    # "Recommended for you".
    text = ("Opinion title\n" + ARTICLE + "\nRelated events\n608th Plenary Session - 23-24 September 2026\n"
            "Work organisation\nRecommended for you\nStrategy on Intergenerational Fairness\nOpinion\n"
            "23 September 2026\nEU enlargement and the climate target\nNews\n18 September 2025")
    out = clean_text(text)
    assert "608th Plenary Session" in out and "Recommended for you" not in out and "Intergenerational" not in out


def test_a_heading_without_a_dated_list_is_kept():
    # Without dates the lines may be the article's own: nothing is cut.
    text = "Headline\n" + ARTICLE + "\nRelated news\nThe Commission will report back in spring."
    assert clean_text(text) == text.strip()


def test_a_related_heading_early_in_the_text_is_kept():
    # A sidebar rendered before the article must not take the article with it.
    text = "Related news\nItem one\n1 October 2026\nItem two\n2 October 2026\n" + ("Body line.\n" * 40)
    assert "Body line." in clean_text(text)


def test_an_unclassed_related_block_is_removed_from_html():
    html = (f"<div><p>{ARTICLE}</p></div><div class='paragraph--type--ela-link-lists-block'><h2>Related news</h2>"
            "<p>ELA supports Member States</p><p>06 October 2026</p><p>Second item</p><p>01 October 2026</p></div>")
    out = clean_html(html)
    assert "Covenant of Mayors" in out and "ELA supports" not in out


OSHA_PAGE = f"""<html><body><header><nav>Main navigation Home Themes</nav></header>
<div class="row"><div id="main" class="col-12">
 <section class="section"><div class="block-system-main-block"><div class="content">
  <div class="node node--type-highlight node--view-mode-full ds-1col">
   <div class="h1-back-wrapper"><h1>Highlights</h1><a href="/en/highlights">Back to highlights</a></div>
   <p>15/10/2026</p><h2>The heart of the matter: new resources on cardiovascular health at work</h2>
   <p>{ARTICLE}</p>
   <div class="field--name-field-related-publications"><h2>Related publications</h2>
   {''.join(f'<article class="node node--type-publication node--view-mode-osha-resources"><p>15/10/2026</p><p>Type: Reports</p><h3>Publication {k} on cardiovascular disease prevention</h3><a href="/en/p{k}">Read more</a></article>' for k in range(8))}
   </div></div></div></div></section></div></div>
<footer>EU-OSHA footer</footer></body></html>"""


def test_a_page_without_main_is_read_from_its_full_view_node():
    txt, _ = extract_html(OSHA_PAGE)
    assert txt and "The heart of the matter" in txt and "Covenant of Mayors" in txt
    assert "Publication 3 on cardiovascular" not in txt and "Read more" not in txt


def test_a_page_with_main_still_reads_main():
    txt, _ = extract_html(COR_PAGE.replace("<main>", "<main><p>Lead paragraph inside main.</p>"))
    assert txt.startswith("Mayors meet with EU leaders") or "Lead paragraph inside main." in txt


def test_an_eu_osha_publication_is_its_download_pdf(monkeypatch):
    # A publication page is a record: summary, "Download in: en", a dated related list. The
    # document is the PDF in its own div.download-pdf block (8 case studies, 15 Oct 2026).
    from types import SimpleNamespace
    osha = importlib.import_module("services.scrapers.economy_eu_osha")
    page = ('<html><body><article class="node node--type-publication node--view-mode-full"><h1>Case study</h1>'
            '<p>Summary.</p><div class="download-pdf no-bg"><a href="/sites/default/files/documents/case_EN.pdf">en</a>'
            '</div></article><footer><a href="/sites/default/files/privacy.pdf">Privacy</a></footer></body></html>')
    asked = []

    def get(url):
        asked.append(url)
        return SimpleNamespace(text=page) if url.endswith("/case-study") else SimpleNamespace(content=b"%PDF-1.7 x")
    monkeypatch.setattr(osha, "http_get", get)
    monkeypatch.setattr(osha, "extract_pdf", lambda raw: "CASE STUDY. Workplace health promotion. " * 20)
    txt, html = osha.publication_pdf("https://osha.europa.eu/en/publications/case-study")
    assert asked[-1] == "https://osha.europa.eu/sites/default/files/documents/case_EN.pdf"
    assert txt.startswith("CASE STUDY") and "case_EN.pdf" in html


def test_a_wrapper_that_starts_with_a_sidebar_list_keeps_the_article():
    # The heading rule climbs to the largest block that BEGINS with the heading; when that
    # block also holds the article it is more than half the page and is left alone.
    html = ("<div><div><h2>Related news</h2><p>Item one</p><p>1 October 2026</p><p>Item two</p>"
            f"<p>2 October 2026</p></div><p>{ARTICLE}</p></div>")
    assert "Covenant of Mayors" in clean_html(html)

"""A card that is one link around everything is titled by the heading inside it.

18 Oct 2026: CPVO's news and event cards are a single <a> around image, type label, <h2>
headline, teaser and date. Both scrapers took the link's whole text: economy_items stored
"Official Announcement Official Publications 5.2026 The Official Gazette of the CPVO has been
published. ... 15 October 2026" on 149 of 149 news and event rows, and the bespoke news
scraper stored the same text when it fitted 220 characters and the URL slug when it did
not. The body fetcher then refused every such page: no page carries that "title".

The card below is the live markup of 18 Oct 2026, trimmed.
"""
import importlib
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
cpvo = importlib.import_module("services.scrapers.economy_cpvo")
bespoke = importlib.import_module("services.scrapers.bespoke_news_scraper")

CARD = """<main><ul><li class="views-row row-1 has-image">
<article class="node-teaser view-mode-teaser node node-news"><div class="row"><div class="group-content columns">
<a class="group-link-wrapper field-group-link" href="/en/news-and-events/news/official-publications-52026">
 <div class="field-name-field-main-image"><article><div><img alt="field_file_image_title_text" src="/g.jpg"/></div></article></div>
 <div class="group-main-wrapper field-group-div">
  <div class="field-name-field-news-type">Official Announcement</div>
  <div class="field field-name-title-field"><h2><span class="field-wrapper">Official Publications 5.2026</span></h2></div>
  <div class="teaser-trimmed"><p>The Official Gazette of the CPVO has been published.</p>
   <p>You may download the gazette from the Gazette</p></div>
 </div>
 <div><div class="field-name-field-display-date"><time datetime="2026-10-15T12:00:00Z">15 October 2026</time></div></div>
</a></div></div></article></li></ul></main>"""

CFG = next(c for c in bespoke.BESPOKE_SOURCES if c["institution"] == "CPVO")


def test_the_economy_listing_takes_the_heading():
    [(url, title, when)] = cpvo._parse_listing(CARD)
    assert title == "Official Publications 5.2026"
    assert url == "https://cpvo.europa.eu/en/news-and-events/news/official-publications-52026"
    assert when.date().isoformat() == "2026-10-15"


def test_a_heading_link_still_works():
    html = ('<main><div class="views-row"><h3><a href="/en/x/seminar">Seminar on plant variety rights</a></h3>'
            '<p>Some teaser text</p><time datetime="2026-01-02T00:00:00Z">2 January</time></div></main>')
    [(url, title, _)] = cpvo._parse_listing(html)
    assert title == "Seminar on plant variety rights" and url.endswith("/en/x/seminar")


def test_the_news_scraper_takes_the_heading():
    [item] = bespoke.parse_bespoke(CARD, CFG)
    assert item["title"] == "Official Publications 5.2026"


def test_a_long_card_no_longer_falls_back_to_the_slug():
    long_card = CARD.replace("Official Publications 5.2026",
                             "Announcement n 03/2026 of the Community Plant Variety Office") \
                    .replace("The Official Gazette of the CPVO has been published.", "Decision text. " * 20)
    [item] = bespoke.parse_bespoke(long_card, CFG)
    assert item["title"] == "Announcement n 03/2026 of the Community Plant Variety Office"


def test_a_link_whose_only_text_is_a_short_heading_is_unchanged():
    # The CJEU's PDF link: "<a><h3>Information</h3></a>". Too short to be a title before and
    # after, so the same fallback applies (checked on 20 live listings: only CPVO changed).
    attrs, inner = ' target="_blank"', "\n  <h3>Information </h3>\n"
    assert bespoke._resolve_title_with_source(attrs, inner, "/upload/docs/application/pdf/2026-09/cp260131en.pdf") \
        == bespoke._resolve_title_with_source(attrs, "Information", "/upload/docs/application/pdf/2026-09/cp260131en.pdf")

"""News rows must arrive dated (11 September 2026).

Measured on the live listings that day, running the production parsers with no
database writes: CNECT dated 0 of 13 cards, the Reform task force 0 of 10, and
the ESMA feed 0 of 10 -- while the date was printed on every one of those cards.
The parsers were reading one carrier (`<time datetime>`, or an RSS <pubDate>) and
dropping everything else on the floor.

The card markup in these tests is copied from the live pages, trimmed only of
images and attributes that play no part in parsing.
"""
import pathlib
import sys
from datetime import date, timedelta

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
BACKEND = pathlib.Path(_REPO_ROOT) / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services.scrapers.dg_news_scraper import parse_ecl_news  # noqa: E402


def _card(meta: str, href: str, title: str = "A title", desc: str = "") -> str:
    return (
        '<article class="ecl-content-item" ><div class="ecl-content-block '
        'ecl-content-item__content-block" data-ecl-content-block >'
        f"{meta}"
        '<div class="ecl-content-block__title">'
        f'<a href="{href}" class="ecl-link ecl-link--standalone" data-ecl-title-link >'
        f"<span>{title}</span></a></div>"
        f'{desc}</div></article>'
    )


# --- ECL cards dated only in primary-meta TEXT -------------------------------

CNECT_CARD = _card(
    '<ul class="ecl-content-block__primary-meta-container">'
    '<li class="ecl-content-block__primary-meta-item">Press release</li>'
    '<li class="ecl-content-block__primary-meta-item">31 August 2026</li></ul>',
    "/en/news/commission-designates-chatgpt-reddit-roblox-under-digital-services-act",
    "Commission designates ChatGPT, Reddit, Roblox under Digital Services Act",
)

REFORM_CARD = _card(
    '<div class="ecl-content-block__primary-meta-container">'
    '<div class="ecl-content-block__primary-meta-item">7 September 2026</div></div>',
    "https://ec.europa.eu/commission/presscorner/detail/en/ip_26_1801",
    "Commission greenlights the Netherlands&#039; fourth payment request",
    '<div class="ecl-content-block__description">European Commission Press release '
    "Brussels, 07 Sep 2026 Today, the European Commission positively assessed</div>",
)


def test_cnect_card_is_dated_from_its_li_meta_item():
    items = parse_ecl_news(CNECT_CARD, "https://digital-strategy.ec.europa.eu/en/news", "news")
    assert [i["news_date"] for i in items] == [date(2026, 8, 31)]
    # The first meta item still decides the type, as before.
    assert items[0]["item_type"] == "press"


def test_reform_card_is_dated_from_its_div_meta_item():
    items = parse_ecl_news(REFORM_CARD, "https://commission.europa.eu/", "news")
    assert [i["news_date"] for i in items] == [date(2026, 9, 7)]


def test_sept_is_a_september_abbreviation_not_a_silent_miss():
    # strptime's %b accepts "Sep" and rejects "Sept"; Europol lost every September
    # date to exactly that on 11 Sep 2026. Every spelling must parse.
    for meta in ("11 Sept 2026", "11 Sep 2026", "11 September 2026", "11 Sept. 2026"):
        card = _card(
            '<ul class="ecl-content-block__primary-meta-container">'
            f'<li class="ecl-content-block__primary-meta-item">{meta}</li></ul>',
            "/en/news/an-item-published-in-september")
        items = parse_ecl_news(card, "https://digital-strategy.ec.europa.eu/en/news", "news")
        assert [i["news_date"] for i in items] == [date(2026, 9, 11)], meta


def test_time_datetime_still_wins_when_present():
    card = _card(
        '<ul class="ecl-content-block__primary-meta-container">'
        '<li class="ecl-content-block__primary-meta-item">News article</li>'
        '<li class="ecl-content-block__primary-meta-item">'
        '<time datetime="2026-09-11T12:00:00Z">11 September 2026</time></li></ul>',
        "/news-and-media/news/safer-and-more-secure-digital-products-2026-09-11_en",
    )
    items = parse_ecl_news(card, "https://commission.europa.eu/", "news")
    assert [i["news_date"] for i in items] == [date(2026, 9, 11)]


def test_a_meta_item_that_merely_contains_a_date_is_not_a_publication_date():
    card = _card(
        '<ul class="ecl-content-block__primary-meta-container">'
        '<li class="ecl-content-block__primary-meta-item">Deadline 30 September 2026</li></ul>',
        "/en/news/some-call",
    )
    items = parse_ecl_news(card, "https://digital-strategy.ec.europa.eu/en/news", "news")
    assert [i["news_date"] for i in items] == [None]


def test_two_bare_dates_is_ambiguous_and_stays_undated():
    card = _card(
        '<ul class="ecl-content-block__primary-meta-container">'
        '<li class="ecl-content-block__primary-meta-item">1 September 2026</li>'
        '<li class="ecl-content-block__primary-meta-item">3 September 2026</li></ul>',
        "/en/news/some-event",
    )
    items = parse_ecl_news(card, "https://digital-strategy.ec.europa.eu/en/news", "news")
    assert [i["news_date"] for i in items] == [None]


def test_a_future_meta_date_is_refused():
    future = date.today() + timedelta(days=30)
    card = _card(
        '<ul class="ecl-content-block__primary-meta-container">'
        f'<li class="ecl-content-block__primary-meta-item">{future.day} {future:%B %Y}</li></ul>',
        "/en/news/tomorrow",
    )
    items = parse_ecl_news(card, "https://digital-strategy.ec.europa.eu/en/news", "news")
    assert [i["news_date"] for i in items] == [None]


# --- navigation cards are not news -------------------------------------------

def test_undated_press_corner_link_card_is_skipped():
    card = _card("", "https://ec.europa.eu/commission/presscorner/home/en", "Visit the Press corner")
    assert parse_ecl_news(card, "https://commission.europa.eu/news-and-media/news_en", "news") == []


def test_undated_faceted_listing_link_card_is_skipped():
    card = _card(
        "",
        "https://research-and-innovation.ec.europa.eu/news/all-research-and-innovation-news_en"
        "?f%5B0%5D=oe_news_types%3Ahttp%3A//publications.europa.eu/resource/authority/"
        "resource-type/PRESS_REL",
        "Press releases",
        '<div class="ecl-content-block__description"><p>Latest press releases and statements</p></div>',
    )
    assert parse_ecl_news(card, "https://research-and-innovation.ec.europa.eu/news/news-alerts_en", "news") == []


def test_a_dated_card_linking_to_a_listing_is_kept():
    # SANTE announces a real item with a link to a filtered publications listing.
    card = _card(
        '<ul class="ecl-content-block__primary-meta-container">'
        '<li class="ecl-content-block__primary-meta-item">'
        '<time datetime="2026-08-20T12:00:00Z">20 August 2026</time></li></ul>',
        "https://health.ec.europa.eu/cross-border-healthcare/publications_en?f%5B0%5D=oe_publication_type%3Ah",
        "Four new factsheets on cross-border healthcare",
    )
    items = parse_ecl_news(card, "https://health.ec.europa.eu/", "news")
    assert [i["news_date"] for i in items] == [date(2026, 8, 20)]


def test_an_undated_article_card_is_kept_for_the_write_guard_to_decide():
    # INTPA stories carry no date on the card. The parser must not drop a real
    # article: resolving or refusing it is the writer's job, not the parser's.
    card = _card("", "/news-and-events/stories/brazilian-public-defenders-give-migrants-new-hope_en",
                 "Brazilian public defenders give migrants new hope")
    items = parse_ecl_news(card, "https://international-partnerships.ec.europa.eu/", "news")
    assert len(items) == 1 and items[0]["news_date"] is None


# --- RSS without <pubDate> ---------------------------------------------------

def _rss(item_xml: str) -> str:
    return ('<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel>'
            f"<title>Feed</title>{item_xml}</channel></rss>")


ESMA_ITEM = (
    "<item><title>Ongoing geopolitical and economic vulnerabilities masked by strong investor optimism</title>"
    "<link>https://www.esma.europa.eu/press-news/esma-news/ongoing-geopolitical-and-economic-vulnerabilities-masked-strong-investor</link>"
    "<description>&lt;span class=\"field field--name-title field--type-string field--label-hidden\"&gt;Ongoing geopolitical&lt;/span&gt; "
    "&lt;span class=\"field field--name-created field--type-created field--label-hidden\"&gt;"
    "&lt;time datetime=\"2026-09-10T10:25:31+02:00\" title=\"Thursday, September 10, 2026 - 10:25\" class=\"datetime\"&gt;"
    "10 September 2026&lt;/time&gt; &lt;/span&gt;</description></item>"
)


def test_esma_item_without_pubdate_is_dated_from_its_created_field():
    from services.scrapers.dg_news_scraper import parse_rss
    items = parse_rss(_rss(ESMA_ITEM), "https://www.esma.europa.eu/rss.xml", "news")
    assert [i["news_date"] for i in items] == [date(2026, 9, 10)]


def test_pubdate_still_wins_over_the_description():
    from services.scrapers.dg_news_scraper import parse_rss
    item = ESMA_ITEM.replace("</title>", "</title><pubDate>Wed, 09 Sep 2026 08:00:00 +0000</pubDate>", 1)
    items = parse_rss(_rss(item), "https://www.esma.europa.eu/rss.xml", "news")
    assert [i["news_date"] for i in items] == [date(2026, 9, 9)]


def test_a_time_in_the_description_that_is_not_the_created_field_is_ignored():
    # An event date quoted in the body must not become the publication date.
    from services.scrapers.dg_news_scraper import parse_rss
    item = ("<item><title>Webinar announced</title><link>https://example.europa.eu/news/webinar</link>"
            "<description>&lt;p&gt;Join us on &lt;time datetime=\"2026-06-01\"&gt;1 June&lt;/time&gt;&lt;/p&gt;"
            "</description></item>")
    items = parse_rss(_rss(item), "https://example.europa.eu/rss", "news")
    assert [i["news_date"] for i in items] == [None]


def _bespoke(cfg_name):
    from services.scrapers.bespoke_news_scraper import BESPOKE_SOURCES
    return next(c for c in BESPOKE_SOURCES if (c.get("source_key") or c["institution"]) == cfg_name)


# --- bespoke listings: the date on the item's own card -----------------------

ACER_LISTING = """
<div class="view-content row"><div class="row news-list-content">
 <div class="views-row row col-12"><div class="related-news-wrapper col-lg-6 col-md-6 col-12">
  <div class="related-new-date">10th September 2026</div>
  <div class="title-wrapper"><a href="/news/christof-lessenich-become-new-acer-director" hreflang="en">Christof Lessenich to become the new ACER Director</a></div>
  <div class="intro-wrapper">The EU Agency for the Cooperation of Energy Regulators is pleased to announce its next Director.</div>
  <a class="btn-related btn btn-primary" href="/news/christof-lessenich-become-new-acer-director">Read More</a>
 </div></div>
 <div class="views-row row col-12"><div class="related-news-wrapper col-lg-6 col-md-6 col-12">
  <div class="related-new-date">7th September 2026</div>
  <div class="title-wrapper"><a href="/news/acer-calls-better-market-modelling-data-centre-demand-outpaces" hreflang="en">ACER calls for better market modelling as data centre demand outpaces supply</a></div>
 </div></div>
</div></div>
"""


def test_each_acer_card_gets_its_own_date_not_its_neighbours():
    from services.scrapers.bespoke_news_scraper import parse_bespoke
    items = parse_bespoke(ACER_LISTING, _bespoke("ACER"))
    assert [(i["source_url"].rsplit("/", 1)[-1][:20], i["news_date"]) for i in items] == [
        ("christof-lessenich-b", date(2026, 9, 10)),
        ("acer-calls-better-ma", date(2026, 9, 7)),
    ]


EUIPO_LISTING = """
<div class="MuiGrid-container">
 <div class="MuiGrid-root MuiGrid-grid-md-3"><div class="MuiPaper-root MuiCard-root">
  <div><span class="MuiTypography-root MuiTypography-body4"><span>news</span></span></div>
  <span class="MuiTypography-root MuiTypography-body4 css-2m6nlv">September 09, 2026</span>
  <span class="MuiTypography-root MuiTypography-subheading4"><a class="MuiLink-root" href="/en/news/security-alert-beware-of-fraudulent-websites-impersonating-the-euipo">Security alert: Beware of fraudulent websites impersonating the EUIPO</a></span>
 </div></div>
 <div class="MuiGrid-root MuiGrid-grid-md-3"><div class="MuiPaper-root MuiCard-root">
  <span class="MuiTypography-root MuiTypography-body4 css-2m6nlv">July 29, 2026</span>
  <span><a class="MuiLink-root" href="/en/news/eu-registers-joyeria-de-cordoba-as-spain-s-first-craft-geographical-indication">EU registers Joyeria de Cordoba as Spain's first craft geographical indication</a></span>
 </div></div>
</div>
"""


def test_euipo_month_first_card_text_is_read():
    from services.scrapers.bespoke_news_scraper import parse_bespoke
    items = parse_bespoke(EUIPO_LISTING, _bespoke("EUIPO"))
    assert [i["news_date"] for i in items] == [date(2026, 9, 9), date(2026, 7, 29)]


FRA_LISTING = """
<div class="view-content">
 <article class="card"><time datetime="2026-09-10T12:00:00Z" class="datetime">10 September 2026</time>
  <h3><a href="/en/news/2026/community-practice-protecting-human-rights-defenders-meets">Community of practice on protecting human rights defenders meets</a></h3></article>
 <article class="card"><time datetime="2026-09-09T12:00:00Z" class="datetime">9 September 2026</time>
  <h3><a href="/en/news/2026/fra-presents-european-conference-antisemitism-outcomes">FRA presents European Conference on Antisemitism outcomes</a></h3></article>
</div>
"""


def test_a_year_only_url_date_gives_way_to_the_cards_real_date():
    # FRA's /news/2026/ produced 1 January 2026 for every row (66 of 66).
    from services.scrapers.bespoke_news_scraper import parse_bespoke
    items = parse_bespoke(FRA_LISTING, _bespoke("FRA"))
    assert [i["news_date"] for i in items] == [date(2026, 9, 10), date(2026, 9, 9)]


def test_a_day_precise_url_date_is_kept_over_the_card():
    # The Council's URL carries /YYYY/MM/DD/: that is the publisher's own date.
    from services.scrapers.bespoke_news_scraper import parse_bespoke
    listing = """<ul>
     <li class="card"><span class="date">9 September 2026</span>
      <a href="/en/press/press-releases/2026/09/10/press-statement-by-president-costa/">Press statement by President Costa</a></li>
     <li class="card"><span class="date">8 September 2026</span>
      <a href="/en/press/press-releases/2026/09/08/eurogroup-statement/">Eurogroup statement on the budget</a></li>
    </ul>"""
    items = parse_bespoke(listing, _bespoke("COUNCIL"))
    assert [i["news_date"] for i in items] == [date(2026, 9, 10), date(2026, 9, 8)]


def test_an_undated_story_card_stays_undated():
    # CoR "stories" carry a city, a project and a person, and no date anywhere.
    from services.scrapers.bespoke_news_scraper import parse_bespoke
    listing = """<ul class="c-smart-grid">
     <li class="c-smart-grid__grid-item"><span>Turku (Finland)</span>
      <a href="/en/news/stories/kakola-wastewater-treatment-plant-sustainable-water-management">Kakola Wastewater Treatment Plant - Sustainable water management</a>
      <span>Niina RATILAINEN</span><span>Green Deal</span></li>
     <li class="c-smart-grid__grid-item"><span>Gelsenkirchen (Germany)</span>
      <a href="/en/news/stories/lesson-liveable-roads-places-and-neighbourhoods">LesSON - Liveable roads, places and neighbourhoods</a></li>
    </ul>"""
    items = parse_bespoke(listing, _bespoke("COR"))
    assert len(items) == 2 and [i["news_date"] for i in items] == [None, None]


def test_a_deadline_on_the_card_is_not_a_publication_date():
    from services.scrapers.bespoke_news_scraper import parse_bespoke
    listing = """<div>
     <div class="card"><span class="deadline-date">30 September 2026</span>
      <a href="/news/call-for-experts-open-until-end-of-september">Call for experts open until the end of September</a></div>
     <div class="card"><div class="related-new-date">2nd September 2026</div>
      <a href="/news/acer-publishes-market-monitoring-report-2026">ACER publishes its market monitoring report</a></div>
    </div>"""
    items = parse_bespoke(listing, _bespoke("ACER"))
    assert [i["news_date"] for i in items] == [None, date(2026, 9, 2)]


def test_an_abbreviated_month_in_plain_card_text_is_read():
    # CEPOL prints "01 Sept 2026"; a non-month word in the month slot is not a date.
    from services.scrapers.bespoke_news_scraper import parse_bespoke
    listing = """<div>
     <div class="card"><span>News</span><span>01 Sept 2026</span>
      <a href="/en/news/cybercrime-simulation-strengthens-cooperation">Cybercrime simulation strengthens cooperation</a></div>
     <div class="card"><span>Top 12 Items 2026</span>
      <a href="/en/news/the-twelve-items-of-the-year-in-review">The twelve items of the year</a></div>
    </div>"""
    items = parse_bespoke(listing, _bespoke("EUIPO"))
    assert [i["news_date"] for i in items] == [date(2026, 9, 1), None]


def test_two_dates_on_one_card_is_ambiguous():
    from services.scrapers.bespoke_news_scraper import parse_bespoke
    listing = """<div>
     <div class="card"><span>Published 3 September 2026, updated 5 September 2026</span>
      <a href="/en/news/security-alert-updated-guidance-for-users">Security alert: updated guidance</a></div>
     <div class="card"><span>July 29, 2026</span>
      <a href="/en/news/another-item-from-the-office-listing">Another item from the office</a></div>
    </div>"""
    items = parse_bespoke(listing, _bespoke("EUIPO"))
    assert [i["news_date"] for i in items] == [None, date(2026, 7, 29)]


def test_a_lone_item_does_not_borrow_a_date_from_the_whole_page():
    # One item on the page: its "card" climbs to the page body. The size cap stops
    # a date elsewhere on a large page being read as this item's.
    from services.scrapers.bespoke_news_scraper import parse_bespoke
    filler = "<p>" + ("Lorem ipsum dolor sit amet. " * 900) + "</p>"
    listing = (f"<div><a href=\"/en/news/the-only-item-on-this-page\">The only item on this page</a>"
               f"{filler}<aside>Next event: 14 October 2026</aside></div>")
    items = parse_bespoke(listing, _bespoke("EUIPO"))
    assert len(items) == 1 and items[0]["news_date"] is None


def test_the_euaa_listing_page_is_not_an_item():
    from services.scrapers.bespoke_news_scraper import BESPOKE_SOURCES, parse_bespoke
    listing = """<div>
     <a href="/news-events/press-releases">Press Releases and News</a>
     <div class="euaa-news-area__item"><h3>EU+ asylum applications continued to decline in the first half of 2026</h3>
      <p>Published: <time datetime="2026-09-10T12:00:00Z" class="datetime">10 September 2026</time>
      <a href="/news-events/eu-asylum-applications-continued-decline-first-half-2026">Read More</a></p></div>
    </div>"""
    for cfg in [c for c in BESPOKE_SOURCES if c["institution"] == "EUAA"]:
        items = parse_bespoke(listing, cfg)
        assert [i["source_url"].rsplit("/", 1)[-1] for i in items] == [
            "eu-asylum-applications-continued-decline-first-half-2026"], cfg["link_re"]
        assert items[0]["news_date"] == date(2026, 9, 10)


def test_europol_feed_has_no_date_and_stays_undated_for_the_write_guard():
    # Europol's items are title, link and description only (10 of 10, 11 Sep 2026).
    # The date is on each item page, which is the write guard's job to read.
    from services.scrapers.dg_news_scraper import parse_rss
    item = ("<item><title>Thousands of horses caught up in Europe-wide trafficking scheme</title>"
            "<link>https://www.europol.europa.eu/media-press/newsroom/news/thousands-of-horses-caught-in-europe-wide-trafficking-scheme</link>"
            "<description>Europol has supported a major operation.</description></item>")
    items = parse_rss(_rss(item), "https://www.europol.europa.eu/rss", "news")
    assert [i["news_date"] for i in items] == [None]

"""Dating the undated news stock (11 September 2026).

Every snippet here is trimmed from the live page it names. Each rule is tested for
the date it must read AND for the date it must refuse, because on these sites the
wrong date sits right beside the right one.
"""
import pathlib
import sys
from datetime import date, datetime, timedelta, timezone

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
BACKEND = pathlib.Path(_REPO_ROOT) / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services.news import item_date  # noqa: E402
from services.news.item_date import host_item_date, resolve_item_date  # noqa: E402
from services.scrapers.economy_common import extract_item_date  # noqa: E402


def _d(result):
    dt, carrier = result
    return (dt.date() if dt else None), carrier


# --- labelled generic carriers ----------------------------------------------

def test_ecl_publication_header():
    html = ('<ul class="ecl-page-header__meta"><li class="ecl-page-header__meta-item">NEWS ARTICLE</li>'
            '<li class="ecl-page-header__meta-item">Publication 12 June 2026</li></ul>')
    assert _d(extract_item_date(html)) == (date(2026, 6, 12), "ecl_publication_header")


def test_published_label_across_whitespace_and_tags():
    assert _d(extract_item_date("<h3>Published:\n\t\t\t 10 September 2026</h3>")) == (
        date(2026, 9, 10), "published_label")
    assert _d(extract_item_date("<p>Published: <strong>1 July 2026</strong></p>")) == (
        date(2026, 7, 1), "published_label")


def test_labels_not_followed_by_a_date_do_not_match():
    assert extract_item_date("<h2>Published: 3 reports this year</h2>") == (None, None)
    assert extract_item_date(
        '<li class="ecl-page-header__meta-item">Publication type</li>') == (None, None)


def test_a_labelled_carrier_never_overrides_an_earlier_one():
    html = ('<time datetime="2026-09-01T10:00:00Z">1 Sep</time>'
            '<h3>Published: 10 September 2026</h3>')
    assert _d(extract_item_date(html)) == (date(2026, 9, 1), "time_datetime")


# --- EEAS -------------------------------------------------------------------

EEAS_NEWS = """
<div class="main-content col-md-7"><div class="card"><div class="card-body"><div class="content-header">
 <h1>Turning waste into fertiliser: a composting site changing Divjaka</h1>
 <div class="node__meta">07.09.2026 | Press and information team of the Delegation to Albania</div>
</div></div></div></div>
<div class="paragraph paragraph--type--more-stories"><div class="views-element-container"><div class="view view-more-stories">
 <div class="view-content"><div class="related-grid">
  <div class="card story node node--type-story"><div class="image-card-content"><div class="node__meta">28.08.2026</div></div></div>
  <div class="card story node node--type-story"><div class="image-card-content"><div class="node__meta">30.07.2026</div></div></div>
 </div></div></div></div></div>
"""


def test_eeas_reads_the_pages_own_meta_not_the_related_stories():
    url = "https://www.eeas.europa.eu/delegations/albania/turning-waste-fertiliser-composting-site-changing-divjaka_en"
    assert _d(host_item_date(url, EEAS_NEWS)) == (date(2026, 9, 7), "eeas_node_meta")


def test_eeas_campaign_with_only_related_content_is_refused():
    # The eu-ambassadors-conference-2026 campaign: every node__meta belongs to related
    # press material (10 and 9 March) while the listing dates the campaign 4 March.
    html = """<article class="node node--type-campaign"><div class="paragraph--type--related-content">
      <div class="views-element-container"><div class="view-content"><div class="related-grid">
      <div class="card node node--type-press-material"><div class="image-card-content"><div class="node__meta">10.03.2026</div></div></div>
      <div class="card node node--type-press-material"><div class="image-card-content"><div class="node__meta">09.03.2026</div></div></div>
      </div></div></div></div></article>"""
    assert host_item_date("https://www.eeas.europa.eu/eeas/eu-ambassadors-conference-2026_en", html) == (None, None)


def test_eeas_campaign_page_level_meta_is_read():
    html = ('<article class="node node--type-campaign"><div class="node__content">'
            '<div class="container-xxxl pt-4"><div class="node__meta">27.11.2025 | Press and information team</div>'
            '</div></div></article>')
    assert _d(host_item_date("https://www.eeas.europa.eu/plug-in-to-evolution_en", html)) == (
        date(2025, 11, 27), "eeas_node_meta")


def test_eeas_two_own_dates_is_ambiguous():
    html = '<div class="card"><div class="node__meta">01.06.2026</div><div class="node__meta">03.06.2026</div></div>'
    assert host_item_date("https://www.eeas.europa.eu/x_en", html) == (None, None)


# --- Ombudsman --------------------------------------------------------------

OMBUDSMAN = """<app-doc-infos><div class="article-information"><p>
 <span>News</span> - <span class="label">Date</span> <span class="information">Thursday</span>
 <span class="information">20 August 2026</span> <span class="label">Case</span> <span>1036/2026/AML</span> -
 <span class="label">Opened on</span> <span class="information">Tuesday</span> <span class="information">18 August 2026</span>
</p></div></app-doc-infos>"""


def test_ombudsman_reads_the_date_label_not_opened_on():
    url = "https://www.ombudsman.europa.eu/en/news-document/en/231701"
    assert _d(host_item_date(url, OMBUDSMAN)) == (date(2026, 8, 20), "ombudsman_date_label")


def test_ombudsman_without_a_date_label_is_refused():
    html = ('<div class="article-information"><p><span>Opened on</span> <span>Tuesday</span> '
            '<span>18 August 2026</span></p></div>')
    assert host_item_date("https://www.ombudsman.europa.eu/en/news-document/en/1", html) == (None, None)


def test_the_site_rule_runs_before_the_generic_carriers(monkeypatch):
    # A generic carrier on the same page would take the case's decision date.
    html = '<time datetime="2025-11-07T00:00:00Z">7 Nov</time>' + OMBUDSMAN
    seen = {}

    def _fetch(url, fetcher=None, **kw):
        seen["url"] = url
        return html

    monkeypatch.setattr(item_date, "escalating_get", _fetch)
    dt, carrier = resolve_item_date(" https://www.ombudsman.europa.eu/en/news-document/en/231701 ")
    assert (dt.date(), carrier) == (date(2026, 8, 20), "ombudsman_date_label")
    assert seen["url"] == "https://www.ombudsman.europa.eu/en/news-document/en/231701"


# --- EUIPO ------------------------------------------------------------------

def test_euipo_reads_its_only_visible_date_day_first():
    html = ('<div class="MuiStack-root"><span class="MuiTypography-root MuiTypography-body4 css-1x">29/07/2026</span>'
            '<h1>EU registers Joyeria de Cordoba</h1></div>'
            '<script>{"first_published_at":"2023-05-24T19:21:12Z","note":"01/01/2020"}</script>')
    url = "https://www.euipo.europa.eu/en/news/eu-registers-joyeria-de-cordoba"
    assert _d(host_item_date(url, html)) == (date(2026, 7, 29), "euipo_sole_page_date")


def test_euipo_two_visible_dates_is_ambiguous():
    html = "<span>09/09/2026</span><p>Apply by 30/09/2026</p>"
    assert host_item_date("https://www.euipo.europa.eu/en/news/x", html) == (None, None)


EUIPO_WEBINARS = (
    "<span>02/06/2026</span><span>09/06/2026</span><span>16/06/2026</span>"
    '<script>self.__next_f.push([1,"{\\"story\\":{\\"name\\":\\"Layout\\",\\"full_slug\\":\\"en/layout\\",'
    '\\"first_published_at\\":\\"2023-05-24T19:21:12.176Z\\"},\\"page\\":{\\"name\\":\\"Tuesday Webinars June 2026\\",'
    '\\"slug\\":\\"tuesday-webinars-june-2026\\",\\"full_slug\\":\\"en/news/tuesday-webinars-june-2026\\",'
    '\\"sort_by_date\\":null,\\"first_published_at\\":\\"2026-05-28T15:00:25.065Z\\"}}"])</script>'
)


def test_euipo_ambiguous_page_falls_back_to_its_own_storyblok_story():
    url = "https://www.euipo.europa.eu/en/news/tuesday-webinars-june-2026"
    assert _d(host_item_date(url, EUIPO_WEBINARS)) == (date(2026, 5, 28), "euipo_sole_page_date")


def test_euipo_storyblok_value_of_another_story_is_never_taken():
    url = "https://www.euipo.europa.eu/en/news/some-other-article"
    assert host_item_date(url, EUIPO_WEBINARS) == (None, None)


# --- ECHA -------------------------------------------------------------------

def test_echa_reads_the_helsinki_dateline_not_the_deadlines():
    html = ('<div class="single-news-article"><p><strong>Helsinki,&nbsp;17 August 2026 –</strong> '
            'ECHA begins work. Comments by 13 August 2026 are welcome; the restriction applies from '
            '14 February 2028.</p></div>')
    url = "https://echa.europa.eu/-/echa-begins-work-to-reduce-hazardous-substances-in-vehicles"
    assert _d(host_item_date(url, html)) == (date(2026, 8, 17), "echa_helsinki_dateline")


def test_echa_without_a_dateline_is_refused():
    html = '<div class="single-news-article"><p>ECHA updated eChemPortal on 20 April 2026.</p></div>'
    assert host_item_date("https://echa.europa.eu/-/echa-updates-oecd-echemportal", html) == (None, None)


ENISA_PAGE = """<article class="node-news-content">
 <p class="events-metadata"><span class="type">Press Release</span> <span class="date">Aug 06,2026</span></p>
 <div class="publications-item"><div class="publication-content"><p class="metadata"><span class="date">
  <time datetime="2023-02-16T02:00:00+02:00" class="datetime">16 February, 2023</time></span></p></div></div>
 <div class="publications-item"><div class="publication-content"><p class="metadata"><span class="date">
  <time datetime="2019-01-14T02:00:00+02:00" class="datetime">14 January, 2019</time></span></p></div></div>
</article>"""


def test_enisa_reads_its_byline_not_the_related_publications():
    url = "https://www.enisa.europa.eu/news/enisa-scales-up-its-role-in-the-cve-program"
    assert _d(host_item_date(url, ENISA_PAGE)) == (date(2026, 8, 6), "enisa_events_metadata")


def test_a_site_rule_is_authoritative_no_generic_fallback(monkeypatch):
    # Without its byline the ENISA page still holds a related publication's <time>.
    # The generic carriers would store 2023; the resolver must refuse instead.
    page = ENISA_PAGE.replace('<p class="events-metadata">', '<p class="other">')
    monkeypatch.setattr(item_date, "escalating_get", lambda u, fetcher=None, **kw: page)
    monkeypatch.setattr(item_date, "browser_get", lambda u, fetcher=None: page)
    assert resolve_item_date("https://www.enisa.europa.eu/news/x") == (None, "no_carrier")
    assert extract_item_date(page)[0] is not None       # the generic trap is real


def test_site_rules_do_not_leak_to_other_hosts():
    assert host_item_date("https://www.enisa.europa.eu/news/x", EEAS_NEWS) == (None, None)


# --- parser: the URL forms that made stock undatable ------------------------

def test_bespoke_strips_whitespace_inside_href():
    from services.scrapers.bespoke_news_scraper import BESPOKE_SOURCES, parse_bespoke
    cfg = next(c for c in BESPOKE_SOURCES if c["institution"] == "ENISA")
    listing = ('<div><h3><a href="/news/the-cra-single-reporting-platform-is-launched ">'
               'The CRA Single Reporting Platform is launched</a></h3></div>')
    items = parse_bespoke(listing, cfg)
    assert [i["source_url"] for i in items] == [
        "https://www.enisa.europa.eu/news/the-cra-single-reporting-platform-is-launched"]
    assert not items[0]["entry_key"].endswith(" ")


def test_bespoke_resolves_a_relative_base_href_against_the_listing():
    from services.scrapers.bespoke_news_scraper import BESPOKE_SOURCES, parse_bespoke
    cfg = next(c for c in BESPOKE_SOURCES if c["institution"] == "OMBUDSMAN")
    listing = ('<html><head><base href="/"></head><body><div>'
               '<a href="/en/news-document/en/231701">Ombudswoman opens inquiry into trade department lobbying</a>'
               '</div></body></html>')
    items = parse_bespoke(listing, cfg)
    assert [i["source_url"] for i in items] == ["https://www.ombudsman.europa.eu/en/news-document/en/231701"]
    assert items[0]["entry_key"] == "https://www.ombudsman.europa.eu/en/news-document/en/231701"


def test_backfill_makes_stored_urls_fetchable():
    from scripts.backfill_news_document_dates import _absolute_url
    assert _absolute_url("OMBUDSMAN", "/en/news-document/en/226977") == \
        "https://www.ombudsman.europa.eu/en/news-document/en/226977"
    assert _absolute_url("ENISA", "https://www.enisa.europa.eu/news/x ") == "https://www.enisa.europa.eu/news/x"
    assert _absolute_url("ESMA", "https://www.esma.europa.eu/a") == "https://www.esma.europa.eu/a"


# --- repair plan ------------------------------------------------------------

def _row(i, url, sk, nd=None, fetched=None, key=None):
    from services.scrapers.dg_news_scraper import _canon_url
    return {"id": i, "source_url": url, "source_key": sk, "news_date": nd, "fetched_at": fetched,
            "entry_key": key or _canon_url(url), "title": f"t{i}"}


NOW = datetime(2026, 9, 11, 16, 0, tzinfo=timezone.utc)
OLD = NOW - timedelta(days=90)
FRESH = NOW - timedelta(hours=3)
LISTINGS = {"OMBUDSMAN": "https://www.ombudsman.europa.eu/en/news-documents",
            "ENISA": "https://www.enisa.europa.eu/news"}


def _plan(rows, post_deploy=False):
    from scripts.repair_news_stock import plan
    from services.scrapers.dg_news_scraper import _canon_url
    return plan(rows, listing_urls=LISTINGS, canon_key=_canon_url, now=NOW, post_deploy=post_deploy)


def test_navigation_and_registry_rows_are_junk_but_a_dated_faceted_item_is_not():
    rows = [
        _row(1, "https://ec.europa.eu/commission/presscorner/home/en", "EC", fetched=OLD),
        _row(2, "https://research-and-innovation.ec.europa.eu/news/all_en?f%5B0%5D=oe_news_types%3Ax", "RTD", fetched=OLD),
        _row(3, "https://agriculture.ec.europa.eu/farming/gi/geographical-indications-food-and-drink/bordeaux_en", "AGRI"),
        _row(4, "https://health.ec.europa.eu/x/publications_en?f%5B0%5D=oe_publication_type%3Ah", "SANTE",
             nd=date(2026, 6, 8), fetched=OLD),
    ]
    p = _plan(rows)
    assert sorted(a["id"] for a in p["delete"]) == [1, 2, 3]


def test_cor_stories_hub_link_is_navigation_in_parser_and_repair():
    from services.scrapers.bespoke_news_scraper import BESPOKE_SOURCES, parse_bespoke
    cfg = next(c for c in BESPOKE_SOURCES if c["institution"] == "COR")
    listing = ('<ul><li><a href="/en/news/all-stories">Access all stories</a></li>'
               '<li><a href="/en/news/regions-call-stronger-local-voice-consumer-policy">'
               'Regions call for a stronger local voice in consumer policy</a></li></ul>')
    assert [i["source_url"].rsplit("/", 1)[-1] for i in parse_bespoke(listing, cfg)] == [
        "regions-call-stronger-local-voice-consumer-policy"]
    rows = [_row(1, "https://www.cor.europa.eu/en/news/all-stories", "COR", fetched=OLD)]
    assert [(a["id"], a["why"]) for a in _plan(rows)["delete"]] == [(1, "cor_stories_hub_navigation")]


def test_relative_twin_is_deleted_and_its_date_carried_over():
    rows = [_row(1, "https://www.ombudsman.europa.eu/en/news-document/en/224093", "OMBUDSMAN", fetched=None),
            _row(2, "/en/news-document/en/224093", "OMBUDSMAN", nd=date(2026, 5, 11), fetched=OLD)]
    p = _plan(rows)
    assert [(a["id"], a["survivor"]) for a in p["delete"]] == [(2, 1)]
    assert p["set_date"] == [{"id": 1, "news_date": date(2026, 5, 11), "why": "date_carried_from_deleted_twin"}]


def test_a_row_on_a_live_listing_waits_for_the_deploy():
    rows = [_row(1, "https://www.ombudsman.europa.eu/en/news-document/en/225413", "OMBUDSMAN"),
            _row(2, "/en/news-document/en/225413", "OMBUDSMAN", fetched=FRESH),
            _row(3, "/en/news-document/en/231701", "OMBUDSMAN", fetched=FRESH)]
    before = _plan(rows)
    assert before["delete"] == [] and before["rewrite"] == []
    assert sorted(a["id"] for a in before["deferred"]) == [2, 3]
    after = _plan(rows, post_deploy=True)
    assert [a["id"] for a in after["delete"]] == [2]
    assert [(a["id"], a["new_url"], a["new_key"]) for a in after["rewrite"]] == [
        (3, "https://www.ombudsman.europa.eu/en/news-document/en/231701",
         "https://www.ombudsman.europa.eu/en/news-document/en/231701")]


def test_whitespace_url_with_a_twin_is_deleted_and_without_one_rewritten():
    rows = [_row(1, "https://www.enisa.europa.eu/news/nis360", "ENISA", fetched=OLD),
            _row(2, "https://www.enisa.europa.eu/news/nis360 ", "ENISA", fetched=OLD),
            _row(3, "https://www.enisa.europa.eu/news/cve-root ", "ENISA", fetched=OLD)]
    p = _plan(rows)
    assert [a["id"] for a in p["delete"]] == [2]
    assert [(a["id"], a["new_url"]) for a in p["rewrite"]] == [(3, "https://www.enisa.europa.eu/news/cve-root")]


def test_cor_alias_copy_is_deleted_in_favour_of_the_real_slug():
    rows = [_row(1, "https://www.cor.europa.eu/en/news/ukraine-recovery-conference-gdansk", "COR", fetched=OLD),
            _row(2, "https://www.cor.europa.eu/en/news/ukraine-recovery-conference-gdansk-0", "COR", fetched=OLD)]
    rows[1]["title"] = rows[0]["title"] = "Ukraine Recovery Conference: Gdansk serves as a milepost"
    p = _plan(rows)
    assert [(a["id"], a["why"]) for a in p["delete"]] == [(2, "cor_drupal_alias_of_real_slug")]


def test_a_dash_zero_slug_elsewhere_or_with_another_title_is_a_different_item():
    rows = [_row(1, "https://www.srb.europa.eu/en/content/technical-meeting-operational-guidance", "SRB", fetched=OLD),
            _row(2, "https://www.srb.europa.eu/en/content/technical-meeting-operational-guidance-0", "SRB", fetched=OLD),
            _row(3, "https://www.cor.europa.eu/en/news/plenary-session", "COR", fetched=OLD),
            _row(4, "https://www.cor.europa.eu/en/news/plenary-session-0", "COR", fetched=OLD)]
    rows[2]["title"], rows[3]["title"] = "Plenary session, June", "Plenary session, July"
    assert _plan(rows)["delete"] == []


def test_a_future_date_beside_the_real_one_still_makes_the_page_ambiguous():
    html = '<div class="card"><div class="node__meta">01.06.2026</div><div class="node__meta">30.12.2099</div></div>'
    assert host_item_date("https://www.eeas.europa.eu/x_en", html) == (None, None)


def test_a_clean_row_is_left_alone():
    rows = [_row(1, "https://www.esma.europa.eu/press-news/esma-news/x", "ESMA", fetched=FRESH)]
    assert _plan(rows) == {"delete": [], "set_date": [], "rewrite": [], "deferred": []}

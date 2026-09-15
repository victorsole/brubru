"""Rows from site-wide feeds carry the type of what they are, not `news`.

The defect (found 15 Sep 2026): the RSS parser stamps every entry with its feed's default
type. Ten bodies were read from site-wide feeds, so eu_news_items held events, videos,
podcasts, consultations, publications, e-mail alert digests, vacancies and procurement
notices as news, and /api/v2/news/all served them (EESC alone: 361). The registry now
reads section feeds where they exist, drops the feeds with no news, and types the rest
through services/news/feed_item_types.py; scripts/relabel_news_item_types.py fixed the
stock with the same rules.

Until the registry change is deployed, production still reads the old feeds and can
re-stamp their newest rows as news, which fails the store tests below. Deploy, then run
the relabel script again.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from api.v1._deps import api_user_with_rate_limit
from api.v2.news import _EU_NEWS_SOURCE_TYPES, _INSTITUTIONAL_NEWS
from main import app
from models.user import User
from services.news import feed_item_types as fit
from services.scrapers import dg_news_scraper
from services.scrapers.dg_news_sources import EU_BODY_FEEDS

RULED = sorted(fit.RULES)


@pytest.fixture(scope="module")
def db():
    from core.database import SessionLocal
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture(scope="module")
def client():
    app.dependency_overrides[api_user_with_rate_limit] = lambda: User(
        email="test@example.com", role="admin"
    )
    yield TestClient(app)
    app.dependency_overrides.pop(api_user_with_rate_limit, None)


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------

def _feeds(inst):
    return {f["url"]: f["default_type"] for f in EU_BODY_FEEDS if f["institution"] == inst}


def test_section_feeds_replace_the_site_wide_ones():
    assert _feeds("EESC") == {
        "https://www.eesc.europa.eu/en/news-media/news.rss": "news",
        "https://www.eesc.europa.eu/en/news-media/press-releases.rss": "press",
    }
    assert _feeds("BEREC") == {
        "https://www.berec.europa.eu/en/export_news.xml/371": "news",
        "https://www.berec.europa.eu/en/export_news.xml/378": "press",
    }


def test_feeds_without_news_are_gone():
    for inst in ("ERA", "EFCA", "EBA"):
        assert not _feeds(inst), f"{inst}'s feed carried no news and came back"


def test_a_section_feed_default_agrees_with_the_rule_for_its_section():
    """Otherwise each sync would flip a relabelled row back."""
    assert fit.rule_for("EESC", "https://www.eesc.europa.eu/en/news-media/news/x") == "news"
    assert fit.rule_for("EESC", "https://www.eesc.europa.eu/en/news-media/press-releases/x") == "press"
    assert fit.rule_for("EESC", "https://www.eesc.europa.eu/en/president/news/x") == "press"
    assert fit.rule_for("BEREC", "https://www.berec.europa.eu/en/news/latest-news/x") == "news"
    assert fit.rule_for("BEREC", "https://www.berec.europa.eu/en/news/press-releases/x") == "press"


def test_every_feed_still_in_the_registry_from_a_ruled_body_has_rules():
    for f in EU_BODY_FEEDS:
        if f["institution"] in ("EESC", "BEREC", "ELA", "ETF", "EULISA", "EFSA", "SRB"):
            assert fit.has_rules(f["institution"])


# ---------------------------------------------------------------------------
# The rules (examples taken from the stored rows and their own pages, 15 Sep 2026)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("inst,url,expected", [
    ("EESC", "https://www.eesc.europa.eu/en/agenda/our-events/events/nat-section-28042027", "event"),
    ("EESC", "https://www.eesc.europa.eu/en/agenda-items/41st-esg-meeting", "event"),
    ("EESC", "https://www.eesc.europa.eu/en/our-work/opinions-information-reports/follow-opinions/eco687-follow-commission", "publication"),
    ("EESC", "https://www.eesc.europa.eu/en/news-media/videos/we-have-date-university-college-cork-30-june-2026", "video"),
    ("EESC", "https://www.eesc.europa.eu/en/news-media/articles/current-affairs-wildfires-eu", "story"),
    ("EESC", "https://www.eesc.europa.eu/en/news-media/test-r", fit.SKIP),
    ("BEREC", "https://www.berec.europa.eu/en/public-consultations-calls-for-inputs/public-consultation-on-the-draft-berec-further-guidance-on-5g-network-slicing", "consultation"),
    ("BEREC", "https://www.berec.europa.eu/en/events/berec-external-workshop-on-combating-fraud", "event"),
    ("BEREC", "https://www.berec.europa.eu/en/tasks/berec-position-papers-on-the-digital-networks-act-proposal", "publication"),
    ("BEREC", "https://www.berec.europa.eu/en/composition-of-the-management-board-pursuant-to-article-15-and-352-of-regulation-eu-20181971-1", fit.SKIP),
    ("ELA", "https://www.ela.europa.eu/en/news/ela-launches-eu4socialsecurity-campaign", "news"),
    ("ELA", "https://www.ela.europa.eu/en/publications/labour-shortages-and-surpluses-europe-2025", "publication"),
    ("ELA", "https://www.ela.europa.eu/en/about-ela/procurements/eures-training-programme-ela2026op0004", fit.SKIP),
    ("ETF", "https://www.etf.europa.eu/en/node/13446", "news"),
    ("ETF", "https://www.etf.europa.eu/en/publications-and-resources/publications/trp-monitoring-reports/turning-textile-waste-opportunity", "publication"),
    ("EULISA", "https://www.eulisa.europa.eu/news-and-events/videos/making-ees", "video"),
    ("EULISA", "https://www.eulisa.europa.eu/news-and-events/events/eu-lisa-industry-roundtable-sep-2026", "event"),
    ("EFSA", "https://www.efsa.europa.eu/en/podcast/episode-42-pesticides-good-bad-and-ugly", "podcast"),
    ("EFSA", "https://www.efsa.europa.eu/en/news/efsa-lowers-safe-level-exposure-tfa", "news"),
    ("EFCA", "https://www.efca.europa.eu/en/information-hub/video/coast-guard-functions-exercise-at-sea", "video"),
    ("EFCA", "https://www.efca.europa.eu/en/node/951", fit.SKIP),
    ("ERA", "https://www.era.europa.eu/agency-you/recruitment/vacancies", fit.SKIP),
    ("EBA", "https://www.eba.europa.eu/node/19999", "publication"),
    ("SRB", "https://www.srb.europa.eu/en/content/head-ict-development", fit.SKIP),
    ("SRB", "https://www.srb.europa.eu/en/content/srb-statement-tragic-incident-its-premises", fit.PAGE),
    ("EMA", "https://www.ema.europa.eu/en/news/anything", fit.UNKNOWN),  # no rules: untouched
])
def test_the_rules(inst, url, expected):
    assert fit.rule_for(inst, url) == expected


@pytest.mark.parametrize("html,expected", [
    ('<body class="path-node page-node-type-srb-news">', "news"),
    ('<body class="path-node page-node-type-srb-event">', "event"),
    ('<body class="path-node page-node-type-srb-tender">', fit.SKIP),
    ('<body class="layout-no-sidebars page-node-951 path-node node--type-procurement">', fit.SKIP),
    ('<body class="path-frontpage">', fit.UNKNOWN),
])
def test_a_page_rule_reads_the_drupal_node_type(html, expected):
    got, how = fit.item_type_for("SRB", "https://www.srb.europa.eu/en/content/x", fetch=lambda u: html)
    assert got == expected


def test_an_unreadable_page_is_unknown_not_a_guess():
    assert fit.item_type_for("SRB", "https://www.srb.europa.eu/en/content/x", fetch=lambda u: None) == (
        fit.UNKNOWN, "page-unreadable")


def test_the_sync_drops_non_content_and_types_the_rest(monkeypatch):
    monkeypatch.setattr(dg_news_scraper, "_fetch_page_text",
                        lambda u: '<body class="page-node-type-srb-event">')
    items = [
        {"source_url": "https://www.srb.europa.eu/en/content/head-ict-development", "item_type": "news"},
        {"source_url": "https://www.srb.europa.eu/en/content/sixteenth-round-table", "item_type": "news"},
    ]
    out = dg_news_scraper._type_feed_items("SRB", items)
    assert [(i["source_url"].rsplit("/", 1)[-1], i["item_type"]) for i in out] == [
        ("sixteenth-round-table", "event")]
    # A body without rules is returned untouched.
    ema = [{"source_url": "https://www.ema.europa.eu/en/news/x", "item_type": "news"}]
    assert dg_news_scraper._type_feed_items("EMA", ema) == ema


# ---------------------------------------------------------------------------
# The store and the API
# ---------------------------------------------------------------------------

def test_every_stored_row_of_a_ruled_body_has_a_rule(db):
    rows = db.execute(text("SELECT institution, source_url FROM eu_news_items "
                           "WHERE institution = ANY(:i)"), {"i": RULED}).fetchall()
    assert rows, "no rows: the instrument, not a pass"
    assert not [(r.institution, r.source_url) for r in rows
                if fit.rule_for(r.institution, r.source_url) == fit.UNKNOWN]


def test_no_stored_row_contradicts_its_url_rule(db):
    """PAGE rows are typed from their page and checked by the relabel dry run instead."""
    rows = db.execute(text("SELECT institution, item_type, source_url FROM eu_news_items "
                           "WHERE institution = ANY(:i)"), {"i": RULED}).fetchall()
    wrong = []
    for r in rows:
        rule = fit.rule_for(r.institution, r.source_url)
        if rule == fit.SKIP:
            wrong.append((r.institution, "should not be stored", r.source_url))
        elif rule not in (fit.PAGE, fit.UNKNOWN) and rule != r.item_type:
            wrong.append((r.institution, f"{r.item_type} != {rule}", r.source_url))
    assert not wrong, f"{len(wrong)} rows, e.g. {wrong[:3]}"


@pytest.mark.parametrize("body", sorted(k for k, v in _INSTITUTIONAL_NEWS.items() if v in fit.RULES))
def test_the_news_api_serves_no_non_news_item_from_a_ruled_body(client, body):
    inst = _INSTITUTIONAL_NEWS[body]
    items, page = [], 1
    while True:
        r = client.get("/api/v2/news/all", params={"body": body, "days": 3650, "limit": 100, "page": page})
        assert r.status_code == 200
        items += r.json()["data"]
        if not r.json().get("has_more"):
            break
        page += 1
    institutional = [i for i in items if isinstance(i["id"], str)]
    bad = []
    for i in institutional:
        rule = fit.rule_for(inst, i["public_url"])
        if rule == fit.SKIP or (rule not in (fit.PAGE, fit.UNKNOWN) and rule not in _EU_NEWS_SOURCE_TYPES):
            bad.append((rule, i["public_url"]))
    assert not bad, f"{body}: {len(bad)} served, e.g. {bad[:3]}"

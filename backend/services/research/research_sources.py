"""
Research & Evidence source catalogue (MEUB Section 4, independent tab).

A curated, PI-aware launchpad over EXTERNAL EU research/evidence publishers.
Read-only: deep-links + PI-seeded searches, plus read-through of a source's
publications RSS feed where one exists. Two feed mechanisms:

  1. Native page feed: many EC DG /publications_en pages expose a feed at
     /node/<N>/rss_en (auto-discovered from the page).
  2. Central corporate-body feed: the unified EC publications feed
     (commission.europa.eu/node/3/rss_en) filtered to one DG by its
     corporate-body authority code. Used for DGs without a clean native feed.

Admin noise (management plans, annual activity reports) is filtered out by title.
No DB ingestion, no Anthropic.

Groups: 'foresight' (STOA/JRC/Council), 'research' (cross-cutting research bodies:
CORDIS, JRC Knowledge Centres, the Publications Office catalogue, data.europa.eu),
and 'department' (Commission DGs and research executive agencies).
"""
from __future__ import annotations

import logging
import re
import time
import urllib.parse
import urllib.request
from typing import Dict, List, Optional
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

_UA = {"User-Agent": "Brubru/1.0 (+https://brubru.beresol.eu)"}
_TTL = 6 * 3600
_rss_cache: Dict[str, tuple] = {}   # landing -> (expiry, rss_url|None)
_feed_cache: Dict[str, tuple] = {}  # feed_url -> (expiry, items)

# Central EC publications feed + corporate-body authority namespace.
_CENTRAL_FEED = "https://commission.europa.eu/node/3/rss_en"
_CB = "http://publications.europa.eu/resource/authority/corporate-body/"

# Titles that are administrative noise, not research/evidence.
_ADMIN_RE = re.compile(
    r"^(management plan|annual activity report|consolidated annual activity|annual management plan|"
    r"strategic plan|list of |organisation chart|mission letter|decision of the|"
    r"register of|code of conduct|declaration of|"
    r"vacancy notice|vacancy for|statement of revenue|call for expression|call for tender|"
    r"call for proposal|call for application|budget of|financial statements?|publication of the annual|"
    r"minutes of|board of supervisors|sb composition|composition of|contact persons|it solutions|"
    r"agenda of|summary of conclusions|publication of the final|changes from last update)",
    re.I,
)


def _src(id, group, icon, color, name, full, landing, search, pi_tags,
         feed_landing=None, cb_code=None, sparql_cb=None, rss_url=None, scrape_cfg=None,
         economy_body=None):
    return dict(id=id, group=group, icon=icon, color=color, name=name, full=full,
                landing=landing, search=search, pi_tags=pi_tags,
                feed_landing=feed_landing, cb_code=cb_code, sparql_cb=sparql_cb,
                rss_url=rss_url, scrape_cfg=scrape_cfg, economy_body=economy_body)


# Brand colours reused across cards.
_B, _A, _G, _P, _O, _R = "#1e3a8a", "#0693e3", "#059669", "#9b51e0", "#d97706", "#dc2626"

SOURCES: List[dict] = [
    # ---- Foresight anchors ----
    _src("stoa", "foresight", "flask", _B, "STOA",
         "European Parliament scientific foresight (Panel for the Future of Science and Technology)",
         "https://www.europarl.europa.eu/stoa/en/home/highlights",
         "https://www.europarl.europa.eu/thinktank/en/search.html?textualSearch={q}", ["*"]),
    _src("jrc", "foresight", "microscope", _A, "JRC Publications",
         "Joint Research Centre publications repository (science for policy)",
         "https://publications.jrc.ec.europa.eu/repository/",
         "https://publications.jrc.ec.europa.eu/repository/search?query={q}", ["*"]),
    _src("council", "foresight", "bank", _P, "Council think tank",
         "Council of the EU Analysis & Research Team and strategic papers",
         "https://www.consilium.europa.eu/en/documents-publications/think-tank/",
         "https://www.consilium.europa.eu/en/documents-publications/think-tank/?keyword={q}", ["*"]),

    # ---- Cross-cutting research bodies ----
    _src("cordis", "research", "rocket", _G, "CORDIS",
         "Results of EU-funded research (Horizon Europe, H2020, FP7): projects, deliverables, result briefs",
         "https://cordis.europa.eu/projects", "https://cordis.europa.eu/search?q={q}", ["*"]),
    # The Product Bureau is where the ecodesign preparatory studies live, one
    # product group at a time. It is the research source behind every ESPR
    # delegated act, including textiles (product group 467), and it was absent.
    _src("jrc_product_bureau", "research", "microscope", _A, "JRC Product Bureau",
         "Ecodesign and Ecolabel preparatory studies by product group: the technical "
         "evidence base behind ESPR delegated acts, including textiles and apparel",
         "https://susproc.jrc.ec.europa.eu/product-bureau/product-groups",
         "https://susproc.jrc.ec.europa.eu/product-bureau/product-groups",
         ["ecodesign", "product", "circular", "textile", "environment", "energy"]),
    _src("knowledge4policy", "research", "lightbulb", _A, "JRC Knowledge Centres",
         "Science-for-policy knowledge centres and observatories (bioeconomy, migration, food security, cancer, disaster risk and more)",
         "https://knowledge4policy.ec.europa.eu/", "https://knowledge4policy.ec.europa.eu/search?text={q}", ["*"]),
    _src("op_catalogue", "research", "library", _B, "EU Publications catalogue",
         "The Publications Office catalogue: the whole EU institutional publication corpus, across every department",
         "https://op.europa.eu/en/web/general-publications/publications",
         "https://op.europa.eu/en/search-results?queryText={q}", ["*"]),
    _src("data_europa", "research", "chart", _A, "EU Data studies",
         "data.europa.eu analytical studies and data stories on open data, the data economy and data spaces",
         "https://data.europa.eu/en/publications/studies",
         "https://data.europa.eu/data/datasets?query={q}", ["digital", "data", "tech"]),

    # ---- Commission departments & research executive agencies ----
    # Native page feeds (clean /node/N/rss_en):
    _src("grow", "department", "factory", _O, "DG GROW",
         "Single-market and industrial studies, periodic reports and the Chief Economist's Single Market Economic Papers",
         "https://single-market-economy.ec.europa.eu/publications_en",
         "https://single-market-economy.ec.europa.eu/publications_en",
         ["single market", "industr", "sme", "compet", "internal market"],
         feed_landing="https://single-market-economy.ec.europa.eu/publications_en"),
    _src("mare", "department", "anchor", _A, "DG MARE",
         "Fisheries and maritime affairs: reports, studies, evaluations and STECF-linked science",
         "https://oceans-and-fisheries.ec.europa.eu/publications-list_en",
         "https://oceans-and-fisheries.ec.europa.eu/publications-list_en",
         ["fisher", "maritim", "ocean", "blue econ", "aquacult"],
         feed_landing="https://oceans-and-fisheries.ec.europa.eu/publications-list_en"),
    _src("env", "department", "leaf", _G, "DG ENV",
         "Environment: reports, guidance and studies on nature, pollution, water, waste and the circular economy",
         "https://environment.ec.europa.eu/publications_en",
         "https://environment.ec.europa.eu/publications_en",
         ["environ", "nature", "biodiv", "pollution", "circular", "water", "waste"],
         feed_landing="https://environment.ec.europa.eu/publications_en"),
    _src("empl", "department", "account-group", _R, "DG EMPL",
         "Employment and social affairs: labour-market analysis, studies, expert opinions and periodic reports",
         "https://employment-social-affairs.ec.europa.eu/publications_en",
         "https://employment-social-affairs.ec.europa.eu/publications_en",
         ["employ", "social", "labour", "skills", "work"],
         feed_landing="https://employment-social-affairs.ec.europa.eu/publications_en"),
    _src("home", "department", "shield", _R, "DG HOME",
         "Migration and home affairs: studies, factsheets and reports on migration, asylum, borders and security",
         "https://home-affairs.ec.europa.eu/whats-new/publications_en",
         "https://home-affairs.ec.europa.eu/whats-new/publications_en",
         ["migrat", "asylum", "border", "security", "home affairs", "radical"],
         feed_landing="https://home-affairs.ec.europa.eu/whats-new/publications_en"),
    _src("sante", "department", "hospital", _G, "DG SANTE",
         "Public health and food safety: health reports, indicators and country profiles",
         "https://health.ec.europa.eu/publications_en",
         "https://health.ec.europa.eu/publications_en",
         ["health", "pharma", "medicine", "food safety", "cancer", "disease"],
         feed_landing="https://health.ec.europa.eu/publications_en"),
    _src("hera", "department", "medical", _R, "HERA",
         "Health Emergency Preparedness and Response Authority: factsheets and reports on medical countermeasures",
         "https://health.ec.europa.eu/health-emergency-preparedness-and-response-hera/hera-publications_en",
         "https://health.ec.europa.eu/health-emergency-preparedness-and-response-hera/hera-publications_en",
         ["health", "emergency", "pandemic", "preparedness", "medical countermeasure"],
         feed_landing="https://health.ec.europa.eu/health-emergency-preparedness-and-response-hera/hera-publications_en"),
    _src("rea", "department", "rocket", _A, "REA",
         "Research Executive Agency: brochures, reports and results across Horizon clusters and missions",
         "https://rea.ec.europa.eu/publications_en", "https://rea.ec.europa.eu/publications_en",
         ["research", "horizon", "innovation"],
         feed_landing="https://rea.ec.europa.eu/publications_en"),
    # Central corporate-body feeds (DGs without a clean native feed):
    _src("ecfin", "department", "chart", _A, "DG ECFIN",
         "European Economy series: discussion and institutional papers, economic briefs and the economic forecasts",
         "https://economy-finance.ec.europa.eu/ecfin-publications_en",
         "https://economy-finance.ec.europa.eu/ecfin-publications_en",
         ["econom", "financ", "fiscal", "euro", "budget", "monetary"], cb_code="ECFIN"),
    _src("cnect", "department", "chip", _P, "DG CNECT",
         "Shaping Europe's Digital Future: reports, studies and factsheets on digital policy",
         "https://digital-strategy.ec.europa.eu/en/library",
         "https://digital-strategy.ec.europa.eu/en/search?text={q}",
         ["digital", "tech", "ai", "telecom", "cyber", "data", "connect"], cb_code="CNECT"),
    _src("ener", "department", "flash", _O, "DG ENER",
         "Energy: policy publications, market analysis and ecodesign final and preparatory studies",
         "https://energy.ec.europa.eu/resources/energy-publications_en",
         "https://energy.ec.europa.eu/resources/energy-publications_en",
         ["energy", "electric", "gas", "renewable", "nuclear", "grid"], cb_code="ENER"),
    _src("clima", "department", "earth", _G, "DG CLIMA",
         "Climate action: reports and studies on emissions, carbon markets and climate adaptation",
         "https://climate.ec.europa.eu/citizens-stakeholders/publications_en",
         "https://climate.ec.europa.eu/citizens-stakeholders/publications_en",
         ["climate", "emission", "carbon", "ets", "cbam", "adaptation"], cb_code="CLIMA"),
    _src("comp", "department", "scale", _P, "DG COMP",
         "Competition: policy briefs, ex-post evaluations, market studies and annual reports",
         "https://competition-policy.ec.europa.eu/publications_en",
         "https://competition-policy.ec.europa.eu/publications_en",
         ["competition", "state aid", "antitrust", "merger", "cartel"], cb_code="COMP"),
    _src("move", "department", "train", _O, "DG MOVE",
         "Mobility and transport: transport studies, market observation and research-and-innovation outputs",
         "https://transport.ec.europa.eu/transport-themes/research-and-innovation_en",
         "https://transport.ec.europa.eu/transport-themes/research-and-innovation_en",
         ["transport", "mobility", "rail", "aviation", "road", "maritime transport"], cb_code="MOVE"),
    _src("taxud", "department", "percent", _A, "DG TAXUD",
         "Taxation and customs: taxation papers, the annual report on taxation and taxation-trends data",
         "https://taxation-customs.ec.europa.eu/taxation/economic-analysis_en",
         "https://taxation-customs.ec.europa.eu/taxation/economic-analysis_en",
         ["tax", "taxation", "customs", "vat", "excise"], cb_code="TAXUD"),
    _src("trade", "department", "trade", _B, "DG TRADE",
         "Trade and economic security: trade studies, Chief Economist notes and ex-post evaluations",
         "https://policy.trade.ec.europa.eu/analysis-and-assessment_en",
         "https://policy.trade.ec.europa.eu/analysis-and-assessment_en",
         ["trade", "tariff", "export", "import", "trade defence"], cb_code="TRADE"),
    _src("intpa", "department", "handshake", _G, "DG INTPA",
         "International partnerships: development reports, evaluations and the knowledge hub",
         "https://international-partnerships.ec.europa.eu/publications_en",
         "https://international-partnerships.ec.europa.eu/publications_en",
         ["develop", "partnership", "external", "global gateway", "aid"], cb_code="INTPA"),
    _src("echo", "department", "lifebuoy", _R, "DG ECHO",
         "Civil protection and humanitarian aid: reports, studies and lessons-learned",
         "https://civil-protection-humanitarian-aid.ec.europa.eu/resources-campaigns/reports-studies-and-other-publications_en",
         "https://civil-protection-humanitarian-aid.ec.europa.eu/resources-campaigns/reports-studies-and-other-publications_en",
         ["humanitarian", "civil protection", "crisis", "disaster"], cb_code="ECHO"),
    # Card-only deep-links (no usable feed):
    _src("agri", "department", "sprout", _G, "DG AGRI",
         "Short- and medium-term agricultural outlook and market observatories (data on agridata.ec.europa.eu)",
         "https://agriculture.ec.europa.eu/data-and-analysis/markets/outlook_en",
         "https://agriculture.ec.europa.eu/news_en?keywords={q}",
         ["agri", "food", "rural", "cap", "farm"]),
    _src("regio", "department", "map", _O, "DG REGIO",
         "Cohesion and regional-policy evidence: Cohesion Reports and evaluation studies",
         "https://ec.europa.eu/regional_policy/policy/analysis/reports_en",
         "https://ec.europa.eu/regional_policy/en/information/publications",
         ["region", "cohesion", "territor", "urban"]),
    _src("erc", "department", "atom", _B, "ERC",
         "European Research Council: thematic, monitoring and mapping reports on frontier research",
         "https://erc.europa.eu/news-events/erc-publications",
         "https://erc.europa.eu/news-events/erc-publications",
         ["research", "frontier", "science", "innovation"]),
    _src("eacea", "department", "school", _P, "EACEA / Eurydice",
         "Education, audiovisual and culture: Eurydice analyses and Erasmus+ / Creative Europe studies",
         "https://www.eacea.ec.europa.eu/publications-0_en",
         "https://www.eacea.ec.europa.eu/publications-0_en",
         ["education", "culture", "youth", "sport", "erasmus"]),
    # External action via Cellar SPARQL (EEAS is not in the Commission central feed).
    _src("eeas", "department", "earth", _B, "EEAS",
         "European External Action Service: joint communications, joint reports and external-action documents on EU foreign and security policy",
         "https://www.eeas.europa.eu/eeas/annual-reports_en",
         "https://www.eeas.europa.eu/search_en?fulltext={q}",
         ["external", "foreign", "security", "defence", "enlargement", "neighbourhood",
          "sanctions", "diploma", "global gateway", "trade"],
         sparql_cb="EEAS"),

    # ---- Economic & financial supervision ----
    # Read Brubru's canonical economy_items layer (the api/v2/eu-financial-institutions
    # folders + scripts/sync_economy.py, migration 119) for item_type=publication.
    # One maintained source of truth, with full bodies; we just filter admin noise.
    _src("ecb", "research", "bank", _B, "ECB",
         "European Central Bank research: Working Papers, Occasional Papers, the Economic Bulletin and the Financial Stability Review",
         "https://www.ecb.europa.eu/press/research-publications/html/index.en.html",
         "https://www.ecb.europa.eu/search/search/html/index.en.html?searchterm={q}",
         ["econom", "financ", "monetary", "bank", "euro", "inflation", "interest rate", "fiscal"],
         economy_body="ecb"),
    _src("ecb_ssm", "research", "shield", _A, "ECB Banking Supervision",
         "ECB Banking Supervision (Single Supervisory Mechanism): supervisory reports, good-practice guides, supervisory banking statistics and the annual report on supervisory activities",
         "https://www.bankingsupervision.europa.eu/press/publications/html/index.en.html",
         "https://www.bankingsupervision.europa.eu/search/html/index.en.html?searchterm={q}",
         ["bank", "supervis", "prudential", "financ", "ssm", "capital", "credit", "risk"],
         economy_body="ecb_ssm"),
    _src("esma", "research", "chart", _P, "ESMA",
         "European Securities and Markets Authority: reports, technical standards, guidelines and risk assessments on EU securities markets",
         "https://www.esma.europa.eu/document-library",
         "https://www.esma.europa.eu/search?search_api_fulltext={q}",
         ["market", "securit", "financ", "invest", "fund", "trading", "capital market", "mifid"],
         economy_body="esma"),
    _src("esrb", "research", "scale", _R, "ESRB",
         "European Systemic Risk Board: macroprudential recommendations, warnings and reports on systemic risk and financial stability",
         "https://www.esrb.europa.eu/pub/html/index.en.html",
         "https://www.esrb.europa.eu/home/search/html/index.en.html?searchterm={q}",
         ["systemic risk", "financ", "macroprudential", "stability", "bank", "risk", "econom"],
         sparql_cb="ESRB"),   # ESRB is not in economy_items; keep Cellar
    _src("eba", "research", "bank", _O, "EBA",
         "European Banking Authority: reports, guidelines, technical standards (ITS/RTS), consultation papers and EU-wide stress-test results",
         "https://www.eba.europa.eu/publications-and-media/publications",
         "https://www.eba.europa.eu/search-results?text={q}",
         ["bank", "financ", "credit", "capital", "prudential", "basel", "stress test", "risk"],
         economy_body="eba"),
    _src("eiopa", "research", "lifebuoy", _G, "EIOPA",
         "European Insurance and Occupational Pensions Authority: reports, studies, consultations and risk dashboards on insurance and pensions",
         "https://www.eiopa.europa.eu/publications_en",
         "https://www.eiopa.europa.eu/search_en?search_api_fulltext={q}",
         ["insur", "pension", "financ", "occupational", "solvency", "risk"],
         economy_body="eiopa"),
]


def _http(url: str, timeout: int = 15) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=timeout) as r:
        return r.read()


def _discover_rss(landing: str) -> Optional[str]:
    """Find the /node/<N>/rss_en feed link on an EC publications page. Cached."""
    now = time.time()
    hit = _rss_cache.get(landing)
    if hit and hit[0] > now:
        return hit[1]
    rss = None
    try:
        html = _http(landing).decode("utf-8", "replace")
        m = re.search(r'href="([^"]*node/\d+/rss_en[^"]*)"', html)
        if m:
            rss = urllib.parse.urljoin(landing, m.group(1).replace("&amp;", "&"))
    except Exception as e:
        logger.warning("[research] rss discovery failed for %s: %s", landing, e)
    _rss_cache[landing] = (now + _TTL, rss)
    return rss


def _cb_feed_url(code: str) -> str:
    return f"{_CENTRAL_FEED}?f%5B0%5D=oe_publication_authors:skos_concept|{_CB}{code}"


def _strip(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()


# Some EU feeds (notably the ECB) emit bare ampersands ("R&D") which are invalid
# XML. Escape any & that is not already part of a character/entity reference.
_BARE_AMP = re.compile(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)")
_DC = "{http://purl.org/dc/elements/1.1/}"


def fetch_feed(feed_url: str, limit: int = 12) -> List[dict]:
    """Parse an RSS feed into recent items (admin noise filtered out). Cached."""
    now = time.time()
    hit = _feed_cache.get(feed_url)
    if hit and hit[0] > now:
        return hit[1]
    items: List[dict] = []
    try:
        xml = _BARE_AMP.sub("&amp;", _http(feed_url).decode("utf-8", "replace"))
        root = ET.fromstring(xml)
        for it in root.iter("item"):
            def gx(tag: str) -> str:
                el = it.find(tag)
                return (el.text or "").strip() if el is not None else ""
            title = _strip(gx("title"))
            link = gx("link") or gx("guid")
            if not (title and link) or _ADMIN_RE.match(title):
                continue
            date = gx("pubDate") or gx(f"{_DC}date") or gx("date") or gx("published")
            items.append({"title": title, "url": link, "date": date,
                          "snippet": _strip(gx("description"))[:240]})
            if len(items) >= limit:
                break
    except Exception as e:
        logger.warning("[research] feed parse failed for %s: %s", feed_url, e)
    _feed_cache[feed_url] = (now + 1800, items)
    return items


_SPARQL = "http://publications.europa.eu/webapi/rdf/sparql"


def fetch_cellar_works(cb_code: str, limit: int = 12) -> List[dict]:
    """Recent works authored by a corporate body, via Cellar SPARQL (no WAF).

    Used for EU bodies absent from the Commission central publications feed
    (e.g. EEAS). Each work links to its public EUR-Lex page by CELEX. Cached.
    """
    import json as _json
    now = time.time()
    key = f"cellar:{cb_code}"
    hit = _feed_cache.get(key)
    if hit and hit[0] > now:
        return hit[1]
    q = (
        "PREFIX cdm:<http://publications.europa.eu/ontology/cdm#> "
        "SELECT DISTINCT ?title ?date ?celex ?w WHERE { "
        f"?w cdm:work_created_by_agent <{_CB}{cb_code}> . "
        "?expr cdm:expression_belongs_to_work ?w ; cdm:expression_title ?title ; "
        "cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/ENG> . "
        "OPTIONAL { ?w cdm:resource_legal_id_celex ?celex } "
        "OPTIONAL { ?w cdm:work_date_creation_legacy ?date } "
        f"}} ORDER BY DESC(?date) LIMIT {int(limit)}"
    )
    url = (_SPARQL + "?query=" + urllib.parse.quote(q)
           + "&format=" + urllib.parse.quote("application/sparql-results+json"))
    items: List[dict] = []
    try:
        data = _json.loads(_http(url, timeout=30))
        seen = set()
        for b in data.get("results", {}).get("bindings", []):
            title = _strip(b.get("title", {}).get("value", ""))
            if not title or title in seen or _ADMIN_RE.match(title):
                continue
            seen.add(title)
            celex = (b.get("celex") or {}).get("value")
            link = (f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"
                    if celex else (b.get("w") or {}).get("value", ""))
            items.append({"title": title, "url": link,
                          "date": (b.get("date") or {}).get("value", ""), "snippet": ""})
    except Exception as e:
        logger.warning("[research] cellar SPARQL failed for %s: %s", cb_code, e)
    _feed_cache[key] = (now + _TTL, items)
    return items


_DATE_TXT = re.compile(r"\d{1,2}\s+[A-Za-z]+\s+20\d{2}|\d{2}[/.]\d{2}[/.]20\d{2}")
# Operational noise that can appear MID-title (so ^-anchored _ADMIN_RE misses it):
# "EBA - SB Composition", "...meeting minutes", "Agenda workshop on...".
_NOISE_RE = re.compile(r"\b(meeting minutes|\bminutes\b|sb composition|board composition|"
                       r"workshop|meeting agenda|list of participants)\b", re.I)


def _scrape_html_list(cfg: dict, limit: int = 12) -> List[dict]:
    """Scrape a server-rendered (no-WAF) publications list via CSS selectors.

    cfg = {url, item, title, date}. Admin/operational titles are filtered out.
    Cached. Used for bodies whose research is on-site, not in Cellar or RSS.
    """
    from bs4 import BeautifulSoup
    url = cfg["url"]
    now = time.time()
    key = f"scrape:{url}"
    hit = _feed_cache.get(key)
    if hit and hit[0] > now:
        return hit[1]
    items: List[dict] = []
    try:
        soup = BeautifulSoup(_http(url, timeout=20).decode("utf-8", "replace"), "html.parser")
        seen = set()
        for card in soup.select(cfg["item"]):
            a = card.select_one(cfg["title"])
            if not a or not a.get("href"):
                continue
            title = a.get_text(" ", strip=True)
            href = urllib.parse.urljoin(url, a["href"])
            if (not title or len(title) < 12 or href in seen
                    or _ADMIN_RE.match(title) or _NOISE_RE.search(title)):
                continue
            seen.add(href)
            de = card.select_one(cfg["date"]) if cfg.get("date") else None
            dm = _DATE_TXT.search(de.get_text(" ", strip=True)) if de else None
            items.append({"title": title[:300], "url": href,
                          "date": dm.group(0) if dm else "", "snippet": ""})
            if len(items) >= limit:
                break
    except Exception as e:
        logger.warning("[research] scrape failed for %s: %s", url, e)
    _feed_cache[key] = (now + _TTL, items)
    return items


def _fetch_economy_publications(body_code: str, limit: int = 12) -> List[dict]:
    """Read item_type=publication for a body from Brubru's canonical economy_items
    table (the api/v2/eu-financial-institutions layer, kept fresh by
    scripts/sync_economy.py). Admin/operational noise is filtered out. Cached.
    """
    from sqlalchemy import text
    from core.database import SessionLocal
    now = time.time()
    key = f"economy:{body_code}"
    hit = _feed_cache.get(key)
    if hit and hit[0] > now:
        return hit[1]
    items: List[dict] = []
    db = SessionLocal()
    try:
        rows = db.execute(text(
            "SELECT title, public_url, document_date, summary FROM economy_items "
            "WHERE body_code = :bc AND item_type = 'publication' "
            "ORDER BY document_date DESC NULLS LAST, id DESC LIMIT :lim"
        ), {"bc": body_code, "lim": limit * 4}).fetchall()
    except Exception as e:
        logger.warning("[research] economy_items read failed for %s: %s", body_code, e)
        rows = []
    finally:
        db.close()
    for r in rows:
        title = (r.title or "").strip()
        if not title or len(title) < 12 or _ADMIN_RE.match(title) or _NOISE_RE.search(title):
            continue
        items.append({
            "title": title[:300],
            "url": r.public_url or "",
            "date": r.document_date.strftime("%d %B %Y") if r.document_date else "",
            "snippet": _strip(r.summary or "")[:240],
        })
        if len(items) >= limit:
            break
    _feed_cache[key] = (now + 1800, items)
    return items


def _is_pi_match(src: dict, pi_lower: List[str]) -> bool:
    tags = src.get("pi_tags") or []
    if "*" in tags:
        return True
    return any(t in p or p in t for t in tags for p in pi_lower if p)


def _seed_search(src: dict, pi: List[str]) -> str:
    tmpl = src.get("search") or src.get("landing")
    if "{q}" not in tmpl:
        return tmpl
    chosen = ""
    for tag in src.get("pi_tags", []):
        if tag == "*":
            continue
        for p in pi:
            if tag in p.lower() or p.lower() in tag:
                chosen = p
                break
        if chosen:
            break
    if not chosen and pi:
        chosen = pi[0]
    # A policy-interest LABEL is a heading, not a search term. Seeding a
    # repository search with "Ecodesign of sustainable products / Digital
    # product passport", slash and all, returns nothing on JRC or CORDIS. The
    # taxonomy already carries a curated keyword list per interest whose first
    # entry is the concise form: ecodesign, environment, climate, digital.
    if chosen:
        try:
            from services.tracking.pi_committee_crosswalk import PI_TO_KEYWORDS

            kws = PI_TO_KEYWORDS.get(chosen.strip()) or []
            if kws:
                chosen = kws[0]
        except Exception:  # noqa: BLE001 - a bad seed must never break the page
            pass
    return tmpl.replace("{q}", urllib.parse.quote(chosen))


def build_catalogue(pi: List[str]) -> dict:
    """Return the curated source cards, PI-annotated and PI-seeded."""
    pi_lower = [p.lower() for p in (pi or [])]
    order = {"foresight": 0, "research": 1, "department": 2}
    out = []
    for s in SOURCES:
        out.append({
            "id": s["id"], "group": s["group"], "icon": s["icon"], "color": s["color"],
            "name": s["name"], "full": s["full"], "landing": s["landing"],
            "search": _seed_search(s, pi),
            "has_feed": bool(s.get("feed_landing") or s.get("cb_code") or s.get("sparql_cb")
                             or s.get("rss_url") or s.get("scrape_cfg") or s.get("economy_body")),
            "is_pi_match": _is_pi_match(s, pi_lower),
        })
    # group order, then PI matches first within a group.
    out.sort(key=lambda x: (order.get(x["group"], 9), not x["is_pi_match"], x["name"]))
    return {"pi_active": bool(pi_lower), "count": len(out), "sources": out}


def read_through(source_id: str, limit: int = 12) -> List[dict]:
    """Live read-through of a source's publications feed (no storage)."""
    src = next((s for s in SOURCES if s["id"] == source_id), None)
    if not src:
        return []
    if src.get("feed_landing"):
        rss = _discover_rss(src["feed_landing"])
        return fetch_feed(rss, limit) if rss else []
    if src.get("cb_code"):
        return fetch_feed(_cb_feed_url(src["cb_code"]), limit)
    if src.get("economy_body"):
        return _fetch_economy_publications(src["economy_body"], limit)
    if src.get("rss_url"):
        return fetch_feed(src["rss_url"], limit)
    if src.get("sparql_cb"):
        return fetch_cellar_works(src["sparql_cb"], limit)
    if src.get("scrape_cfg"):
        return _scrape_html_list(src["scrape_cfg"], limit)
    return []

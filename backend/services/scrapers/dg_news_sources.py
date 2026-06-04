"""
Registry of European Commission hub / DG / agency NEWS URLs to aggregate into
MEUB "News" (from docs/new_format/prompt_new_format.md, lines 137-381).

Each entry: url, institution, dg (canonical DG code or None), default_type
(news|publication|story|press), and an optional agency code for provenance.

The DG newsrooms share the EC Drupal "content item" markup (ecl-content-item with
an image, a <time datetime>, a title link and a description) -> one generic parser
(dg_news_scraper.parse_ecl_news), normal browser-UA HTTP, no WAF. presscorner /
newsletter-archives / data.europa.eu / cordis use different markup -> best-effort
(logged, not silently dropped).
"""

DG_NEWS_SOURCES = [
    # --- Commission hub ---
    {"url": "https://commission.europa.eu/news-and-media/news_en", "institution": "COMMISSION", "dg": None, "default_type": "news"},
    {"url": "https://commission.europa.eu/news-and-media/highlighted-news_en", "institution": "COMMISSION", "dg": None, "default_type": "news"},
    {"url": "https://ec.europa.eu/commission/presscorner/home/en", "institution": "COMMISSION", "dg": None, "default_type": "press"},

    # --- Per-DG newsrooms (ECL) ---
    {"url": "https://agriculture.ec.europa.eu/media/news_en", "institution": "COMMISSION", "dg": "AGRI", "default_type": "news"},
    {"url": "https://agriculture.ec.europa.eu/media/stories_en", "institution": "COMMISSION", "dg": "AGRI", "default_type": "story"},
    {"url": "https://climate.ec.europa.eu/news-your-voice/news_en?f%5B0%5D=news_type_news_type%3A1", "institution": "COMMISSION", "dg": "CLIMA", "default_type": "news"},
    {"url": "https://climate.ec.europa.eu/news-other-reads/stories_en", "institution": "COMMISSION", "dg": "CLIMA", "default_type": "story"},
    {"url": "https://digital-strategy.ec.europa.eu/en/news", "institution": "COMMISSION", "dg": "CNECT", "default_type": "news"},
    {"url": "https://competition-policy.ec.europa.eu/about/news_en", "institution": "COMMISSION", "dg": "COMP", "default_type": "news"},
    {"url": "https://competition-policy.ec.europa.eu/antitrust-and-cartels/latest-news_en", "institution": "COMMISSION", "dg": "COMP", "default_type": "news"},
    {"url": "https://competition-policy.ec.europa.eu/mergers/latest-news_en", "institution": "COMMISSION", "dg": "COMP", "default_type": "news"},
    {"url": "https://competition-policy.ec.europa.eu/state-aid/latest-news_en", "institution": "COMMISSION", "dg": "COMP", "default_type": "news"},
    {"url": "https://digital-markets-act.ec.europa.eu/latest-news_en", "institution": "COMMISSION", "dg": "COMP", "default_type": "news"},
    {"url": "https://defence-industry-space.ec.europa.eu/newsroom/latest-news_en", "institution": "COMMISSION", "dg": "DEFIS", "default_type": "news"},
    {"url": "https://eu-space.europa.eu/explore-euspace/news/recent", "institution": "COMMISSION", "dg": "DEFIS", "default_type": "news"},
    {"url": "https://www.copernicus.eu/en/news/news", "institution": "COMMISSION", "dg": "DEFIS", "default_type": "news"},
    {"url": "https://commission.europa.eu/news_en?f%5B0%5D=departments_departments%3Ahttp%3A//publications.europa.eu/resource/authority/corporate-body/DIGIT", "institution": "COMMISSION", "dg": "DIGIT", "default_type": "news"},
    {"url": "https://economy-finance.ec.europa.eu/ecfin-news_en", "institution": "COMMISSION", "dg": "ECFIN", "default_type": "news"},
    {"url": "https://economy-finance.ec.europa.eu/ecfin-publications_en", "institution": "COMMISSION", "dg": "ECFIN", "default_type": "publication"},
    {"url": "https://employment-social-affairs.ec.europa.eu/news_en", "institution": "COMMISSION", "dg": "EMPL", "default_type": "news"},
    {"url": "https://employment-social-affairs.ec.europa.eu/publications_en", "institution": "COMMISSION", "dg": "EMPL", "default_type": "publication"},
    {"url": "https://energy.ec.europa.eu/news_en", "institution": "COMMISSION", "dg": "ENER", "default_type": "news"},
    {"url": "https://energy.ec.europa.eu/resources/energy-publications_en", "institution": "COMMISSION", "dg": "ENER", "default_type": "publication"},
    {"url": "https://enlargement.ec.europa.eu/news_en", "institution": "COMMISSION", "dg": "ENEST", "default_type": "news"},
    {"url": "https://environment.ec.europa.eu/news_en", "institution": "COMMISSION", "dg": "ENV", "default_type": "news"},
    {"url": "https://environment.ec.europa.eu/stories_en", "institution": "COMMISSION", "dg": "ENV", "default_type": "story"},
    {"url": "https://environment.ec.europa.eu/publications_en", "institution": "COMMISSION", "dg": "ENV", "default_type": "publication"},
    {"url": "https://anti-fraud.ec.europa.eu/media-corner/news_en", "institution": "COMMISSION", "dg": "OLAF", "default_type": "news"},
    {"url": "https://civil-protection-humanitarian-aid.ec.europa.eu/news-stories/news_en", "institution": "COMMISSION", "dg": "ECHO", "default_type": "news"},
    {"url": "https://ec.europa.eu/eurostat/news", "institution": "COMMISSION", "dg": "ESTAT", "default_type": "news"},
    {"url": "https://finance.ec.europa.eu/finance-news_en", "institution": "COMMISSION", "dg": "FISMA", "default_type": "news"},
    {"url": "https://fpi.ec.europa.eu/news_en", "institution": "COMMISSION", "dg": "FPI", "default_type": "news"},
    {"url": "https://fpi.ec.europa.eu/stories_en", "institution": "COMMISSION", "dg": "FPI", "default_type": "story"},
    {"url": "https://food.ec.europa.eu/food-safety-news_en", "institution": "COMMISSION", "dg": "SANTE", "default_type": "news"},
    {"url": "https://health.ec.europa.eu/latest-updates_en", "institution": "COMMISSION", "dg": "SANTE", "default_type": "news"},
    {"url": "https://health.ec.europa.eu/health-emergency-preparedness-and-response-hera/latest-updates_en", "institution": "COMMISSION", "dg": "HERA", "default_type": "news"},
    {"url": "https://single-market-economy.ec.europa.eu/news_en", "institution": "COMMISSION", "dg": "GROW", "default_type": "news"},
    {"url": "https://single-market-economy.ec.europa.eu/publications_en", "institution": "COMMISSION", "dg": "GROW", "default_type": "publication"},
    {"url": "https://international-partnerships.ec.europa.eu/news-and-events/news_en", "institution": "COMMISSION", "dg": "INTPA", "default_type": "news"},
    {"url": "https://international-partnerships.ec.europa.eu/news-and-events/stories_en", "institution": "COMMISSION", "dg": "INTPA", "default_type": "story"},
    {"url": "https://joint-research-centre.ec.europa.eu/news-announcements_en", "institution": "COMMISSION", "dg": "JRC", "default_type": "news"},
    {"url": "https://joint-research-centre.ec.europa.eu/jrc-explains_en", "institution": "COMMISSION", "dg": "JRC", "default_type": "story"},
    {"url": "https://commission.europa.eu/news-and-media/news_en?f%5B0%5D=oe_news_departments%3Ahttp%3A//publications.europa.eu/resource/authority/corporate-body/JUST", "institution": "COMMISSION", "dg": "JUST", "default_type": "news"},
    {"url": "https://oceans-and-fisheries.ec.europa.eu/news_en", "institution": "COMMISSION", "dg": "MARE", "default_type": "news"},
    {"url": "https://north-africa-middle-east-gulf.ec.europa.eu/about-us/latest-news_en", "institution": "COMMISSION", "dg": "MENA", "default_type": "news"},
    {"url": "https://home-affairs.ec.europa.eu/whats-new/news_en", "institution": "COMMISSION", "dg": "HOME", "default_type": "news"},
    {"url": "https://home-affairs.ec.europa.eu/whats-new/publications_en", "institution": "COMMISSION", "dg": "HOME", "default_type": "publication"},
    {"url": "https://transport.ec.europa.eu/news-events/news_en", "institution": "COMMISSION", "dg": "MOVE", "default_type": "news"},
    {"url": "https://commission.europa.eu/about/departments-and-executive-agencies/reform-and-investment-task-force/latest_en", "institution": "COMMISSION", "dg": "REFORM", "default_type": "news"},
    {"url": "https://research-and-innovation.ec.europa.eu/news/news-alerts_en", "institution": "COMMISSION", "dg": "RTD", "default_type": "news"},
    {"url": "https://research-and-innovation.ec.europa.eu/knowledge-publications-tools-and-data/publications_en", "institution": "COMMISSION", "dg": "RTD", "default_type": "publication"},
    {"url": "https://taxation-customs.ec.europa.eu/news_en", "institution": "COMMISSION", "dg": "TAXUD", "default_type": "news"},
    {"url": "https://policy.trade.ec.europa.eu/news_en", "institution": "COMMISSION", "dg": "TRADE", "default_type": "news"},
    {"url": "https://translation.ec.europa.eu/news-and-events/news", "institution": "COMMISSION", "dg": "DGT", "default_type": "news"},
    {"url": "https://ec.europa.eu/regional_policy/policy/analysis/reports_en", "institution": "COMMISSION", "dg": "REGIO", "default_type": "publication"},

    # --- Executive agencies ---
    {"url": "https://cinea.ec.europa.eu/news-events/news_en", "institution": "COMMISSION", "dg": None, "agency": "CINEA", "default_type": "news"},
    {"url": "https://www.eacea.ec.europa.eu/news-events/news_en", "institution": "COMMISSION", "dg": None, "agency": "EACEA", "default_type": "news"},
    {"url": "https://hadea.ec.europa.eu/news_en", "institution": "COMMISSION", "dg": None, "agency": "HADEA", "default_type": "news"},
    {"url": "https://eismea.ec.europa.eu/news_en", "institution": "COMMISSION", "dg": None, "agency": "EISMEA", "default_type": "news"},
    {"url": "https://erc.europa.eu/news-events/news", "institution": "COMMISSION", "dg": None, "agency": "ERCEA", "default_type": "news"},
    {"url": "https://rea.ec.europa.eu/news_en", "institution": "COMMISSION", "dg": None, "agency": "REA", "default_type": "news"},
    {"url": "https://eu-careers.europa.eu/en/upcoming-selection-procedures", "institution": "COMMISSION", "dg": None, "agency": "EPSO", "default_type": "news"},

    # --- EU data / open data ---
    {"url": "https://data.europa.eu/en/news-events/news", "institution": "COMMISSION", "dg": None, "agency": "OP", "default_type": "news"},
    {"url": "https://cordis.europa.eu/news", "institution": "COMMISSION", "dg": "RTD", "default_type": "news"},
    {"url": "https://op.europa.eu/en/web/general-publications/just-published-2025", "institution": "COMMISSION", "dg": None, "agency": "OP", "default_type": "publication"},

    # ECL-parseable holdouts (1 Jun 2026). NB: the URL Victor gave for "ECHA" is
    # actually the EU portal's GENERAL featured-news (european-union.europa.eu),
    # not ECHA-specific -> tagged institution="EU"; ECHA proper still needs a feed.
    {"url": "https://european-union.europa.eu/news-and-events/featured-news_en", "institution": "EU", "dg": None, "default_type": "news"},
    {"url": "https://www.amla.europa.eu/news-media/news-articles_en", "institution": "AMLA", "dg": None, "default_type": "news"},
]


# ---------------------------------------------------------------------------
# Other EU institutions, authorities, agencies & bodies — via their RSS/Atom
# feeds (auto-discovered + verified to yield, 1 June 2026). "All the EU."
# institution = the body's acronym (free string in eu_news_items). kind='rss'.
# Feed-less bodies (EP, Council, EIB, ECA, CJEU, ECHA, ENISA, EUIPO, EMA, EUAA,
# Eurojust, FRA, EU-OSHA, Eurofound, ACER, ECDC, AMLA, CEPOL, EIT, CPVO, CdT)
# need per-site parsers (EP shipped in ep_news_scraper.py; others pending).
# ---------------------------------------------------------------------------
EU_BODY_FEEDS = [
    {"institution": "ECB", "url": "https://www.ecb.europa.eu/rss/press.html"},
    {"institution": "EFSA", "url": "https://www.efsa.europa.eu/en/press/rss"},
    {"institution": "EEA", "url": "https://www.eea.europa.eu/en/newsroom/rss-feeds/eeas-press-releases-rss/rss.xml"},
    {"institution": "EUROPOL", "url": "https://www.europol.europa.eu/rss"},
    {"institution": "FRONTEX", "url": "https://frontex.europa.eu/media-centre/news/news-release/feed"},
    {"institution": "EASA", "url": "https://www.easa.europa.eu/en/newsroom-and-events/news/feed.xml"},
    {"institution": "ERA", "url": "https://www.era.europa.eu/rss.xml"},
    {"institution": "EUSPA", "url": "https://www.euspa.europa.eu/pressroom/press-releases/rss.xml"},
    {"institution": "EUDA", "url": "https://www.euda.europa.eu/news/home/rss.xml"},
    {"institution": "EIGE", "url": "https://eige.europa.eu/newsroom/news/rss.xml"},
    {"institution": "CEDEFOP", "url": "https://www.cedefop.europa.eu/en/news.rss"},
    {"institution": "ETF", "url": "https://www.etf.europa.eu/rss.xml"},
    {"institution": "ELA", "url": "https://www.ela.europa.eu/rss.xml"},
    {"institution": "EFCA", "url": "https://www.efca.europa.eu/rss.xml"},
    {"institution": "EBA", "url": "https://www.eba.europa.eu/rss.xml"},
    {"institution": "ESMA", "url": "https://www.esma.europa.eu/rss.xml"},
    {"institution": "EIOPA", "url": "https://www.eiopa.europa.eu/node/4816/rss_en"},
    {"institution": "EULISA", "url": "https://www.eulisa.europa.eu/news-and-events.rss"},
    {"institution": "BEREC", "url": "https://www.berec.europa.eu/rss.xml"},
    {"institution": "SRB", "url": "https://www.srb.europa.eu/en/rss"},
    {"institution": "EESC", "url": "https://www.eesc.europa.eu/en/recent-content.rss"},
    {"institution": "EPPO", "url": "https://www.eppo.europa.eu/en/news.xml"},
    {"institution": "EMA", "url": "https://www.ema.europa.eu/en/news.xml"},
    {"institution": "EMSA", "url": "https://www.emsa.europa.eu/newsroom/latest-news.html?format=feed&type=rss"},
]
for _f in EU_BODY_FEEDS:
    _f.setdefault("dg", None)
    _f.setdefault("kind", "rss")
    _f.setdefault("default_type", "news")


# "EU bubble outlets" — independent media covering the EU bubble (institution=
# 'OUTLET'; a distinct News topic). Auto-updated via RSS like everything else.
# Contexte is paywalled (no public feed) -> not auto-ingestable without credentials.
OUTLET_FEEDS = [
    {"institution": "OUTLET", "source_key": "Politico Europe", "url": "https://www.politico.eu/feed/"},
    {"institution": "OUTLET", "source_key": "Euractiv", "url": "https://www.euractiv.com/feed/"},
    {"institution": "OUTLET", "source_key": "EU Observer", "url": "https://euobserver.com/rss"},
]
for _f in OUTLET_FEEDS:
    _f.setdefault("dg", None)
    _f.setdefault("kind", "rss")
    _f.setdefault("default_type", "news")

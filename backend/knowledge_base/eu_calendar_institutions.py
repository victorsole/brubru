"""
EU Calendar Institutions and Policy Area Definitions.

Static data for the My EU Calendar feature, defining institutions
with codes, names, MDI icons, colours, and calendar source URLs.

Also includes policy area mappings to EP committees and Council
configurations for cross-filtering.

Created: February 2026
"""

from typing import Dict, List, NamedTuple, Optional


# ============================================================================
# Institution Definitions
# ============================================================================

class EUInstitution(NamedTuple):
    """EU Institution definition for calendar display."""
    code: str
    name: str
    short_name: str
    mdi_icon: str
    colour: str
    calendar_url: Optional[str]


EU_INSTITUTIONS: List[EUInstitution] = [
    EUInstitution(
        code="EP",
        name="European Parliament",
        short_name="EP",
        mdi_icon="mdi-account-group",
        colour="#0693e3",
        calendar_url="https://www.europarl.europa.eu/plenary/en/agendas.html",
    ),
    EUInstitution(
        code="COUNCIL",
        name="Council of the EU",
        short_name="Council",
        mdi_icon="mdi-bank",
        colour="#059669",
        calendar_url="https://www.consilium.europa.eu/en/meetings/calendar/",
    ),
    EUInstitution(
        code="EUROPEAN_COUNCIL",
        name="European Council",
        short_name="European Council",
        mdi_icon="mdi-star-four-points",
        colour="#d97706",
        calendar_url="https://www.consilium.europa.eu/en/european-council/",
    ),
    EUInstitution(
        code="COMMISSION",
        name="European Commission",
        short_name="Commission",
        mdi_icon="mdi-domain",
        colour="#9b51e0",
        calendar_url="https://commission.europa.eu/strategy-and-policy/decision-making-process-commission/decision-making-during-weekly-meetings_en",
    ),
    EUInstitution(
        code="ECJ",
        name="Court of Justice of the EU",
        short_name="ECJ",
        mdi_icon="mdi-gavel",
        colour="#dc2626",
        calendar_url="https://curia.europa.eu/site/jcms/d2_5117/en/judicial-calendar",
    ),
    EUInstitution(
        code="ECB",
        name="European Central Bank",
        short_name="ECB",
        mdi_icon="mdi-currency-eur",
        colour="#0369a1",
        calendar_url="https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html",
    ),
    EUInstitution(
        code="ESMA",
        name="European Securities and Markets Authority",
        short_name="ESMA",
        mdi_icon="mdi-chart-line",
        colour="#7c3aed",
        calendar_url="https://www.esma.europa.eu/press-news/key-dates",
    ),
    EUInstitution(
        code="EMA",
        name="European Medicines Agency",
        short_name="EMA",
        mdi_icon="mdi-pill",
        colour="#0d9488",
        calendar_url="https://www.ema.europa.eu/en/events/upcoming-events",
    ),
    EUInstitution(
        code="EBA",
        name="European Banking Authority",
        short_name="EBA",
        mdi_icon="mdi-cash",
        colour="#b45309",
        calendar_url="https://www.eba.europa.eu/publications-and-media/events",
    ),
    EUInstitution(
        code="EIOPA",
        name="European Insurance and Occupational Pensions Authority",
        short_name="EIOPA",
        mdi_icon="mdi-shield-check",
        colour="#6366f1",
        calendar_url="https://www.eiopa.europa.eu/agenda_en",
    ),
    EUInstitution(
        code="COR",
        name="European Committee of the Regions",
        short_name="CoR",
        mdi_icon="mdi-map-marker-multiple",
        colour="#e11d48",
        calendar_url="https://cor.europa.eu/en/plenaries-events/plenary-sessions",
    ),
    EUInstitution(
        code="EESC",
        name="European Economic and Social Committee",
        short_name="EESC",
        mdi_icon="mdi-handshake",
        colour="#4f46e5",
        calendar_url="https://www.eesc.europa.eu/en/agenda",
    ),
    # All-EU bodies added 1 Jun 2026 for MEUB My EU Calendar event ingestion
    # (migration 102). These ARE the body (no sub-departments).
    EUInstitution(code="EDPS", name="European Data Protection Supervisor", short_name="EDPS",
        mdi_icon="mdi-shield-lock", colour="#0ea5e9",
        calendar_url="https://www.edps.europa.eu/about-edps/members-mission/agenda_en"),
    EUInstitution(code="OMBUDSMAN", name="European Ombudsman", short_name="Ombudsman",
        mdi_icon="mdi-scale-balance", colour="#0d9488",
        calendar_url="https://www.ombudsman.europa.eu/en/calendar/our-events"),
    EUInstitution(code="EIB", name="European Investment Bank", short_name="EIB",
        mdi_icon="mdi-bank", colour="#1d4ed8",
        calendar_url="https://www.eib.org/en/events/index"),
    EUInstitution(code="ECA", name="European Court of Auditors", short_name="ECA",
        mdi_icon="mdi-clipboard-check", colour="#7c3aed",
        calendar_url="https://www.eca.europa.eu/en/events"),
    EUInstitution(code="ECHA", name="European Chemicals Agency", short_name="ECHA",
        mdi_icon="mdi-flask", colour="#ca8a04",
        calendar_url="https://echa.europa.eu/events/"),
    EUInstitution(code="ENISA", name="European Union Agency for Cybersecurity", short_name="ENISA",
        mdi_icon="mdi-lock-check", colour="#2563eb",
        calendar_url="https://www.enisa.europa.eu/events"),
    EUInstitution(code="EUIPO", name="European Union Intellectual Property Office", short_name="EUIPO",
        mdi_icon="mdi-copyright", colour="#db2777",
        calendar_url="https://www.euipo.europa.eu/en/news-and-events/events"),
    EUInstitution(code="EUAA", name="European Union Agency for Asylum", short_name="EUAA",
        mdi_icon="mdi-account-group", colour="#0891b2",
        calendar_url="https://www.euaa.europa.eu/key-words/events"),
    EUInstitution(code="EUROJUST", name="EU Agency for Criminal Justice Cooperation", short_name="Eurojust",
        mdi_icon="mdi-gavel", colour="#9333ea",
        calendar_url="https://www.eurojust.europa.eu/media-and-events/public-events"),
    EUInstitution(code="FRA", name="EU Agency for Fundamental Rights", short_name="FRA",
        mdi_icon="mdi-human-greeting", colour="#16a34a",
        calendar_url="https://fra.europa.eu/en/news-and-events/upcoming-events"),
    EUInstitution(code="EU_OSHA", name="European Agency for Safety and Health at Work", short_name="EU-OSHA",
        mdi_icon="mdi-hard-hat", colour="#ea580c",
        calendar_url="https://osha.europa.eu/en/oshevents"),
    EUInstitution(code="EUROFOUND", name="European Foundation for Living and Working Conditions", short_name="Eurofound",
        mdi_icon="mdi-briefcase", colour="#0284c7",
        calendar_url="https://www.eurofound.europa.eu/en/news-and-events/all-events?contentType=upcoming"),
    EUInstitution(code="ACER", name="EU Agency for the Cooperation of Energy Regulators", short_name="ACER",
        mdi_icon="mdi-flash", colour="#d97706",
        calendar_url="https://www.acer.europa.eu/public-events"),
    EUInstitution(code="ECDC", name="European Centre for Disease Prevention and Control", short_name="ECDC",
        mdi_icon="mdi-virus", colour="#dc2626",
        calendar_url="https://www.ecdc.europa.eu/en/about-ecdc/work-ecdc/meetings-and-visits-ecdc"),
    EUInstitution(code="AMLA", name="Authority for Anti-Money Laundering", short_name="AMLA",
        mdi_icon="mdi-cash-lock", colour="#475569",
        calendar_url="https://www.amla.europa.eu/policy/public-hearings_en"),
    EUInstitution(code="CEPOL", name="EU Agency for Law Enforcement Training", short_name="CEPOL",
        mdi_icon="mdi-police-badge", colour="#1e40af",
        calendar_url="https://www.cepol.europa.eu/training-education/webinars"),
    EUInstitution(code="EIT", name="European Institute of Innovation and Technology", short_name="EIT",
        mdi_icon="mdi-lightbulb-on", colour="#0d9488",
        calendar_url="https://www.eit.europa.eu/news-events/events"),
    EUInstitution(code="CPVO", name="Community Plant Variety Office", short_name="CPVO",
        mdi_icon="mdi-sprout", colour="#65a30d",
        calendar_url="https://cpvo.europa.eu/en/news-and-events/conferences-and-events"),
    EUInstitution(code="EMSA", name="European Maritime Safety Agency", short_name="EMSA",
        mdi_icon="mdi-ferry", colour="#0369a1",
        calendar_url="https://www.emsa.europa.eu/workshops-a-events.html"),
    EUInstitution(code="EEAS", name="European External Action Service", short_name="EEAS",
        mdi_icon="mdi-earth", colour="#1e3a8a",
        calendar_url="https://www.eeas.europa.eu/filter-page/events_en"),
    EUInstitution(code="FUNDING", name="EU Funding & Tenders Portal", short_name="Funding & Tenders",
        mdi_icon="mdi-cash-multiple", colour="#0d9488",
        calendar_url="https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/support/events"),
]

# Quick lookups
EU_INSTITUTION_BY_CODE: Dict[str, EUInstitution] = {
    inst.code: inst for inst in EU_INSTITUTIONS
}

EU_INSTITUTION_CODES: List[str] = [inst.code for inst in EU_INSTITUTIONS]


# ============================================================================
# Council Configurations
# ============================================================================

COUNCIL_CONFIGURATIONS: Dict[str, str] = {
    "GAC": "General Affairs Council",
    "FAC": "Foreign Affairs Council",
    "ECOFIN": "Economic and Financial Affairs Council",
    "JHA": "Justice and Home Affairs Council",
    "EPSCO": "Employment, Social Policy, Health and Consumer Affairs Council",
    "COMPET": "Competitiveness Council",
    "TTE": "Transport, Telecommunications and Energy Council",
    "AGRIFISH": "Agriculture and Fisheries Council",
    "ENVI": "Environment Council",
    "EDUC": "Education, Youth, Culture and Sport Council",
    "EUROGROUP": "Eurogroup",
    "COREPER_I": "Committee of Permanent Representatives (Part 1)",
    "COREPER_II": "Committee of Permanent Representatives (Part 2)",
}


# ============================================================================
# European Commission Directorates-General (the "department" level)
# ============================================================================
# Source of truth: the verified EC taxonomy (31 May 2026 corpus crawl) — 40 DGs
# = 25 policy + 15 functional/horizontal. Used both for the My EU Calendar
# institution->department dropdown and to normalise/infer `commission_dg`.
# (code, name, kind) where kind in {"policy", "functional"}.

COMMISSION_DGS: List[tuple] = [
    # 25 policy DGs
    ("AGRI", "Agriculture and Rural Development", "policy"),
    ("BUDG", "Budget", "policy"),
    ("CLIMA", "Climate Action", "policy"),
    ("CNECT", "Communications Networks, Content and Technology", "policy"),
    ("COMP", "Competition", "policy"),
    ("DEFIS", "Defence Industry and Space", "policy"),
    ("ECFIN", "Economic and Financial Affairs", "policy"),
    ("EAC", "Education, Youth, Sport and Culture", "policy"),
    ("EMPL", "Employment, Social Affairs and Inclusion", "policy"),
    ("ENER", "Energy", "policy"),
    ("ENEST", "Enlargement and Eastern Neighbourhood", "policy"),
    ("ENV", "Environment", "policy"),
    ("FISMA", "Financial Stability, Financial Services and Capital Markets Union", "policy"),
    ("GROW", "Internal Market, Industry, Entrepreneurship and SMEs", "policy"),
    ("HOME", "Migration and Home Affairs", "policy"),
    ("INTPA", "International Partnerships", "policy"),
    ("JUST", "Justice and Consumers", "policy"),
    ("MARE", "Maritime Affairs and Fisheries", "policy"),
    ("MENA", "Middle East and North Africa", "policy"),
    ("MOVE", "Mobility and Transport", "policy"),
    ("REGIO", "Regional and Urban Policy", "policy"),
    ("RTD", "Research and Innovation", "policy"),
    ("SANTE", "Health and Food Safety", "policy"),
    ("TAXUD", "Taxation and Customs Union", "policy"),
    ("TRADE", "Trade and Economic Security", "policy"),
    # 15 functional / horizontal DGs and DG-level departments
    ("COMM", "Communication", "functional"),
    ("DIGIT", "Digital Services", "functional"),
    ("DGT", "Translation", "functional"),
    ("SCIC", "Interpretation", "functional"),
    ("HR", "Human Resources and Security", "functional"),
    ("ESTAT", "Eurostat", "functional"),
    ("JRC", "Joint Research Centre", "functional"),
    ("ECHO", "European Civil Protection and Humanitarian Aid Operations", "functional"),
    ("OLAF", "European Anti-Fraud Office", "functional"),
    ("HERA", "Health Emergency Preparedness and Response Authority", "functional"),
    ("SG", "Secretariat-General", "functional"),
    ("SJ", "Legal Service", "functional"),
    ("IAS", "Internal Audit Service", "functional"),
    ("IDEA", "Inspire, Debate, Engage and Accelerate Action", "functional"),
    ("REFORM", "Structural Reform Support", "functional"),
]

COMMISSION_DG_NAME: Dict[str, str] = {c: n for c, n, _ in COMMISSION_DGS}
COMMISSION_DG_CODES: List[str] = [c for c, _, _ in COMMISSION_DGS]

# Dirty -> canonical DG code, for normalising scraped `commission_dg` values
# ("DG ENV", "dg sante", "ENVIRONMENT" ...). Extend as new variants appear.
_DG_ALIASES: Dict[str, str] = {
    "DG ENV": "ENV", "ENVIRONMENT": "ENV",
    "DG MOVE": "MOVE", "DG SANTE": "SANTE", "DG GROW": "GROW",
    "DG ENER": "ENER", "DG AGRI": "AGRI", "DG MARE": "MARE",
    "DG CLIMA": "CLIMA", "DG TRADE": "TRADE", "DG COMP": "COMP",
    "DG FISMA": "FISMA", "DG REGIO": "REGIO", "REGION": "REGIO",
    "NEAR": "ENEST",  # former DG NEAR split into ENEST + MENA
}

# Keyword -> DG, to INFER the department from a Commission event title/description
# when `commission_dg` is null. First match wins; ordered most-specific first.
_DG_INFERENCE: List[tuple] = [
    ("AGRI", ("agricultur", "common agricultural", "rural development", "farm", "cap ")),
    ("MARE", ("fisher", "fishing", "aquacultur", "maritime affairs", "blue economy", "ocean")),
    ("SANTE", ("health", "medicine", "pharmaceutic", "food safety", "veterinary", "novel food", "feed additive")),
    ("ENV", ("environment", "biodiversity", "circular economy", "pollution", "nature restoration", "waste")),
    ("CLIMA", ("climate", "emission", "carbon", "ets", "cbam")),
    ("ENER", ("energy", "electricity", "hydrogen", "renewable", "gas market", "nuclear")),
    ("MOVE", ("transport", "mobility", "aviation", "rail", "maritime transport", "vehicle")),
    ("CNECT", ("digital", "artificial intelligence", " ai ", "connectivity", "cyber", "platform", "telecom")),
    ("GROW", ("internal market", "industry", "sme", "single market", "entrepreneur")),
    ("TRADE", ("trade", "tariff", "anti-dumping", "export control", "economic security")),
    ("FISMA", ("financial services", "capital markets", "banking union", "insurance")),
    ("ECFIN", ("economic and financial", "fiscal", "macroeconomic", "euro area")),
    ("TAXUD", ("taxation", "customs", "vat", "excise")),
    ("COMP", ("competition", "state aid", "antitrust", "merger")),
    ("EMPL", ("employment", "social affairs", "labour", "skills", "working conditions")),
    ("JUST", ("justice", "consumer", "fundamental rights", "rule of law", "data protection")),
    ("HOME", ("migration", "asylum", "border", "schengen", "home affairs")),
    ("REGIO", ("cohesion", "regional", "structural fund", "urban policy")),
    ("RTD", ("research", "innovation", "horizon europe")),
    ("ECHO", ("humanitarian", "civil protection", "disaster")),
    ("DEFIS", ("defence industry", "space programme", "galileo", "copernicus")),
    ("INTPA", ("international partnership", "global gateway", "development cooperation")),
    ("ENEST", ("enlargement", "accession", "western balkan", "eastern neighbourhood")),
    ("EAC", ("education", "erasmus", "youth", "culture", "sport")),
]


def normalise_dg(raw: Optional[str]) -> Optional[str]:
    """Map a scraped commission_dg value to a canonical DG code (or None)."""
    if not raw:
        return None
    v = raw.strip().upper().replace("DG ", "").strip()
    if v in COMMISSION_DG_NAME:
        return v
    full = raw.strip().upper()
    if full in _DG_ALIASES:
        return _DG_ALIASES[full]
    if v in _DG_ALIASES:
        return _DG_ALIASES[v]
    return v if v in COMMISSION_DG_NAME else None


def infer_dg(text: Optional[str]) -> Optional[str]:
    """Infer a DG code from an event title/description. None if no confident match."""
    if not text:
        return None
    t = text.lower()
    for code, kws in _DG_INFERENCE:
        if any(k in t for k in kws):
            return code
    return None


# ============================================================================
# EP Committees (the EP "department" level)
# ============================================================================

EP_COMMITTEES: Dict[str, str] = {
    "AFET": "Foreign Affairs", "DEVE": "Development", "INTA": "International Trade",
    "BUDG": "Budgets", "CONT": "Budgetary Control", "ECON": "Economic and Monetary Affairs",
    "EMPL": "Employment and Social Affairs", "ENVI": "Environment, Climate and Food Safety",
    "ITRE": "Industry, Research and Energy", "IMCO": "Internal Market and Consumer Protection",
    "TRAN": "Transport and Tourism", "REGI": "Regional Development",
    "AGRI": "Agriculture and Rural Development", "PECH": "Fisheries",
    "CULT": "Culture and Education", "JURI": "Legal Affairs",
    "LIBE": "Civil Liberties, Justice and Home Affairs", "AFCO": "Constitutional Affairs",
    "FEMM": "Women's Rights and Gender Equality", "PETI": "Petitions",
    # Subcommittees
    "SEDE": "Security and Defence", "DROI": "Human Rights",
    "FISC": "Tax Matters", "SANT": "Public Health",
    # Special committees (EP10)
    "HOUS": "Housing", "EUDS": "European Democracy Shield",
}


# ============================================================================
# Policy Area Definitions
# ============================================================================

class PolicyAreaConfig(NamedTuple):
    """Policy area mapping for calendar filters."""
    code: str
    label: str
    colour: str
    ep_committee_codes: List[str]
    council_configs: List[str]


POLICY_AREAS: List[PolicyAreaConfig] = [
    PolicyAreaConfig(
        code="digital_ai",
        label="Digital & AI",
        colour="#2563eb",
        ep_committee_codes=["ITRE", "IMCO", "LIBE"],
        council_configs=["COMPET", "TTE"],
    ),
    PolicyAreaConfig(
        code="green_deal",
        label="Green Deal",
        colour="#16a34a",
        ep_committee_codes=["ENVI", "ITRE", "TRAN"],
        council_configs=["ENVI", "TTE"],
    ),
    PolicyAreaConfig(
        code="trade",
        label="Trade",
        colour="#9333ea",
        ep_committee_codes=["INTA"],
        council_configs=["FAC"],
    ),
    PolicyAreaConfig(
        code="defence",
        label="Defence",
        colour="#475569",
        ep_committee_codes=["AFET", "SEDE"],
        council_configs=["FAC"],
    ),
    PolicyAreaConfig(
        code="health",
        label="Health",
        colour="#dc2626",
        ep_committee_codes=["ENVI", "SANT"],
        council_configs=["EPSCO"],
    ),
    PolicyAreaConfig(
        code="agriculture",
        label="Agriculture",
        colour="#ca8a04",
        ep_committee_codes=["AGRI", "PECH"],
        council_configs=["AGRIFISH"],
    ),
    PolicyAreaConfig(
        code="migration",
        label="Migration",
        colour="#ea580c",
        ep_committee_codes=["LIBE"],
        council_configs=["JHA"],
    ),
    PolicyAreaConfig(
        code="budget",
        label="Budget",
        colour="#0891b2",
        ep_committee_codes=["BUDG", "CONT", "ECON", "FISC"],
        council_configs=["ECOFIN", "EUROGROUP"],
    ),
]

POLICY_AREA_BY_CODE: Dict[str, PolicyAreaConfig] = {
    pa.code: pa for pa in POLICY_AREAS
}

POLICY_AREA_CODES: List[str] = [pa.code for pa in POLICY_AREAS]


# ============================================================================
# Helpers
# ============================================================================

def get_institution(code: str) -> EUInstitution:
    """Get institution by code. Raises KeyError if not found."""
    return EU_INSTITUTION_BY_CODE[code.upper()]


def get_institutions_for_frontend() -> List[Dict]:
    """Get institutions formatted for frontend display."""
    return [
        {
            "code": inst.code,
            "name": inst.name,
            "short_name": inst.short_name,
            "mdi_icon": inst.mdi_icon,
            "colour": inst.colour,
            "calendar_url": inst.calendar_url,
        }
        for inst in EU_INSTITUTIONS
    ]


def get_policy_areas_for_frontend() -> List[Dict]:
    """Get policy areas formatted for frontend display."""
    return [
        {
            "code": pa.code,
            "label": pa.label,
            "colour": pa.colour,
            "ep_committee_codes": pa.ep_committee_codes,
            "council_configs": pa.council_configs,
        }
        for pa in POLICY_AREAS
    ]


def get_bodies_for_frontend() -> Dict[str, List[Dict]]:
    """Institution code -> its selectable 'departments' for the cascading filter.

    EP -> committees, COMMISSION -> DGs (with policy/functional kind), COUNCIL ->
    configurations. Institutions that ARE the body (ECB, EMA, agencies, ...) or
    have no sub-level (European Council, third-party) return an empty list.
    """
    bodies: Dict[str, List[Dict]] = {code: [] for code in EU_INSTITUTION_CODES}
    bodies["EP"] = [
        {"code": c, "name": n} for c, n in sorted(EP_COMMITTEES.items())
    ]
    bodies["COMMISSION"] = [
        {"code": c, "name": n, "kind": k} for c, n, k in COMMISSION_DGS
    ]
    bodies["COUNCIL"] = [
        {"code": c, "name": n} for c, n in COUNCIL_CONFIGURATIONS.items()
    ]
    return bodies


def get_policy_areas_for_event(
    ep_committee_code: Optional[str] = None,
    council_configuration: Optional[str] = None,
    explicit_areas: Optional[List[str]] = None,
) -> List[str]:
    """
    Determine which policy areas an event belongs to based on its metadata.

    Checks EP committee code and Council configuration against the
    policy area mappings.
    """
    areas = set(explicit_areas or [])

    for pa in POLICY_AREAS:
        if ep_committee_code and ep_committee_code in pa.ep_committee_codes:
            areas.add(pa.code)
        if council_configuration and council_configuration in pa.council_configs:
            areas.add(pa.code)

    return sorted(areas)

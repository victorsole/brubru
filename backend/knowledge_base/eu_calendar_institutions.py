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

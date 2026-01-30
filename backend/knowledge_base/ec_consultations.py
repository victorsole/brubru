"""
EC Public Consultations Constants.

Constants for the European Commission "Have Your Say" public consultations portal.
Portal URL: https://ec.europa.eu/info/law/better-regulation/have-your-say

Created: January 2026
"""

from enum import Enum
from typing import Dict, NamedTuple


# ============================================================================
# Consultation Types
# ============================================================================

class ConsultationType(str, Enum):
    """Types of EC public consultations."""
    PUBLIC_CONSULTATION = "public_consultation"
    CALL_FOR_EVIDENCE = "call_for_evidence"
    FEEDBACK = "feedback"
    ROADMAP = "roadmap"
    INITIATIVE = "initiative"


CONSULTATION_TYPE_LABELS = {
    ConsultationType.PUBLIC_CONSULTATION: "Public consultation",
    ConsultationType.CALL_FOR_EVIDENCE: "Call for evidence",
    ConsultationType.FEEDBACK: "Feedback on draft act",
    ConsultationType.ROADMAP: "Roadmap feedback",
    ConsultationType.INITIATIVE: "Initiative",
}


# ============================================================================
# Consultation Statuses
# ============================================================================

class ConsultationStatus(str, Enum):
    """Status of a consultation."""
    OPEN = "open"
    UPCOMING = "upcoming"
    CLOSED = "closed"
    OUTCOME_PUBLISHED = "outcome_published"
    WITHDRAWN = "withdrawn"


CONSULTATION_STATUS_LABELS = {
    ConsultationStatus.OPEN: "Open",
    ConsultationStatus.UPCOMING: "Upcoming",
    ConsultationStatus.CLOSED: "Closed",
    ConsultationStatus.OUTCOME_PUBLISHED: "Outcome published",
    ConsultationStatus.WITHDRAWN: "Withdrawn",
}


# ============================================================================
# Policy Areas
# ============================================================================

class PolicyArea(str, Enum):
    """EC Policy areas (aligned with Have Your Say taxonomy)."""
    AGRICULTURE = "agriculture"
    BANKING_FINANCE = "banking_finance"
    BORDERS_SECURITY = "borders_security"
    BUDGET = "budget"
    BUSINESS = "business"
    CLIMATE = "climate"
    COMPETITION = "competition"
    CONSUMERS = "consumers"
    CULTURE = "culture"
    CUSTOMS = "customs"
    DIGITAL = "digital"
    ECONOMY = "economy"
    EDUCATION = "education"
    EMPLOYMENT = "employment"
    ENERGY = "energy"
    ENLARGEMENT = "enlargement"
    ENVIRONMENT = "environment"
    FOOD_SAFETY = "food_safety"
    FOREIGN_AFFAIRS = "foreign_affairs"
    FRAUD = "fraud"
    HEALTH = "health"
    HUMANITARIAN_AID = "humanitarian_aid"
    INTERNAL_MARKET = "internal_market"
    JUSTICE = "justice"
    MARITIME = "maritime"
    PUBLIC_ADMIN = "public_admin"
    REGIONAL_POLICY = "regional_policy"
    RESEARCH = "research"
    SINGLE_MARKET = "single_market"
    SOCIAL_AFFAIRS = "social_affairs"
    SPORT = "sport"
    STATISTICS = "statistics"
    TAXATION = "taxation"
    TRADE = "trade"
    TRANSPORT = "transport"
    YOUTH = "youth"
    OTHER = "other"


POLICY_AREA_LABELS = {
    PolicyArea.AGRICULTURE: "Agriculture and rural development",
    PolicyArea.BANKING_FINANCE: "Banking and financial services",
    PolicyArea.BORDERS_SECURITY: "Borders and security",
    PolicyArea.BUDGET: "Budget",
    PolicyArea.BUSINESS: "Business and industry",
    PolicyArea.CLIMATE: "Climate action",
    PolicyArea.COMPETITION: "Competition",
    PolicyArea.CONSUMERS: "Consumers",
    PolicyArea.CULTURE: "Culture and media",
    PolicyArea.CUSTOMS: "Customs",
    PolicyArea.DIGITAL: "Digital economy and society",
    PolicyArea.ECONOMY: "Economy, finance and the euro",
    PolicyArea.EDUCATION: "Education and training",
    PolicyArea.EMPLOYMENT: "Employment and social affairs",
    PolicyArea.ENERGY: "Energy",
    PolicyArea.ENLARGEMENT: "EU enlargement",
    PolicyArea.ENVIRONMENT: "Environment",
    PolicyArea.FOOD_SAFETY: "Food safety",
    PolicyArea.FOREIGN_AFFAIRS: "Foreign affairs and security policy",
    PolicyArea.FRAUD: "Fraud prevention",
    PolicyArea.HEALTH: "Public health",
    PolicyArea.HUMANITARIAN_AID: "Humanitarian aid and civil protection",
    PolicyArea.INTERNAL_MARKET: "Internal market",
    PolicyArea.JUSTICE: "Justice and fundamental rights",
    PolicyArea.MARITIME: "Maritime affairs and fisheries",
    PolicyArea.PUBLIC_ADMIN: "Institutional affairs",
    PolicyArea.REGIONAL_POLICY: "Regional policy",
    PolicyArea.RESEARCH: "Research and innovation",
    PolicyArea.SINGLE_MARKET: "Single market",
    PolicyArea.SOCIAL_AFFAIRS: "Social protection and inclusion",
    PolicyArea.SPORT: "Sport",
    PolicyArea.STATISTICS: "Statistics",
    PolicyArea.TAXATION: "Taxation",
    PolicyArea.TRADE: "Trade",
    PolicyArea.TRANSPORT: "Transport",
    PolicyArea.YOUTH: "Youth",
    PolicyArea.OTHER: "Other",
}


# ============================================================================
# Directorate-Generals
# ============================================================================

class DirectorateGeneral(NamedTuple):
    """EC Directorate-General information."""
    code: str
    name: str
    full_name: str


# All EC Directorate-Generals
DGS = [
    DirectorateGeneral("AGRI", "Agriculture", "DG Agriculture and Rural Development"),
    DirectorateGeneral("BUDG", "Budget", "DG Budget"),
    DirectorateGeneral("CLIMA", "Climate Action", "DG Climate Action"),
    DirectorateGeneral("CNECT", "Communications Networks", "DG Communications Networks, Content and Technology"),
    DirectorateGeneral("COMM", "Communication", "DG Communication"),
    DirectorateGeneral("COMP", "Competition", "DG Competition"),
    DirectorateGeneral("DEFIS", "Defence Industry", "DG Defence Industry and Space"),
    DirectorateGeneral("DIGIT", "Informatics", "DG Informatics"),
    DirectorateGeneral("EAC", "Education and Culture", "DG Education, Youth, Sport and Culture"),
    DirectorateGeneral("ECFIN", "Economic and Financial Affairs", "DG Economic and Financial Affairs"),
    DirectorateGeneral("ECHO", "Civil Protection", "DG European Civil Protection and Humanitarian Aid Operations"),
    DirectorateGeneral("EMPL", "Employment", "DG Employment, Social Affairs and Inclusion"),
    DirectorateGeneral("ENER", "Energy", "DG Energy"),
    DirectorateGeneral("ENV", "Environment", "DG Environment"),
    DirectorateGeneral("ESTAT", "Eurostat", "Eurostat - European Statistics"),
    DirectorateGeneral("FISMA", "Financial Stability", "DG Financial Stability, Financial Services and Capital Markets Union"),
    DirectorateGeneral("GROW", "Internal Market", "DG Internal Market, Industry, Entrepreneurship and SMEs"),
    DirectorateGeneral("HOME", "Migration and Home Affairs", "DG Migration and Home Affairs"),
    DirectorateGeneral("HR", "Human Resources", "DG Human Resources and Security"),
    DirectorateGeneral("INTPA", "International Partnerships", "DG International Partnerships"),
    DirectorateGeneral("JRC", "Joint Research Centre", "Joint Research Centre"),
    DirectorateGeneral("JUST", "Justice", "DG Justice and Consumers"),
    DirectorateGeneral("MARE", "Maritime Affairs", "DG Maritime Affairs and Fisheries"),
    DirectorateGeneral("MOVE", "Mobility and Transport", "DG Mobility and Transport"),
    DirectorateGeneral("NEAR", "Neighbourhood", "DG Neighbourhood and Enlargement Negotiations"),
    DirectorateGeneral("OLAF", "Anti-Fraud Office", "European Anti-Fraud Office"),
    DirectorateGeneral("OP", "Publications Office", "Publications Office of the European Union"),
    DirectorateGeneral("REFORM", "Structural Reform", "DG Structural Reform Support"),
    DirectorateGeneral("REGIO", "Regional Policy", "DG Regional and Urban Policy"),
    DirectorateGeneral("RTD", "Research", "DG Research and Innovation"),
    DirectorateGeneral("SANTE", "Health", "DG Health and Food Safety"),
    DirectorateGeneral("SCIC", "Interpretation", "DG Interpretation"),
    DirectorateGeneral("SG", "Secretariat-General", "Secretariat-General"),
    DirectorateGeneral("SJ", "Legal Service", "Legal Service"),
    DirectorateGeneral("TAXUD", "Taxation and Customs", "DG Taxation and Customs Union"),
    DirectorateGeneral("TRADE", "Trade", "DG Trade"),
]

# Quick lookup by code
DG_BY_CODE: Dict[str, DirectorateGeneral] = {dg.code: dg for dg in DGS}
DG_CODES = [dg.code for dg in DGS]


# ============================================================================
# Document Types
# ============================================================================

class DocumentType(str, Enum):
    """Types of consultation documents."""
    QUESTIONNAIRE = "questionnaire"
    IMPACT_ASSESSMENT = "impact_assessment"
    DRAFT_ACT = "draft_act"
    EXPLANATORY_MEMO = "explanatory_memo"
    ANNEX = "annex"
    FACTSHEET = "factsheet"
    SUMMARY = "summary"
    INCEPTION_IMPACT_ASSESSMENT = "inception_impact_assessment"
    ROADMAP = "roadmap"
    OUTCOME_REPORT = "outcome_report"
    STATISTICS = "statistics"
    OTHER = "other"


DOCUMENT_TYPE_LABELS = {
    DocumentType.QUESTIONNAIRE: "Questionnaire",
    DocumentType.IMPACT_ASSESSMENT: "Impact assessment",
    DocumentType.DRAFT_ACT: "Draft legislative act",
    DocumentType.EXPLANATORY_MEMO: "Explanatory memorandum",
    DocumentType.ANNEX: "Annex",
    DocumentType.FACTSHEET: "Factsheet",
    DocumentType.SUMMARY: "Summary",
    DocumentType.INCEPTION_IMPACT_ASSESSMENT: "Inception impact assessment",
    DocumentType.ROADMAP: "Roadmap",
    DocumentType.OUTCOME_REPORT: "Outcome report",
    DocumentType.STATISTICS: "Statistics",
    DocumentType.OTHER: "Other",
}


# ============================================================================
# Stakeholder Categories
# ============================================================================

class StakeholderCategory(str, Enum):
    """Categories of stakeholders for consultation responses."""
    EU_CITIZEN = "eu_citizen"
    BUSINESS = "business"
    BUSINESS_ASSOCIATION = "business_association"
    CONSUMER_ORG = "consumer_org"
    NGO = "ngo"
    TRADE_UNION = "trade_union"
    ACADEMIC = "academic"
    PUBLIC_AUTHORITY = "public_authority"
    OTHER = "other"


STAKEHOLDER_CATEGORY_LABELS = {
    StakeholderCategory.EU_CITIZEN: "EU citizen",
    StakeholderCategory.BUSINESS: "Company/business organisation",
    StakeholderCategory.BUSINESS_ASSOCIATION: "Business association",
    StakeholderCategory.CONSUMER_ORG: "Consumer organisation",
    StakeholderCategory.NGO: "Non-governmental organisation (NGO)",
    StakeholderCategory.TRADE_UNION: "Trade union",
    StakeholderCategory.ACADEMIC: "Academic/research institution",
    StakeholderCategory.PUBLIC_AUTHORITY: "Public authority",
    StakeholderCategory.OTHER: "Other",
}


# ============================================================================
# Portal URLs
# ============================================================================

HAVE_YOUR_SAY_BASE_URL = "https://ec.europa.eu/info/law/better-regulation/have-your-say"
HAVE_YOUR_SAY_INITIATIVES_URL = f"{HAVE_YOUR_SAY_BASE_URL}/initiatives_en"

# API endpoints (discovered from portal investigation)
# The portal uses server-side rendering with some JSON API endpoints
PORTAL_SEARCH_URL = f"{HAVE_YOUR_SAY_BASE_URL}/initiatives_en"


# ============================================================================
# Relevance Scoring
# ============================================================================

# Consultations with these types are more impactful
CONSULTATION_TYPE_RELEVANCE = {
    ConsultationType.PUBLIC_CONSULTATION: 100,
    ConsultationType.CALL_FOR_EVIDENCE: 90,
    ConsultationType.FEEDBACK: 80,
    ConsultationType.INITIATIVE: 70,
    ConsultationType.ROADMAP: 60,
}

# Policy areas with higher regulatory impact
HIGH_PRIORITY_POLICY_AREAS = {
    PolicyArea.DIGITAL,
    PolicyArea.CLIMATE,
    PolicyArea.ENERGY,
    PolicyArea.INTERNAL_MARKET,
    PolicyArea.COMPETITION,
    PolicyArea.TRADE,
    PolicyArea.BANKING_FINANCE,
    PolicyArea.TAXATION,
}


# ============================================================================
# Helper Functions
# ============================================================================

def get_dg_full_name(code: str) -> str:
    """Get full DG name from code."""
    dg = DG_BY_CODE.get(code.upper())
    return dg.full_name if dg else f"DG {code}"


def get_policy_area_label(policy_area: PolicyArea) -> str:
    """Get human-readable policy area label."""
    return POLICY_AREA_LABELS.get(policy_area, str(policy_area.value))


def get_consultation_type_label(consultation_type: ConsultationType) -> str:
    """Get human-readable consultation type label."""
    return CONSULTATION_TYPE_LABELS.get(consultation_type, str(consultation_type.value))


def get_status_label(status: ConsultationStatus) -> str:
    """Get human-readable status label."""
    return CONSULTATION_STATUS_LABELS.get(status, str(status.value))


def calculate_relevance_score(
    consultation_type: ConsultationType,
    policy_area: PolicyArea,
    days_remaining: int = None
) -> int:
    """
    Calculate relevance score for a consultation.

    Factors:
    - Consultation type (public consultation highest)
    - Policy area (priority areas get bonus)
    - Days remaining (urgency bonus)

    Returns:
        Score from 0-100
    """
    base_score = CONSULTATION_TYPE_RELEVANCE.get(consultation_type, 50)

    # Policy area bonus
    if policy_area in HIGH_PRIORITY_POLICY_AREAS:
        base_score = min(100, base_score + 10)

    # Urgency bonus for closing soon
    if days_remaining is not None:
        if days_remaining <= 3:
            base_score = min(100, base_score + 15)
        elif days_remaining <= 7:
            base_score = min(100, base_score + 10)
        elif days_remaining <= 14:
            base_score = min(100, base_score + 5)

    return base_score

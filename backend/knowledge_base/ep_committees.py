"""
EP Committee Constants and Definitions.

All 26 European Parliament committees with metadata for scraping
and classification.

Created: January 2026
"""

from typing import Dict, List, NamedTuple


class EPCommittee(NamedTuple):
    """EP Committee definition."""
    code: str
    name: str
    full_name: str
    policy_area: str
    url_path: str  # Path segment for work-in-progress URL


# All 26 EP committees (deduplicated - JURI appears twice in source)
EP_COMMITTEES: List[EPCommittee] = [
    # External Relations
    EPCommittee(
        code="AFET",
        name="Foreign Affairs",
        full_name="Committee on Foreign Affairs",
        policy_area="External relations",
        url_path="afet"
    ),
    EPCommittee(
        code="DROI",
        name="Human Rights",
        full_name="Subcommittee on Human Rights",
        policy_area="External relations",
        url_path="droi"
    ),
    EPCommittee(
        code="SEDE",
        name="Security and Defence",
        full_name="Subcommittee on Security and Defence",
        policy_area="External relations",
        url_path="sede"
    ),
    EPCommittee(
        code="DEVE",
        name="Development",
        full_name="Committee on Development",
        policy_area="External relations",
        url_path="deve"
    ),
    EPCommittee(
        code="INTA",
        name="International Trade",
        full_name="Committee on International Trade",
        policy_area="External relations",
        url_path="inta"
    ),
    EPCommittee(
        code="EUDS",
        name="EU-US Relations",
        full_name="Delegation to the EU-US Parliamentary Assembly",
        policy_area="External relations",
        url_path="euds"
    ),

    # Economic/Financial
    EPCommittee(
        code="BUDG",
        name="Budgets",
        full_name="Committee on Budgets",
        policy_area="Economic/Financial",
        url_path="budg"
    ),
    EPCommittee(
        code="CONT",
        name="Budgetary Control",
        full_name="Committee on Budgetary Control",
        policy_area="Economic/Financial",
        url_path="cont"
    ),
    EPCommittee(
        code="ECON",
        name="Economic and Monetary Affairs",
        full_name="Committee on Economic and Monetary Affairs",
        policy_area="Economic/Financial",
        url_path="econ"
    ),
    EPCommittee(
        code="FISC",
        name="Tax Matters",
        full_name="Subcommittee on Tax Matters",
        policy_area="Economic/Financial",
        url_path="fisc"
    ),

    # Social
    EPCommittee(
        code="EMPL",
        name="Employment and Social Affairs",
        full_name="Committee on Employment and Social Affairs",
        policy_area="Social",
        url_path="empl"
    ),
    EPCommittee(
        code="FEMM",
        name="Women's Rights and Gender Equality",
        full_name="Committee on Women's Rights and Gender Equality",
        policy_area="Social",
        url_path="femm"
    ),
    EPCommittee(
        code="HOUS",
        name="Housing and Urban Development",
        full_name="Committee on Housing and Urban Development",
        policy_area="Social",
        url_path="hous"
    ),

    # Environment/Health
    EPCommittee(
        code="ENVI",
        name="Environment, Public Health and Food Safety",
        full_name="Committee on Environment, Public Health and Food Safety",
        policy_area="Environment/Health",
        url_path="envi"
    ),
    EPCommittee(
        code="SANT",
        name="Public Health",
        full_name="Subcommittee on Public Health",
        policy_area="Environment/Health",
        url_path="sant"
    ),

    # Industry/Tech
    EPCommittee(
        code="ITRE",
        name="Industry, Research and Energy",
        full_name="Committee on Industry, Research and Energy",
        policy_area="Industry/Tech",
        url_path="itre"
    ),

    # Internal Market
    EPCommittee(
        code="IMCO",
        name="Internal Market and Consumer Protection",
        full_name="Committee on Internal Market and Consumer Protection",
        policy_area="Internal Market",
        url_path="imco"
    ),

    # Infrastructure
    EPCommittee(
        code="TRAN",
        name="Transport and Tourism",
        full_name="Committee on Transport and Tourism",
        policy_area="Infrastructure",
        url_path="tran"  # Note: TRAN uses different URL format
    ),

    # Cohesion
    EPCommittee(
        code="REGI",
        name="Regional Development",
        full_name="Committee on Regional Development",
        policy_area="Cohesion",
        url_path="regi"
    ),

    # Agriculture
    EPCommittee(
        code="AGRI",
        name="Agriculture and Rural Development",
        full_name="Committee on Agriculture and Rural Development",
        policy_area="Agriculture",
        url_path="agri"
    ),
    EPCommittee(
        code="PECH",
        name="Fisheries",
        full_name="Committee on Fisheries",
        policy_area="Agriculture",
        url_path="pech"
    ),

    # Culture/Education
    EPCommittee(
        code="CULT",
        name="Culture and Education",
        full_name="Committee on Culture and Education",
        policy_area="Culture/Education",
        url_path="cult"
    ),

    # Legal/Institutional
    EPCommittee(
        code="JURI",
        name="Legal Affairs",
        full_name="Committee on Legal Affairs",
        policy_area="Legal/Institutional",
        url_path="juri"
    ),
    EPCommittee(
        code="AFCO",
        name="Constitutional Affairs",
        full_name="Committee on Constitutional Affairs",
        policy_area="Legal/Institutional",
        url_path="afco"
    ),

    # Justice/Home Affairs
    EPCommittee(
        code="LIBE",
        name="Civil Liberties, Justice and Home Affairs",
        full_name="Committee on Civil Liberties, Justice and Home Affairs",
        policy_area="Justice/Home Affairs",
        url_path="libe"
    ),

    # Citizens
    EPCommittee(
        code="PETI",
        name="Petitions",
        full_name="Committee on Petitions",
        policy_area="Citizens",
        url_path="peti"
    ),
]

# Quick lookup by code
EP_COMMITTEE_BY_CODE: Dict[str, EPCommittee] = {
    c.code: c for c in EP_COMMITTEES
}

# All committee codes (for validation)
EP_COMMITTEE_CODES: List[str] = [c.code for c in EP_COMMITTEES]

# Policy area groupings
EP_COMMITTEES_BY_POLICY_AREA: Dict[str, List[EPCommittee]] = {}
for committee in EP_COMMITTEES:
    if committee.policy_area not in EP_COMMITTEES_BY_POLICY_AREA:
        EP_COMMITTEES_BY_POLICY_AREA[committee.policy_area] = []
    EP_COMMITTEES_BY_POLICY_AREA[committee.policy_area].append(committee)


def get_committee(code: str) -> EPCommittee:
    """Get committee by code. Raises KeyError if not found."""
    return EP_COMMITTEE_BY_CODE[code.upper()]


def get_committee_url(code: str, page: int = 0, term: int = 10) -> str:
    """
    Build work-in-progress URL for a committee.

    Note: TRAN uses a different URL format (missing code in path).
    """
    committee = get_committee(code)
    base_url = "https://www.europarl.europa.eu"

    if code.upper() == "TRAN":
        # TRAN uses different URL format
        return (
            f"{base_url}/committees/en/documents/work-in-progress"
            f"?committeeMnemoCode=TRAN&term={term}&page={page}"
        )

    return (
        f"{base_url}/committees/en/{committee.url_path}/documents/work-in-progress"
        f"?term={term}&page={page}"
    )


def get_committees_for_frontend() -> List[Dict]:
    """Get committees formatted for frontend dropdowns."""
    return [
        {
            "code": c.code,
            "name": c.name,
            "full_name": c.full_name,
            "policy_area": c.policy_area,
        }
        for c in EP_COMMITTEES
    ]

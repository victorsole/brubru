"""
Brubru proprietary body families — a policy-domain lens over every EU body, used
by the cross-body aggregator folders (/api/v2/events first, /api/v2/news next).

This is editorial, not org-chart: a body is tagged by the policy communities it
matters to, many-to-many (the ECB sits in both Finance and Digital for fintech).
That curation is the proprietary, sellable layer Brubru adds on top of the raw
feeds. Edit freely — it is the single source of truth for the `family=` selector.

Also reconciles the two event stores' body namespaces: economy_items uses Brubru
body codes (cedefop, ecb, sns, ...); eu_calendar_events uses an institution enum
(COMMISSION, EP, COUNCIL, ...). Both answer to the same canonical body code here.
"""
from __future__ import annotations

# family slug -> {label, bodies (canonical codes)}. Bodies may repeat across families.
FAMILIES: dict[str, dict] = {
    "digital-tech": {"label": "Digital & Tech",
                     "bodies": ["euipo", "enisa", "berec", "eu_lisa", "chips", "sns", "eurohpc", "eccc",
                                "interoperable", "eugovtech"]},
    "health-life-sciences": {"label": "Health & Life Sciences",
                             "bodies": ["ema", "ecdc", "efsa", "euda", "ihi", "edctp3", "hadea"]},
    "climate-energy-environment": {"label": "Climate, Energy & Environment",
                                   "bodies": ["eea", "echa", "acer", "hydrogen", "aviation", "cinea"]},
    "finance-economy": {"label": "Finance & Economy",
                        "bodies": ["ecb", "ecb_ssm", "eba", "eiopa", "esma", "esrb", "srb", "eib",
                                   "esm", "amla", "eif", "eurogroup"]},
    "defence-security-borders": {"label": "Defence, Security & Borders",
                                 "bodies": ["eda", "satcen", "euiss", "esdc", "frontex", "europol",
                                            "cepol", "eurojust", "eeas"]},
    "research-innovation": {"label": "Research & Innovation",
                            "bodies": ["ercea", "rea", "eit", "eismea", "eurohpc"]},
    "justice-rights": {"label": "Justice & Rights",
                       "bodies": ["cjeu", "fra", "edps", "edpb", "ombudsman"]},
    "transport-mobility": {"label": "Transport & Mobility",
                           "bodies": ["easa", "emsa", "era", "euspa", "sesar", "rail"]},
    "jobs-skills-social": {"label": "Jobs, Skills & Social",
                           "bodies": ["cedefop", "etf", "eurofound", "eu_osha", "ela"]},
    "trade-industry-market": {"label": "Trade, Industry & Single Market",
                              "bodies": ["euipo", "cpvo"]},
    "core-institutions": {"label": "Core Institutions",
                          "bodies": ["commission", "parliament", "council", "european-council",
                                     "cor", "eesc", "eurogroup"]},
}


def bodies_for_family(slug: str) -> set[str]:
    return set(FAMILIES.get(slug, {}).get("bodies", []))


def families_for_body(code: str) -> list[str]:
    return [slug for slug, f in FAMILIES.items() if code in f["bodies"]]


def family_label(slug: str) -> str | None:
    f = FAMILIES.get(slug)
    return f["label"] if f else None


# eu_calendar_events.institution (enum) <-> canonical body code.
CAL_INSTITUTION_TO_BODY: dict[str, str] = {
    "COMMISSION": "commission", "EP": "parliament", "COUNCIL": "council",
    "EUROPEAN_COUNCIL": "european-council", "COR": "cor", "EESC": "eesc",
    "EMA": "ema", "ECB": "ecb", "EU_OSHA": "eu_osha", "EEAS": "eeas",
    "EIT": "eit", "EUROFOUND": "eurofound", "FRA": "fra", "CEPOL": "cepol",
    "THIRD_PARTY": "third-party", "FUNDING": "funding",
}
BODY_TO_CAL_INSTITUTION: dict[str, str] = {v: k for k, v in CAL_INSTITUTION_TO_BODY.items()}

# Friendly names for bodies that only appear in the calendar store (not economy_bodies).
CALENDAR_ONLY_BODY_NAMES: dict[str, str] = {
    "commission": "European Commission",
    "parliament": "European Parliament",
    "council": "Council of the EU",
    "european-council": "European Council",
    "third-party": "Third-party / external events",
    "funding": "EU Funding & Tenders",
}

"""A compliance package as a checkable artefact, and the rules it must satisfy.

Why this exists
---------------
Compliance packages live as rows in `law_clusters`, `cluster_laws` and
`law_requirements` with no schema beyond the column types and nothing that ever
looked at them as a whole. On 10 August 2026 an audit found what that permits:

  * "AI/ML Startup Compliance", one of ten packages surfaced by default, held 19
    requirements, every one marked critical, drawn from the Eurostat ICT-usage
    statistics regulation and the decision establishing the European AI Office.
    Not one of them bound an AI startup.
  * "E-commerce & Platform Startup Compliance" advertised the Digital Services
    Act in its law list and had ZERO requirements attached to it.
  * "SaaS & B2B Startup Compliance" checked companies against the GDPR articles
    that govern how a supervisory authority accredits a monitoring body.
  * 78 requirements hung off "Corrigendum to ..." rows, so the findings table
    told users their obligation came from a typographical correction.

Every one of those is mechanically detectable. None was detected, because
nothing was looking. This module is what looks.

Two uses, both cheap:
  * `validate(package)` over what is already in the database, as a standing
    audit (scripts/validate_compliance_packages.py --all).
  * `to_yaml` / `from_yaml`, so a package can be exported, reviewed in a diff,
    edited as a file and loaded back. A package that lives in version control
    gets read by a human before it reaches a user, which is the other half of
    why the three above rotted unnoticed.

The rule set is deliberately derived from real defects rather than from a
general idea of quality. Each rule below names the incident it came from.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Mirrors the valid_criticality values the corpus was normalised onto.
VALID_CRITICALITY = {"critical", "important", "recommended"}

# Set by scripts/enrich_requirement_metadata.py. 'economic_operator' is the
# default and the overwhelming majority; the rest are obligations that bind
# somebody other than the company being analysed.
VALID_ADDRESSEES = {
    "economic_operator", "member_state", "commission", "eu_agency",
    "national_authority", "notified_body", "pro", "online_platform",
    "fulfilment_service", "data_protection_authority",
}

# law_requirements.article is varchar(50), applicable_entity varchar(100).
# Exceeded during the cluster 17 rebuild and only caught by a mid-INSERT
# psycopg2 error with a truncated message.
MAX_ARTICLE_LEN = 50
MAX_ENTITY_LEN = 100

# Sector digit, 4-digit year, one or two type letters, 4 digits. Two letters
# because Commission proposals (PC, DC, JC) have them, which is the same
# narrowness that made EurlexFetcher.CELEX_PATTERN silently drop proposals.
CELEX_RE = re.compile(r"^[0-9]{5}[A-Z]{1,2}[0-9]{4}")

# A package whose binding requirements are mostly somebody else's duties returns
# a report dominated by "not applicable". This is the threshold migration 210
# used to unpublish four packages.
NOT_YOURS_LIMIT = 0.33

# Below this a compliance score is not worth acting on.
MIN_BINDING = 10


@dataclass
class Finding:
    """One rule violation. `error` blocks publication, `warning` does not."""
    severity: str          # 'error' | 'warning'
    code: str
    message: str
    where: Optional[str] = None      # article or celex the finding attaches to

    def __str__(self) -> str:
        loc = f" [{self.where}]" if self.where else ""
        return f"{self.severity.upper():<7} {self.code:<28}{loc} {self.message}"


@dataclass
class Package:
    """A compliance package, independent of how it is stored."""
    id: Optional[int]
    name: str
    policy_area: Optional[str] = None
    description: Optional[str] = None
    applicability: Optional[str] = None
    is_startup_focused: bool = False
    is_published: bool = True
    laws: List[Dict[str, Any]] = field(default_factory=list)          # {celex, title}
    requirements: List[Dict[str, Any]] = field(default_factory=list)

    # --- derived -----------------------------------------------------------

    def binding(self) -> List[Dict[str, Any]]:
        return [r for r in self.requirements if not _is_interpretive(r)]

    def not_yours(self) -> List[Dict[str, Any]]:
        return [r for r in self.binding()
                if (r.get("addressee") or "economic_operator") != "economic_operator"]


def _is_interpretive(r: Dict[str, Any]) -> bool:
    v = r.get("interpretive")
    return v is True or str(v).lower() == "true"


def _is_single_case(name: str) -> bool:
    return bool(re.search(r"(State Aid|Countervailing|Anti-Dumping|Duties)", name or "", re.I))


def validate(pkg: Package) -> List[Finding]:
    """Every rule, in one pass. Ordered errors first, then warnings."""
    errors: List[Finding] = []
    warnings: List[Finding] = []

    binding = pkg.binding()
    law_celexes = {(l.get("celex") or "").strip() for l in pkg.laws if l.get("celex")}

    # ---------------------------------------------------------------- errors

    # Cluster 49 (Tirrenia) had 14 requirements and 0 binding once recitals were
    # excluded: an analysis against it can only ever return nothing.
    if not binding:
        errors.append(Finding(
            "error", "no_binding_requirements",
            "The package has no requirement that would be analysed. Every row is "
            "interpretive, or there are no requirements at all."))

    # Cluster 18 advertised the DSA and attached nothing to it.
    reqs_by_celex: Dict[str, int] = {}
    for r in pkg.requirements:
        c = (r.get("law_celex") or "").strip()
        reqs_by_celex[c] = reqs_by_celex.get(c, 0) + 1
    for law in pkg.laws:
        celex = (law.get("celex") or "").strip()
        if not reqs_by_celex.get(celex):
            errors.append(Finding(
                "error", "law_without_requirements",
                f"'{(law.get('title') or celex)[:60]}' is listed as covered by this "
                "package but contributes no requirement, so it is a promise the "
                "analysis cannot keep.", celex or "(no celex)"))

    seen_articles: Dict[str, int] = {}
    for r in pkg.requirements:
        art = (r.get("article") or "").strip()
        where = art or "(no article)"

        if not art:
            errors.append(Finding("error", "missing_article",
                                  "Requirement has no article label.", where))
        elif len(art) > MAX_ARTICLE_LEN:
            errors.append(Finding(
                "error", "article_label_too_long",
                f"{len(art)} characters; law_requirements.article is "
                f"varchar({MAX_ARTICLE_LEN}) and the insert will fail.", where))

        entity = r.get("applicable_entity") or ""
        if len(entity) > MAX_ENTITY_LEN:
            errors.append(Finding(
                "error", "entity_too_long",
                f"applicable_entity is {len(entity)} characters; the column is "
                f"varchar({MAX_ENTITY_LEN}).", where))

        if not (r.get("requirement_text") or "").strip():
            errors.append(Finding("error", "empty_requirement_text",
                                  "Requirement has no text to check against.", where))

        crit = r.get("criticality")
        if crit not in VALID_CRITICALITY:
            errors.append(Finding(
                "error", "invalid_criticality",
                f"'{crit}' is not one of {sorted(VALID_CRITICALITY)}.", where))

        addressee = r.get("addressee") or "economic_operator"
        if addressee not in VALID_ADDRESSEES:
            errors.append(Finding(
                "error", "invalid_addressee",
                f"'{addressee}' is not a known addressee. An unknown value is "
                "treated as a company obligation by the analyser.", where))

        # A requirement whose parent law is not attached will render with a
        # blank source in the findings table.
        celex = (r.get("law_celex") or "").strip()
        if celex and law_celexes and celex not in law_celexes:
            errors.append(Finding(
                "error", "orphan_requirement",
                f"Cites {celex}, which is not among the package's laws.", where))

        # Redundancy is keyed on (act, text), and only within one act is it an
        # error.
        #
        # Three versions of this rule, each corrected by the corpus. Keying on
        # the article label alone reported 322 duplicates (ten acts legitimately
        # hold ten "Article 2(1)" rows). Keying on (law, article) still reported
        # 284 (one article yields several distinct obligations). Keying on text
        # alone was right for single-law packages but wrong for a HUB that
        # deliberately aggregates many acts: the Digital Product Passport hub
        # (cluster 65) collects the same supply-chain traceability obligation
        # from the Toys Regulation and the Detergents Regulation, worded
        # identically, and that is not a double-count of one duty, it is two
        # duties a company owes under two acts. So: same text under the SAME act
        # is a real double-count (error); the same text under DIFFERENT acts is
        # possible over-count from aggregation, flagged as a warning for a human
        # to judge, not a blocker.
        body_key = re.sub(r"\s+", " ", (r.get("requirement_text") or "")).strip().lower()
        if body_key:
            seen_articles.setdefault(body_key, []).append(celex or "(no celex)")

    for body_key, celexes in seen_articles.items():
        if len(celexes) < 2:
            continue
        # Same act twice is an unambiguous double-count; across acts it is
        # aggregation and only worth a human glance.
        max_within_one_act = max(celexes.count(c) for c in set(celexes))
        if max_within_one_act > 1:
            errors.append(Finding(
                "error", "duplicate_requirement",
                f"the same obligation text appears {max_within_one_act} times under "
                f"one act, so it is scored more than once: \"{body_key[:70]}...\""))
        else:
            warnings.append(Finding(
                "warning", "same_text_across_acts",
                f"the same obligation text appears under {len(celexes)} different "
                f"acts ({', '.join(sorted(set(celexes)))}); legitimate for an "
                f"aggregating hub, but confirm it is not accidental: "
                f"\"{body_key[:60]}...\""))

    for law in pkg.laws:
        celex = (law.get("celex") or "").strip()
        if celex and not CELEX_RE.match(celex):
            errors.append(Finding(
                "error", "invalid_celex",
                f"'{celex}' does not look like a CELEX number.", celex))

    # -------------------------------------------------------------- warnings

    if binding and len(binding) < MIN_BINDING:
        warnings.append(Finding(
            "warning", "thin_package",
            f"only {len(binding)} binding requirements; below {MIN_BINDING} a "
            "compliance score is not worth acting on."))

    if binding:
        share = len(pkg.not_yours()) / len(binding)
        if share >= NOT_YOURS_LIMIT:
            warnings.append(Finding(
                "warning", "mostly_not_yours",
                f"{len(pkg.not_yours())} of {len(binding)} binding requirements "
                f"({share:.0%}) bind someone other than the company. The report "
                "will be dominated by 'not applicable'."))

    # Cluster 17 held 19 requirements and marked all 19 critical, which carries
    # no signal: if everything is critical, nothing is.
    if len(binding) >= 5 and all(r.get("criticality") == "critical" for r in binding):
        warnings.append(Finding(
            "warning", "everything_is_critical",
            f"all {len(binding)} binding requirements are 'critical', so the "
            "severity column tells the reader nothing."))

    # Recitals explain, they do not bind. 306 were demoted by hand; this catches
    # the next one before it is scored as a duty.
    for r in pkg.requirements:
        art = (r.get("article") or "").strip()
        if re.match(r"^\s*recital\b", art, re.I) and not _is_interpretive(r):
            warnings.append(Finding(
                "warning", "unmarked_recital",
                "looks like a recital but is not flagged interpretive, so it "
                "will be scored as a binding obligation.", art))

    # 78 requirements hung off corrigendum rows, so the findings table cited a
    # typographical correction as the source of the duty.
    for law in pkg.laws:
        if (law.get("title") or "").lower().startswith("corrigendum to"):
            warnings.append(Finding(
                "warning", "corrigendum_as_source",
                "a corrigendum is a correction notice, not a source of "
                "obligations; point the requirements at the act it corrects.",
                law.get("celex") or "(no celex)"))

    if _is_single_case(pkg.name):
        warnings.append(Finding(
            "warning", "single_case_decision",
            "the name suggests a decision addressed to one named undertaking or "
            "to a Member State, which cannot be self-assessed by anyone else."))

    if binding and not any(r.get("deadline") for r in binding):
        warnings.append(Finding(
            "warning", "no_deadlines",
            "no requirement carries a date, so the action plan has no timeline."))

    if pkg.is_startup_focused and pkg.is_published:
        # Startup packages are what "For you" shows by default, so they are held
        # to the stricter bar.
        if len(binding) < MIN_BINDING:
            warnings.append(Finding(
                "warning", "weak_default_package",
                "this package is surfaced by default in the For-you lens while "
                "being below the minimum size."))

    return errors + warnings


def is_publishable(findings: List[Finding]) -> bool:
    """A package with any error must not be offered to users."""
    return not any(f.severity == "error" for f in findings)


# ---------------------------------------------------------------- serialising

def to_dict(pkg: Package) -> Dict[str, Any]:
    """Plain data, ordered for a readable diff."""
    return {
        "id": pkg.id,
        "name": pkg.name,
        "policy_area": pkg.policy_area,
        "description": pkg.description,
        "applicability": pkg.applicability,
        "is_startup_focused": pkg.is_startup_focused,
        "is_published": pkg.is_published,
        "laws": [{"celex": l.get("celex"), "title": l.get("title")} for l in pkg.laws],
        "requirements": [
            {
                "article": r.get("article"),
                "law_celex": r.get("law_celex"),
                "criticality": r.get("criticality"),
                "addressee": r.get("addressee") or "economic_operator",
                "applicable_entity": r.get("applicable_entity"),
                "deadline": r.get("deadline"),
                "interpretive": bool(_is_interpretive(r)) or None,
                "requirement_text": r.get("requirement_text"),
            }
            for r in pkg.requirements
        ],
    }


def from_dict(d: Dict[str, Any]) -> Package:
    return Package(
        id=d.get("id"),
        name=d.get("name") or "",
        policy_area=d.get("policy_area"),
        description=d.get("description"),
        applicability=d.get("applicability"),
        is_startup_focused=bool(d.get("is_startup_focused")),
        is_published=bool(d.get("is_published", True)),
        laws=list(d.get("laws") or []),
        requirements=list(d.get("requirements") or []),
    )

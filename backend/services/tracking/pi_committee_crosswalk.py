"""
Policy-Interest crosswalk.

The crosswalk now READS from the canonical taxonomy file
`knowledge_base/policy_taxonomy.json` (enriched 5 Jun 2026 so each leaf carries
its committees / DGs / council configs / agencies / keywords / policy-area
strings / CPV alongside its aliases). That JSON is the single source of truth;
this module is the typed accessor over it.

Back-compat: the module-level `PI_TO_*` dicts and the `*_for_interests()`
functions keep their exact old names/signatures, so the ~17 surfaces and the
stakeholder map that import them are unchanged. New: `cpv_for_interests()` and
the reverse maps (`leaves_for_committee/dg/council_config/agency`) used by the
policy-area classifier (Phase 0b).
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Set

_TAXONOMY_PATH = (
    Path(__file__).resolve().parents[2] / "knowledge_base" / "policy_taxonomy.json"
)


@lru_cache(maxsize=1)
def _leaves() -> List[dict]:
    with _TAXONOMY_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return [pa for c in data.get("categories", []) for pa in c.get("policy_areas", [])]


def _field_map(field: str) -> Dict[str, List[str]]:
    """leaf name -> that leaf's list for `field` (e.g. 'committees')."""
    return {pa["name"]: list(pa.get(field, []) or []) for pa in _leaves()}


def _reverse(field: str) -> Dict[str, List[str]]:
    """code -> [leaf names that list it under `field`] (for the classifier)."""
    out: Dict[str, List[str]] = {}
    for pa in _leaves():
        for code in pa.get(field, []) or []:
            out.setdefault(code, []).append(pa["name"])
    return out


# --- Back-compat module-level dicts (now sourced from the JSON) --------------
PI_TO_COMMITTEES: Dict[str, List[str]] = _field_map("committees")
PI_TO_POLICY_AREAS: Dict[str, List[str]] = _field_map("policy_area_strings")
PI_TO_KEYWORDS: Dict[str, List[str]] = _field_map("keywords")
PI_TO_DGS: Dict[str, List[str]] = _field_map("dgs")
PI_TO_COUNCIL_CONFIGS: Dict[str, List[str]] = _field_map("council_configs")
PI_TO_AGENCIES: Dict[str, List[str]] = _field_map("agencies")
PI_TO_CPV: Dict[str, List[str]] = _field_map("cpv")

# --- Reverse maps: code -> leaf names (classifier / "what interest is this?") -
COMMITTEE_TO_PIS: Dict[str, List[str]] = _reverse("committees")
DG_TO_PIS: Dict[str, List[str]] = _reverse("dgs")
COUNCIL_CONFIG_TO_PIS: Dict[str, List[str]] = _reverse("council_configs")
AGENCY_TO_PIS: Dict[str, List[str]] = _reverse("agencies")


def _union(interests: Iterable[str], mapping: Dict[str, List[str]]) -> Set[str]:
    out: Set[str] = set()
    for leaf in interests or []:
        for code in mapping.get((leaf or "").strip(), []):
            out.add(code)
    return out


def committees_for_interests(interests: Iterable[str]) -> Set[str]:
    """Resolve PI leaf names to the union of their EP committee codes."""
    return _union(interests, PI_TO_COMMITTEES)


def policy_areas_for_interests(interests: Iterable[str]) -> Set[str]:
    """Resolve PI leaf names to the union of carriage policy_area strings to match."""
    return _union(interests, PI_TO_POLICY_AREAS)


def keywords_for_interests(interests: Iterable[str]) -> Set[str]:
    """Lowercase relevance keywords for the user's interests (union)."""
    out: Set[str] = set()
    for leaf in interests or []:
        for kw in PI_TO_KEYWORDS.get((leaf or "").strip(), []):
            out.add(kw.lower())
    return out


def dgs_for_interests(interests: Iterable[str]) -> Set[str]:
    """Resolve PI leaf names to the union of their Commission DG codes."""
    return _union(interests, PI_TO_DGS)


def council_configs_for_interests(interests: Iterable[str]) -> Set[str]:
    """Resolve PI leaf names to the union of their Council configuration codes."""
    return _union(interests, PI_TO_COUNCIL_CONFIGS)


def agencies_for_interests(interests: Iterable[str]) -> Set[str]:
    """Resolve PI leaf names to the union of their EU agency institution codes."""
    return _union(interests, PI_TO_AGENCIES)


def cpv_for_interests(interests: Iterable[str]) -> Set[str]:
    """Resolve PI leaf names to the union of their CPV procurement divisions."""
    return _union(interests, PI_TO_CPV)


# --- Reverse lookups: a code -> the canonical leaf NAMES it belongs to --------
def leaves_for_committee(code: str) -> List[str]:
    return COMMITTEE_TO_PIS.get((code or "").strip(), [])


def leaves_for_dg(code: str) -> List[str]:
    return DG_TO_PIS.get((code or "").strip(), [])


def leaves_for_council_config(code: str) -> List[str]:
    return COUNCIL_CONFIG_TO_PIS.get((code or "").strip(), [])


def leaves_for_agency(code: str) -> List[str]:
    return AGENCY_TO_PIS.get((code or "").strip(), [])

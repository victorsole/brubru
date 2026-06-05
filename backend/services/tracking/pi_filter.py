"""
Shared PI-filter builder (Phase 0c).

ONE place that turns a user's Policy Interests into a SQL WHERE clause, so every
MEUB surface filters identically instead of hand-rolling its own `_pi_clause`.
A surface declares which anchors it exposes (an `AnchorSpec`); the builder emits
a parametrised OR over whatever is available:

    policy_areas && <leaf names>          (the canonical join key, once tagged)
    OR dg/committee/config/agency IN <crosswalk codes>
    OR <text cols> ILIKE <crosswalk keywords>

Returns `(sql, params)` so it works for both raw `text()` surfaces and ORM
surfaces (wrap with `text(sql).bindparams(**params)`). No Anthropic.

Companion: `match_reasons()` explains WHY an item matched (the soft "in your
interests" register).
"""

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Tuple

from services.tracking.pi_committee_crosswalk import (
    agencies_for_interests,
    committees_for_interests,
    council_configs_for_interests,
    dgs_for_interests,
    keywords_for_interests,
)


@dataclass(frozen=True)
class AnchorSpec:
    """Which anchor columns a surface exposes. Use None when absent."""
    policy_areas_col: str | None = None    # text[] of canonical leaf names
    dg_col: str | None = None
    committee_col: str | None = None
    council_config_col: str | None = None
    agency_col: str | None = None
    keyword_cols: Tuple[str, ...] = field(default_factory=tuple)  # text cols to ILIKE


def _in_clause(col: str, codes: Iterable[str], pfx: str, params: Dict) -> str | None:
    codes = sorted({c for c in codes if c})
    if not codes:
        return None
    keys = []
    for i, c in enumerate(codes):
        k = f"{pfx}_{i}"
        params[k] = c
        keys.append(f":{k}")
    return f"{col} IN ({', '.join(keys)})"


def build_pi_clause(
    interests: Iterable[str],
    spec: AnchorSpec,
    pfx: str = "pi",
) -> Tuple[str, Dict]:
    """Return (sql_clause, params). Empty interests -> ('TRUE', {}) (no filter)."""
    interests = [i for i in (interests or []) if i]
    params: Dict = {}
    if not interests:
        return "TRUE", params

    ors: List[str] = []

    # 1. Canonical policy_areas overlap — the primary, precise path. Cast BOTH
    # sides to text[] so the clause works whether the column is text[] or
    # varchar[] (eu_news_items vs legislative_carriages differ).
    if spec.policy_areas_col:
        keys = []
        for i, leaf in enumerate(sorted(set(interests))):
            k = f"{pfx}_pa_{i}"
            params[k] = leaf
            keys.append(f":{k}")
        ors.append(f"{spec.policy_areas_col}::text[] && ARRAY[{', '.join(keys)}]::text[]")

    # 2. Body anchors via the crosswalk.
    for col, codes, sub in (
        (spec.dg_col, dgs_for_interests(interests), "dg"),
        (spec.committee_col, committees_for_interests(interests), "cm"),
        (spec.council_config_col, council_configs_for_interests(interests), "cc"),
        (spec.agency_col, agencies_for_interests(interests), "ag"),
    ):
        if col:
            c = _in_clause(col, codes, f"{pfx}_{sub}", params)
            if c:
                ors.append(c)

    # 3. Keyword ILIKE over text columns (coarse fallback / recall booster).
    if spec.keyword_cols:
        kws = sorted(keywords_for_interests(interests))
        likes = []
        for i, kw in enumerate(kws):
            k = f"{pfx}_kw_{i}"
            params[k] = f"%{kw}%"
            for col in spec.keyword_cols:
                likes.append(f"{col} ILIKE :{k}")
        if likes:
            ors.append("(" + " OR ".join(likes) + ")")

    if not ors:
        return "TRUE", params  # interests set but surface exposes no anchors
    return "(" + " OR ".join(ors) + ")", params


def match_reasons(
    item: Dict,
    interests: Iterable[str],
    spec: AnchorSpec,
) -> List[str]:
    """Plain-language reasons an item matches the user's interests (soft register)."""
    interests = [i for i in (interests or []) if i]
    if not interests:
        return []
    reasons: List[str] = []

    if spec.policy_areas_col:
        pas = set(item.get(spec.policy_areas_col) or [])
        hit = pas & set(interests)
        if hit:
            reasons.append("In your interests: " + ", ".join(sorted(hit)))

    for col, codes, label in (
        (spec.dg_col, dgs_for_interests(interests), "DG"),
        (spec.committee_col, committees_for_interests(interests), "committee"),
        (spec.council_config_col, council_configs_for_interests(interests), "Council"),
        (spec.agency_col, agencies_for_interests(interests), "agency"),
    ):
        if col and item.get(col) and item.get(col) in codes:
            reasons.append(f"Matches a {label} you follow ({item.get(col)})")

    return reasons

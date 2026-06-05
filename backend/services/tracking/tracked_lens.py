"""
My Tracked Files as a saved lens (Phase 0d).

Turns the user's tracked legislative files into a set of HARD anchors
(procedures / CELEX / committees) that any MEUB surface can filter or flag by —
the "touches a file you track" assertion (hard register), distinct from the
softer PI suggestions (see pi_filter.match_reasons).

    anchors = tracked_anchors(db, user_id)
    sql, params = tracked_clause(anchors, TrackedSpec(procedure_col="oeil_procedure_ref"))
    reasons = tracked_reasons(item, anchors, spec)
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session


def tracked_anchors(db: Session, user_id: str) -> Dict[str, set]:
    """The anchor set across a user's (non-archived) tracked files.

    `procedures`/`celex`/`committees` are the HARD anchors (exact doc refs) used
    where a surface carries them. `policy_areas` is the topical fallback for
    surfaces with no doc-ref column (e.g. News) — "related to files you track".
    """
    out = {"procedures": set(), "celex": set(), "committees": set(), "policy_areas": set()}
    if not user_id:
        return out
    try:
        rows = db.execute(
            text(
                """
                SELECT lc.oeil_procedure_ref AS proc, lc.celex_numbers AS celex,
                       lc.lead_committee AS committee, lc.policy_areas AS policy_areas
                FROM user_carriage_tracks uct
                JOIN legislative_carriages lc ON lc.id = uct.carriage_id
                WHERE uct.user_id = :uid AND uct.archived_at IS NULL
                """
            ),
            {"uid": user_id},
        ).mappings().all()
    except Exception:
        db.rollback()
        return out
    for r in rows:
        if r["proc"]:
            out["procedures"].add(r["proc"])
        for cx in (r["celex"] or []):
            out["celex"].add(cx)
        if r["committee"]:
            out["committees"].add(r["committee"])
        for pa in (r["policy_areas"] or []):
            out["policy_areas"].add(pa)
    return out


@dataclass(frozen=True)
class TrackedSpec:
    """Which hard-anchor columns a surface exposes for tracked-file matching."""
    procedure_col: str | None = None
    celex_col: str | None = None          # scalar column matched against the tracked CELEX set
    committee_col: str | None = None


def _in(col: str, values: set, pfx: str, params: Dict) -> str | None:
    vals = sorted({v for v in values if v})
    if not vals:
        return None
    keys = []
    for i, v in enumerate(vals):
        k = f"{pfx}_{i}"
        params[k] = v
        keys.append(f":{k}")
    return f"{col} IN ({', '.join(keys)})"


def tracked_clause(
    anchors: Dict[str, set],
    spec: TrackedSpec,
    pfx: str = "trk",
) -> Tuple[str, Dict]:
    """(sql, params) hard-match clause. No tracked anchors / cols -> ('FALSE', {})."""
    params: Dict = {}
    ors: List[str] = []
    if spec.procedure_col:
        c = _in(spec.procedure_col, anchors.get("procedures", set()), f"{pfx}_p", params)
        if c:
            ors.append(c)
    if spec.celex_col:
        c = _in(spec.celex_col, anchors.get("celex", set()), f"{pfx}_x", params)
        if c:
            ors.append(c)
    if spec.committee_col:
        c = _in(spec.committee_col, anchors.get("committees", set()), f"{pfx}_c", params)
        if c:
            ors.append(c)
    if not ors:
        return "FALSE", params  # nothing tracked, or surface exposes no hard anchor
    return "(" + " OR ".join(ors) + ")", params


def tracked_reasons(item: Dict, anchors: Dict[str, set], spec: TrackedSpec) -> List[str]:
    """Plain-language "touches a file you track" reasons (hard register)."""
    reasons: List[str] = []
    if spec.procedure_col and item.get(spec.procedure_col) in anchors.get("procedures", set()):
        reasons.append(f"Touches a file you track ({item.get(spec.procedure_col)})")
    if spec.celex_col and item.get(spec.celex_col) in anchors.get("celex", set()):
        reasons.append(f"Touches a law you track ({item.get(spec.celex_col)})")
    if spec.committee_col and item.get(spec.committee_col) in anchors.get("committees", set()):
        reasons.append(f"In a committee you follow ({item.get(spec.committee_col)})")
    return reasons

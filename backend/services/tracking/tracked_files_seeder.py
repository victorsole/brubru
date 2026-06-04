"""
Auto-populate My Tracked Files from a user's MEUB Policy Interests.

v1 scope (agreed 30 May 2026):
  source  = OEIL-referenced carriages (oeil_procedure_ref not null)
  filter  = ongoing only (exclude COMPLETED / ADOPTED / WITHDRAWN)
  match   = lead_committee in the committees resolved from the user's PI leaves
  action  = create pre-checked UserCarriageTrack rows (idempotent; never duplicates)

No new scraping and no reliance on the dirty carriages.policy_areas field. The
committee coverage is lifted first by backfill_committee_from_oeil_cache.py.
"""

import logging
import re
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from models.user import User
from models.legislative_train import LegislativeCarriage, UserCarriageTrack
from services.tracking.pi_committee_crosswalk import (
    committees_for_interests,
    policy_areas_for_interests,
    keywords_for_interests,
)

logger = logging.getLogger(__name__)

# Concluded statuses are NOT work-in-progress -> excluded from auto-population.
CONCLUDED_STATUSES = {"COMPLETED", "ADOPTED", "WITHDRAWN"}

# Only auto-track SUBSTANTIVE procedures: new laws (COD/CNS/APP), Parliament
# positions (INI/INL/RSP), agreements/appointments (NLE), budget (BUD/DEC).
# Deliberately excludes:
#   - non-procedures: SWD(...)/COM(...) document numbers (those belong in Commission Docs),
#   - scrutiny (DEA/RPS) and housekeeping (IMM/REG/RSO), which are technical noise
#     for a default tracked list (the user can still add them by hand).
# Postgres regex anchored to a real "YYYY/NNNN(TYPE)" procedure reference.
SEEDABLE_REF_REGEX = r"^[0-9]{4}/[0-9]{4}\((COD|CNS|APP|INI|INL|RSP|NLE|BUD|DEC)\)"

# Cap per sync so a broad-interest user is not flooded; they prune/add by hand after.
DEFAULT_LIMIT = 60

# "Procedure File: 2025/2880(RSP)" placeholder — OEIL backfills that never got a
# real descriptive title. Unintelligible on a card, so never auto-track them.
_PLACEHOLDER_TITLE_RE = re.compile(r"^\s*Procedure File:\s*\d{4}/\d+\([A-Z]+\)", re.IGNORECASE)


def _status_str(carriage: LegislativeCarriage) -> str:
    val = getattr(carriage.current_status, "value", carriage.current_status)
    return str(val or "").upper()


def _has_real_title(carriage: LegislativeCarriage) -> bool:
    title = (carriage.title or "").strip()
    if len(title) < 10:
        return False
    return not _PLACEHOLDER_TITLE_RE.match(title)


def _matches_interest_topic(carriage: LegislativeCarriage, keywords: set) -> bool:
    """Topic-relevance gate: the file must actually mention the user's topic.

    Committee/policy matching is a coarse proxy (ENVI = env + health + food), so we
    require a keyword hit in the title or AI summary. Fails open when no keywords are
    defined for the user's interests (so we never block everything by accident).
    """
    if not keywords:
        return True
    haystack = f"{carriage.title or ''} {carriage.ai_summary or ''}".lower()
    return any(kw in haystack for kw in keywords)


def _interest_list(user: User) -> list[str]:
    raw = getattr(user, "policy_interests_list", None)
    if raw is None:
        raw = getattr(user, "policy_interests", None)
    if isinstance(raw, str):
        import json
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            raw = [raw]
    return [str(x) for x in (raw or []) if x]


def sync_tracked_files_from_interests(
    db: Session,
    user: User,
    limit: int = DEFAULT_LIMIT,
) -> dict:
    """
    Seed pre-checked tracked files for the user's policy interests.

    Returns a summary dict: {seeded, committees, candidates, already_tracked}.
    Idempotent: never creates a track the user already has.
    """
    interests = _interest_list(user)
    committees = sorted(committees_for_interests(interests))
    policy_areas = sorted(policy_areas_for_interests(interests))
    keywords = keywords_for_interests(interests)
    summary = {
        "seeded": 0,
        "committees": committees,
        "policy_areas": policy_areas,
        "candidates": 0,
        "already_tracked": 0,
    }

    if not committees and not policy_areas:
        logger.info("Tracked-files sync: user %s has no mappable interests", user.id)
        return summary

    already = {
        t.carriage_id
        for t in db.query(UserCarriageTrack.carriage_id)
        .filter(UserCarriageTrack.user_id == user.id)
        .all()
    }
    summary["already_tracked"] = len(already)

    # Match on committee (primary, reliable) OR policy_areas overlap (secondary,
    # catches committee-less plenary resolutions). Restricted to real, substantive
    # procedure references so SWD/COM documents and scrutiny noise never seed.
    match_clauses = []
    if committees:
        match_clauses.append(LegislativeCarriage.lead_committee.in_(committees))
    if policy_areas:
        match_clauses.append(LegislativeCarriage.policy_areas.overlap(policy_areas))

    candidates = (
        db.query(LegislativeCarriage)
        .filter(
            LegislativeCarriage.oeil_procedure_ref.op("~")(SEEDABLE_REF_REGEX),
            or_(*match_clauses),
        )
        .order_by(LegislativeCarriage.oeil_procedure_ref.desc())
        .all()
    )
    summary["candidates"] = len(candidates)

    seeded = 0
    for carriage in candidates:
        if seeded >= limit:
            break
        if carriage.id in already:
            continue
        if _status_str(carriage) in CONCLUDED_STATUSES:
            continue
        if not _has_real_title(carriage):
            continue
        if not _matches_interest_topic(carriage, keywords):
            continue
        db.add(UserCarriageTrack(user_id=user.id, carriage_id=carriage.id))
        already.add(carriage.id)
        seeded += 1

    if seeded:
        db.commit()
    summary["seeded"] = seeded
    logger.info(
        "Tracked-files sync: user %s committees=%s seeded=%d (candidates=%d)",
        user.id, committees, seeded, summary["candidates"],
    )
    return summary

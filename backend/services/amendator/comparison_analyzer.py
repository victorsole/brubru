"""
Comparison Analyzer Service

Pure computation (no AI calls) on cached alignment scores.
Produces best allies, coverage gaps, and political landscape analysis.

Phase 4 of MEP Amendments feature.

Created: February 2026
"""

import logging
from collections import defaultdict
from typing import Dict, Any, List
from uuid import UUID

from sqlalchemy.orm import Session

from models.alignment_score import AlignmentScore
from models.mep_amendment import MEPAmendment
from models.amendment import Amendment

logger = logging.getLogger(__name__)


def get_comparison(
    db: Session,
    user_id: UUID,
    procedure_ref: str,
    policy_position_hash: str,
) -> Dict[str, Any]:
    """
    Compute comparative analysis from cached alignment scores.

    Returns: {best_allies, coverage_gaps, political_landscape}
    """
    # Load all alignment scores for this user + procedure + position
    scores = db.query(AlignmentScore).filter(
        AlignmentScore.user_id == user_id,
        AlignmentScore.procedure_reference == procedure_ref,
        AlignmentScore.policy_position_hash == policy_position_hash,
    ).all()

    if not scores:
        return {
            'best_allies': [],
            'coverage_gaps': {'user_unique': [], 'blind_spots': []},
            'political_landscape': {'supportive': [], 'mixed': [], 'opposed': []},
        }

    # Load MEP amendments for metadata
    score_amendment_ids = [s.mep_amendment_id for s in scores]
    mep_amendments = db.query(MEPAmendment).filter(
        MEPAmendment.id.in_(score_amendment_ids)
    ).all()
    amendment_map = {a.id: a for a in mep_amendments}

    best_allies = _compute_best_allies(scores, amendment_map)
    coverage_gaps = _compute_coverage_gaps(db, user_id, procedure_ref, mep_amendments)
    political_landscape = _compute_political_landscape(scores, amendment_map)

    return {
        'best_allies': best_allies,
        'coverage_gaps': coverage_gaps,
        'political_landscape': political_landscape,
    }


def _compute_best_allies(
    scores: List[AlignmentScore],
    amendment_map: Dict[UUID, MEPAmendment],
) -> List[Dict[str, Any]]:
    """
    Rank MEPs by average alignment score.
    Returns top 15 allies with name, group, avg score, amendment count.
    """
    # Group scores by author
    author_scores: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        'total_score': 0,
        'count': 0,
        'group': None,
    })

    for s in scores:
        amendment = amendment_map.get(s.mep_amendment_id)
        if not amendment or not amendment.author_names:
            continue

        for author in amendment.author_names:
            entry = author_scores[author]
            entry['total_score'] += s.score
            entry['count'] += 1
            if not entry['group'] and amendment.political_group:
                entry['group'] = amendment.political_group

    # Compute averages and sort
    allies = []
    for name, data in author_scores.items():
        if data['count'] == 0:
            continue
        allies.append({
            'name': name,
            'group': data['group'] or 'Unknown',
            'avg_score': round(data['total_score'] / data['count'], 2),
            'count': data['count'],
        })

    allies.sort(key=lambda x: x['avg_score'], reverse=True)
    return allies[:15]


def _compute_coverage_gaps(
    db: Session,
    user_id: UUID,
    procedure_ref: str,
    mep_amendments: List[MEPAmendment],
) -> Dict[str, List[str]]:
    """
    Compare user's amended elements vs MEP amended elements.

    Returns:
      user_unique: elements the user amended that no MEP touched
      blind_spots: elements MEPs amended that the user hasn't
    """
    # Get user's amendments for this procedure
    user_amendments = db.query(Amendment).filter(
        Amendment.user_id == user_id,
        Amendment.procedure_reference == procedure_ref,
    ).all()

    # Normalise element references for comparison
    user_elements = set()
    for a in user_amendments:
        ref = _normalise_element_ref(a.position_text)
        if ref:
            user_elements.add(ref)

    mep_elements = set()
    for a in mep_amendments:
        ref = _normalise_element_ref(a.element_reference)
        if ref:
            mep_elements.add(ref)

    user_unique = sorted(user_elements - mep_elements)
    blind_spots = sorted(mep_elements - user_elements)

    # Limit to top 20 each for readability
    return {
        'user_unique': user_unique[:20],
        'blind_spots': blind_spots[:20],
    }


def _normalise_element_ref(ref: str) -> str:
    """Normalise element reference for comparison (lowercase, strip whitespace)."""
    if not ref:
        return ''
    return ref.strip().lower()


def _compute_political_landscape(
    scores: List[AlignmentScore],
    amendment_map: Dict[UUID, MEPAmendment],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group alignment scores by political group.

    Classify groups as:
      supportive: avg score >= 1.0
      mixed: avg score between -0.5 and 1.0
      opposed: avg score < -0.5

    Returns three lists, each with: {group, avg_score, count}
    """
    group_data: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        'total_score': 0,
        'count': 0,
    })

    for s in scores:
        amendment = amendment_map.get(s.mep_amendment_id)
        if not amendment:
            continue
        group = amendment.political_group or 'Unknown'
        group_data[group]['total_score'] += s.score
        group_data[group]['count'] += 1

    supportive = []
    mixed = []
    opposed = []

    for group, data in group_data.items():
        if data['count'] == 0:
            continue
        avg = round(data['total_score'] / data['count'], 2)
        entry = {
            'group': group,
            'avg_score': avg,
            'count': data['count'],
        }

        if avg >= 1.0:
            supportive.append(entry)
        elif avg < -0.5:
            opposed.append(entry)
        else:
            mixed.append(entry)

    # Sort each list by avg_score
    supportive.sort(key=lambda x: x['avg_score'], reverse=True)
    mixed.sort(key=lambda x: x['avg_score'], reverse=True)
    opposed.sort(key=lambda x: x['avg_score'])

    return {
        'supportive': supportive,
        'mixed': mixed,
        'opposed': opposed,
    }

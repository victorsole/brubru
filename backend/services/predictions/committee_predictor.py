"""
Committee Predictor - Phase 4.3

Predicts EP committee vote outcomes based on composition.

Uses:
- Committee political balance
- Rapporteur group
- Shadow rapporteur positions
- Historical committee voting patterns

Usage:
    predictor = CommitteePredictor()
    result = await predictor.predict_committee_vote("LIBE", "2024/0138(COD)")
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy.orm import Session

from core.database import SessionLocal

logger = logging.getLogger(__name__)


class CommitteeVoteOutcome(str, Enum):
    """Possible committee vote outcomes."""
    APPROVE = "approve"
    REJECT = "reject"
    AMEND_HEAVILY = "amend_heavily"
    SPLIT = "split"


@dataclass
class CommitteeComposition:
    """Political composition of a committee."""
    committee_code: str
    committee_name: str
    total_members: int
    full_members: int
    substitutes: int

    # By group (full members only for voting)
    group_seats: Dict[str, int] = field(default_factory=dict)

    # Chair and coordinators
    chair_group: Optional[str] = None
    vice_chair_groups: List[str] = field(default_factory=list)

    # Political balance
    pro_eu_seats: int = 0  # EPP + S&D + Renew + Greens
    eurosceptic_seats: int = 0  # ECR + PfE + ESN + some NI


@dataclass
class CommitteeVotePrediction:
    """Prediction for a committee vote."""
    committee_code: str
    committee_name: str
    procedure_ref: str

    # Prediction
    predicted_outcome: CommitteeVoteOutcome
    confidence: float
    expected_margin: int  # Positive = approve, negative = reject

    # Vote breakdown
    estimated_for: int = 0
    estimated_against: int = 0
    estimated_abstain: int = 0

    # Key factors
    rapporteur_group: Optional[str] = None
    shadow_positions: Dict[str, str] = field(default_factory=dict)
    composition: Optional[CommitteeComposition] = None

    # Risk factors
    amendment_risk: str = "low"  # low, moderate, high
    key_groups_to_watch: List[str] = field(default_factory=list)


class CommitteePredictor:
    """
    Predicts committee vote outcomes.

    Uses committee composition and political dynamics.
    """

    # EP Committee data (10th term, 2024-2029)
    # Format: {code: (name, full_members, substitutes)}
    COMMITTEES = {
        'AFET': ('Foreign Affairs', 71, 71),
        'DROI': ('Human Rights', 30, 22),
        'SEDE': ('Security and Defence', 30, 22),
        'DEVE': ('Development', 26, 24),
        'INTA': ('International Trade', 43, 42),
        'BUDG': ('Budgets', 41, 41),
        'CONT': ('Budgetary Control', 30, 30),
        'ECON': ('Economic and Monetary Affairs', 60, 60),
        'EMPL': ('Employment and Social Affairs', 55, 55),
        'ENVI': ('Environment, Public Health and Food Safety', 88, 88),
        'ITRE': ('Industry, Research and Energy', 78, 78),
        'IMCO': ('Internal Market and Consumer Protection', 45, 45),
        'TRAN': ('Transport and Tourism', 49, 49),
        'REGI': ('Regional Development', 43, 43),
        'AGRI': ('Agriculture and Rural Development', 48, 48),
        'PECH': ('Fisheries', 28, 28),
        'CULT': ('Culture and Education', 31, 31),
        'JURI': ('Legal Affairs', 26, 26),
        'LIBE': ('Civil Liberties, Justice and Home Affairs', 68, 68),
        'AFCO': ('Constitutional Affairs', 28, 28),
        'FEMM': ('Women\'s Rights and Gender Equality', 35, 35),
        'PETI': ('Petitions', 35, 35),
    }

    # Typical committee political balance (estimated distribution)
    # Based on d'Hondt allocation proportional to EP seats
    DEFAULT_GROUP_RATIOS = {
        'EPP': 0.267,
        'S&D': 0.193,
        'PfE': 0.119,
        'ECR': 0.111,
        'Renew': 0.109,
        'Greens/EFA': 0.075,
        'The Left': 0.065,
        'ESN': 0.035,
        'NI': 0.026,
    }

    # Group coalitions for vote estimation
    PRO_EU_GROUPS = {'EPP', 'S&D', 'Renew', 'Greens/EFA'}
    EUROSCEPTIC_GROUPS = {'ECR', 'PfE', 'ESN'}

    # Committee names
    COMMITTEE_NAMES = {code: data[0] for code, data in COMMITTEES.items()}

    def __init__(self, db: Optional[Session] = None):
        self._db = db
        self._owns_db = db is None
        self._composition_cache: Dict[str, CommitteeComposition] = {}

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def close(self):
        """Close database session if we own it."""
        if self._owns_db and self._db:
            self._db.close()
            self._db = None

    def get_committee_composition(
        self,
        committee_code: str
    ) -> Optional[CommitteeComposition]:
        """
        Get the political composition of a committee.

        Uses cached data or calculates from default ratios.
        """
        code = committee_code.upper()

        if code in self._composition_cache:
            return self._composition_cache[code]

        if code not in self.COMMITTEES:
            return None

        name, full_members, substitutes = self.COMMITTEES[code]

        # Calculate seat distribution using default ratios
        group_seats = {}
        allocated = 0

        for group, ratio in sorted(self.DEFAULT_GROUP_RATIOS.items(), key=lambda x: -x[1]):
            seats = int(full_members * ratio)
            group_seats[group] = seats
            allocated += seats

        # Distribute remaining seats to largest groups
        remaining = full_members - allocated
        for group in ['EPP', 'S&D', 'PfE', 'ECR', 'Renew']:
            if remaining <= 0:
                break
            group_seats[group] = group_seats.get(group, 0) + 1
            remaining -= 1

        # Calculate political balance
        pro_eu = sum(group_seats.get(g, 0) for g in self.PRO_EU_GROUPS)
        eurosceptic = sum(group_seats.get(g, 0) for g in self.EUROSCEPTIC_GROUPS)

        composition = CommitteeComposition(
            committee_code=code,
            committee_name=name,
            total_members=full_members + substitutes,
            full_members=full_members,
            substitutes=substitutes,
            group_seats=group_seats,
            pro_eu_seats=pro_eu,
            eurosceptic_seats=eurosceptic
        )

        self._composition_cache[code] = composition
        return composition

    def _estimate_group_position(
        self,
        group: str,
        rapporteur_group: Optional[str],
        policy_area: Optional[str] = None
    ) -> str:
        """Estimate a group's position based on rapporteur and policy."""
        # Simplified position estimation
        # In practice, would use historical voting data

        # Groups tend to support their own rapporteurs
        if group == rapporteur_group:
            return 'FOR'

        # Pro-EU coalition typically votes together on mainstream legislation
        if group in self.PRO_EU_GROUPS and rapporteur_group in self.PRO_EU_GROUPS:
            return 'FOR'

        # Eurosceptic groups often oppose mainstream proposals
        if group in self.EUROSCEPTIC_GROUPS:
            if rapporteur_group in self.PRO_EU_GROUPS:
                return 'AGAINST'
            return 'ABSTAIN'

        # The Left - depends on policy area
        if group == 'The Left':
            if policy_area in ['social', 'environment', 'employment']:
                return 'FOR'
            elif policy_area in ['economic', 'trade']:
                return 'AGAINST'

        return 'ABSTAIN'

    async def predict_committee_vote(
        self,
        committee_code: str,
        procedure_ref: str,
        rapporteur_group: Optional[str] = None,
        shadow_positions: Optional[Dict[str, str]] = None,
        policy_area: Optional[str] = None
    ) -> CommitteeVotePrediction:
        """
        Predict the outcome of a committee vote.

        Args:
            committee_code: EP committee code
            procedure_ref: OEIL procedure reference
            rapporteur_group: Rapporteur's political group
            shadow_positions: Known shadow rapporteur positions {group: position}
            policy_area: Policy area for context

        Returns:
            CommitteeVotePrediction with outcome and breakdown
        """
        composition = self.get_committee_composition(committee_code)

        if not composition:
            return CommitteeVotePrediction(
                committee_code=committee_code,
                committee_name=self.COMMITTEE_NAMES.get(committee_code, committee_code),
                procedure_ref=procedure_ref,
                predicted_outcome=CommitteeVoteOutcome.SPLIT,
                confidence=0.3,
                expected_margin=0
            )

        shadow_positions = shadow_positions or {}

        # Estimate votes by group
        estimated_for = 0
        estimated_against = 0
        estimated_abstain = 0
        key_groups = []

        for group, seats in composition.group_seats.items():
            if seats == 0:
                continue

            # Use shadow position if known, otherwise estimate
            if group in shadow_positions:
                position = shadow_positions[group].upper()
            else:
                position = self._estimate_group_position(
                    group, rapporteur_group, policy_area
                )

            # Allocate votes (accounting for some internal dissent)
            cohesion = 0.85  # Assume 85% vote with group line

            if position == 'FOR':
                estimated_for += int(seats * cohesion)
                estimated_against += int(seats * (1 - cohesion) * 0.5)
                estimated_abstain += int(seats * (1 - cohesion) * 0.5)
            elif position == 'AGAINST':
                estimated_against += int(seats * cohesion)
                estimated_for += int(seats * (1 - cohesion) * 0.3)
                estimated_abstain += int(seats * (1 - cohesion) * 0.7)
            else:
                estimated_abstain += int(seats * cohesion)
                estimated_for += int(seats * (1 - cohesion) * 0.5)
                estimated_against += int(seats * (1 - cohesion) * 0.5)

            # Track groups that could swing the vote
            if seats >= 5 and group not in shadow_positions:
                key_groups.append(group)

        # Calculate margin and outcome
        margin = estimated_for - estimated_against
        total_votes = estimated_for + estimated_against + estimated_abstain

        # Determine outcome
        if margin > total_votes * 0.1:
            outcome = CommitteeVoteOutcome.APPROVE
            confidence = min(0.9, 0.5 + margin / total_votes)
        elif margin < -total_votes * 0.1:
            outcome = CommitteeVoteOutcome.REJECT
            confidence = min(0.9, 0.5 + abs(margin) / total_votes)
        elif abs(margin) < total_votes * 0.05:
            outcome = CommitteeVoteOutcome.SPLIT
            confidence = 0.4
        else:
            outcome = CommitteeVoteOutcome.AMEND_HEAVILY
            confidence = 0.5

        # Assess amendment risk
        if outcome in (CommitteeVoteOutcome.SPLIT, CommitteeVoteOutcome.AMEND_HEAVILY):
            amendment_risk = "high"
        elif margin < total_votes * 0.2:
            amendment_risk = "moderate"
        else:
            amendment_risk = "low"

        return CommitteeVotePrediction(
            committee_code=committee_code,
            committee_name=composition.committee_name,
            procedure_ref=procedure_ref,
            predicted_outcome=outcome,
            confidence=confidence,
            expected_margin=margin,
            estimated_for=estimated_for,
            estimated_against=estimated_against,
            estimated_abstain=estimated_abstain,
            rapporteur_group=rapporteur_group,
            shadow_positions=shadow_positions,
            composition=composition,
            amendment_risk=amendment_risk,
            key_groups_to_watch=key_groups[:3]
        )

    def get_committee_info(self, committee_code: str) -> Optional[Dict[str, Any]]:
        """Get basic information about a committee."""
        code = committee_code.upper()
        if code not in self.COMMITTEES:
            return None

        name, full_members, substitutes = self.COMMITTEES[code]
        composition = self.get_committee_composition(code)

        return {
            'code': code,
            'name': name,
            'full_members': full_members,
            'substitutes': substitutes,
            'total': full_members + substitutes,
            'group_distribution': composition.group_seats if composition else {},
            'pro_eu_balance': composition.pro_eu_seats if composition else 0,
            'eurosceptic_balance': composition.eurosceptic_seats if composition else 0
        }


# Singleton instance
_predictor_instance: Optional[CommitteePredictor] = None


def get_committee_predictor() -> CommitteePredictor:
    """Get or create the committee predictor instance."""
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = CommitteePredictor()
    return _predictor_instance

"""
Group Vote Predictor - Phase 3.1

Predicts EP political group voting positions on legislative procedures.

Features used:
- Policy area (committee)
- Rapporteur's group
- Shadow rapporteur positions
- Historical voting patterns on similar votes
- Group cohesion in policy area

Usage:
    predictor = GroupVotePredictor()
    prediction = await predictor.predict_group_position("EPP", "2024/0138(COD)")
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from core.database import SessionLocal
from .cohesion_analyzer import CohesionAnalyzer, get_cohesion_analyzer

logger = logging.getLogger(__name__)


class VotePosition(str, Enum):
    """Predicted vote position."""
    FOR = "FOR"
    AGAINST = "AGAINST"
    ABSTENTION = "ABSTENTION"
    SPLIT = "SPLIT"  # Group likely to split


@dataclass
class GroupPositionPrediction:
    """Prediction for a single group's position."""
    group_code: str
    group_name: str
    predicted_position: VotePosition
    confidence: float  # 0.0-1.0
    expected_cohesion: float  # How unified the vote is expected to be

    # Position probabilities
    prob_for: float = 0.0
    prob_against: float = 0.0
    prob_abstention: float = 0.0

    # Factors influencing prediction
    factors: List[Dict[str, Any]] = field(default_factory=list)

    # Historical reference
    similar_votes: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class PlenaryVotePrediction:
    """Aggregated prediction for a plenary vote."""
    procedure_ref: str
    predicted_outcome: str  # 'PASS', 'FAIL', 'UNCERTAIN'

    # Optional fields with defaults
    title: Optional[str] = None
    confidence: float = 0.0
    predicted_margin: int = 0  # Estimated vote margin (+/-)

    # Vote breakdown
    estimated_for: int = 0
    estimated_against: int = 0
    estimated_abstention: int = 0
    total_meps: int = 705

    # Group-level predictions
    group_predictions: List[GroupPositionPrediction] = field(default_factory=list)

    # Risk factors
    swing_groups: List[str] = field(default_factory=list)  # Groups that could swing outcome
    key_delegations: List[str] = field(default_factory=list)  # Delegations to watch


class GroupVotePredictor:
    """
    Predicts EP group voting positions.

    Uses historical voting patterns and cohesion analysis.
    """

    # EP Group seat counts (10th term, 2024-2029)
    GROUP_SEATS = {
        'EPP': 188,
        'S&D': 136,
        'PfE': 84,  # Patriots for Europe (formerly ID)
        'ECR': 78,
        'Renew': 77,
        'Greens/EFA': 53,
        'The Left': 46,
        'ESN': 25,  # Europe of Sovereign Nations
        'NI': 33,
    }

    # Group typical positions by policy area (baseline)
    BASELINE_POSITIONS = {
        'EPP': {'default': 0.6, 'economic': 0.7, 'social': 0.5, 'environment': 0.4},
        'S&D': {'default': 0.7, 'economic': 0.4, 'social': 0.8, 'environment': 0.7},
        'Renew': {'default': 0.65, 'economic': 0.7, 'social': 0.6, 'environment': 0.6},
        'Greens/EFA': {'default': 0.5, 'economic': 0.3, 'social': 0.8, 'environment': 0.9},
        'ECR': {'default': 0.4, 'economic': 0.6, 'social': 0.3, 'environment': 0.2},
        'PfE': {'default': 0.2, 'economic': 0.4, 'social': 0.2, 'environment': 0.1},
        'The Left': {'default': 0.4, 'economic': 0.2, 'social': 0.8, 'environment': 0.7},
        'ESN': {'default': 0.1, 'economic': 0.3, 'social': 0.1, 'environment': 0.1},
        'NI': {'default': 0.3, 'economic': 0.3, 'social': 0.3, 'environment': 0.3},
    }

    # Group names
    GROUP_NAMES = {
        'EPP': 'European People\'s Party',
        'S&D': 'Socialists & Democrats',
        'Renew': 'Renew Europe',
        'Greens/EFA': 'Greens/European Free Alliance',
        'ECR': 'European Conservatives and Reformists',
        'PfE': 'Patriots for Europe',
        'The Left': 'The Left in the EP',
        'ESN': 'Europe of Sovereign Nations',
        'NI': 'Non-Inscrits',
    }

    def __init__(self, db: Optional[Session] = None):
        self._db = db
        self._owns_db = db is None
        self._cohesion_analyzer = None

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    @property
    def cohesion_analyzer(self) -> CohesionAnalyzer:
        if self._cohesion_analyzer is None:
            self._cohesion_analyzer = CohesionAnalyzer(self.db)
        return self._cohesion_analyzer

    def close(self):
        """Close database session if we own it."""
        if self._owns_db and self._db:
            self._db.close()
            self._db = None

    def _get_policy_category(self, lead_committee: Optional[str]) -> str:
        """Map committee to policy category."""
        economic = ['ECON', 'BUDG', 'CONT', 'INTA', 'IMCO']
        social = ['EMPL', 'CULT', 'FEMM', 'LIBE', 'PETI']
        environment = ['ENVI', 'AGRI', 'PECH', 'TRAN', 'ITRE']

        if lead_committee in economic:
            return 'economic'
        elif lead_committee in social:
            return 'social'
        elif lead_committee in environment:
            return 'environment'
        return 'default'

    async def _get_historical_position(
        self,
        group_code: str,
        procedure_ref: str
    ) -> Optional[Dict[str, float]]:
        """
        Look up historical voting on similar procedures.

        Returns position probabilities based on past votes.
        """
        try:
            from models.ep_voting import EPVote, EPMemberVote, EPMember, EPGroupMembership

            # Extract procedure type
            import re
            proc_match = re.search(r'\(([A-Z]{3})\)', procedure_ref)
            proc_type = proc_match.group(1) if proc_match else None

            if not proc_type:
                return None

            # Get votes on similar procedure types from last 2 years
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=730)

            # Query historical votes for this group on similar procedures
            results = self.db.query(
                EPMemberVote.position,
                func.count(EPMemberVote.id).label('count')
            ).join(
                EPMember,
                EPMemberVote.member_id == EPMember.id
            ).join(
                EPGroupMembership,
                and_(
                    EPGroupMembership.member_id == EPMember.id,
                    EPGroupMembership.group_code == group_code
                )
            ).join(
                EPVote,
                EPMemberVote.vote_id == EPVote.id
            ).filter(
                EPVote.procedure_reference.contains(f"({proc_type})"),
                EPVote.timestamp >= start_date
            ).group_by(
                EPMemberVote.position
            ).all()

            if not results:
                return None

            # Calculate position probabilities
            total = sum(r.count for r in results)
            probs = {'FOR': 0.0, 'AGAINST': 0.0, 'ABSTENTION': 0.0}

            for position, count in results:
                pos_str = position.value if hasattr(position, 'value') else str(position)
                if pos_str in probs:
                    probs[pos_str] = count / total

            return probs

        except ImportError:
            return None
        except Exception as e:
            logger.error(f"Error getting historical position: {e}")
            return None

    async def predict_group_position(
        self,
        group_code: str,
        procedure_ref: str,
        lead_committee: Optional[str] = None,
        rapporteur_group: Optional[str] = None
    ) -> GroupPositionPrediction:
        """
        Predict a group's position on a procedure.

        Args:
            group_code: EP group code
            procedure_ref: OEIL procedure reference
            lead_committee: Lead committee code
            rapporteur_group: Rapporteur's political group

        Returns:
            GroupPositionPrediction with position and confidence
        """
        factors = []

        # 1. Get baseline position based on policy area
        policy_cat = self._get_policy_category(lead_committee)
        baseline = self.BASELINE_POSITIONS.get(group_code, {}).get(
            policy_cat,
            self.BASELINE_POSITIONS.get(group_code, {}).get('default', 0.5)
        )
        factors.append({
            'factor': 'policy_baseline',
            'value': policy_cat,
            'influence': baseline
        })

        # 2. Adjust for rapporteur group relationship
        rapporteur_bonus = 0.0
        if rapporteur_group:
            if rapporteur_group == group_code:
                rapporteur_bonus = 0.25  # Own rapporteur = strong support
                factors.append({
                    'factor': 'own_rapporteur',
                    'value': True,
                    'influence': rapporteur_bonus
                })
            elif self._are_allied_groups(group_code, rapporteur_group):
                rapporteur_bonus = 0.10  # Allied group rapporteur
                factors.append({
                    'factor': 'allied_rapporteur',
                    'value': rapporteur_group,
                    'influence': rapporteur_bonus
                })
            elif self._are_opposed_groups(group_code, rapporteur_group):
                rapporteur_bonus = -0.15  # Opposed group rapporteur
                factors.append({
                    'factor': 'opposed_rapporteur',
                    'value': rapporteur_group,
                    'influence': rapporteur_bonus
                })

        # 3. Get historical voting patterns
        historical = await self._get_historical_position(group_code, procedure_ref)
        if historical:
            # Weight historical data
            historical_for = historical.get('FOR', 0.0)
            factors.append({
                'factor': 'historical_pattern',
                'value': f"{historical_for:.0%} FOR on similar",
                'influence': historical_for
            })
            # Blend baseline with historical
            baseline = 0.6 * baseline + 0.4 * historical_for

        # 4. Get expected cohesion
        cohesion_result = await self.cohesion_analyzer.calculate_group_cohesion(group_code)
        expected_cohesion = cohesion_result.cohesion_score if cohesion_result else 0.75

        # 5. Calculate final probabilities
        prob_for = min(1.0, max(0.0, baseline + rapporteur_bonus))
        prob_against = min(1.0, max(0.0, 1.0 - prob_for - 0.1))
        prob_abstention = 1.0 - prob_for - prob_against

        # Normalize
        total = prob_for + prob_against + prob_abstention
        prob_for /= total
        prob_against /= total
        prob_abstention /= total

        # Determine predicted position
        if expected_cohesion < 0.60:
            predicted_position = VotePosition.SPLIT
            confidence = 0.4
        elif prob_for > 0.5:
            predicted_position = VotePosition.FOR
            confidence = prob_for * expected_cohesion
        elif prob_against > 0.5:
            predicted_position = VotePosition.AGAINST
            confidence = prob_against * expected_cohesion
        else:
            predicted_position = VotePosition.ABSTENTION
            confidence = prob_abstention * expected_cohesion

        return GroupPositionPrediction(
            group_code=group_code,
            group_name=self.GROUP_NAMES.get(group_code, group_code),
            predicted_position=predicted_position,
            confidence=confidence,
            expected_cohesion=expected_cohesion,
            prob_for=prob_for,
            prob_against=prob_against,
            prob_abstention=prob_abstention,
            factors=factors
        )

    def _are_allied_groups(self, group1: str, group2: str) -> bool:
        """Check if two groups are politically allied."""
        # Pro-EU mainstream alliance
        mainstream = {'EPP', 'S&D', 'Renew'}
        if group1 in mainstream and group2 in mainstream:
            return True

        # Green-Left alliance
        left_green = {'Greens/EFA', 'The Left', 'S&D'}
        if group1 in left_green and group2 in left_green:
            return True

        # Right alliance
        right = {'ECR', 'PfE', 'ESN'}
        if group1 in right and group2 in right:
            return True

        return False

    def _are_opposed_groups(self, group1: str, group2: str) -> bool:
        """Check if two groups are politically opposed."""
        left = {'Greens/EFA', 'The Left', 'S&D'}
        right = {'ECR', 'PfE', 'ESN'}

        if (group1 in left and group2 in right) or (group1 in right and group2 in left):
            return True

        return False

    async def predict_plenary_vote(
        self,
        procedure_ref: str,
        lead_committee: Optional[str] = None,
        rapporteur_group: Optional[str] = None,
        title: Optional[str] = None
    ) -> PlenaryVotePrediction:
        """
        Predict the outcome of a plenary vote.

        Aggregates group predictions weighted by seats.

        Args:
            procedure_ref: OEIL procedure reference
            lead_committee: Lead committee code
            rapporteur_group: Rapporteur's political group
            title: Procedure title

        Returns:
            PlenaryVotePrediction with overall outcome and group breakdown
        """
        group_predictions = []
        estimated_for = 0
        estimated_against = 0
        estimated_abstention = 0
        swing_groups = []

        # Predict for each group
        for group_code, seats in self.GROUP_SEATS.items():
            prediction = await self.predict_group_position(
                group_code=group_code,
                procedure_ref=procedure_ref,
                lead_committee=lead_committee,
                rapporteur_group=rapporteur_group
            )
            group_predictions.append(prediction)

            # Estimate vote distribution based on prediction
            if prediction.predicted_position == VotePosition.SPLIT:
                # Split vote - distribute by probabilities
                estimated_for += int(seats * prediction.prob_for)
                estimated_against += int(seats * prediction.prob_against)
                estimated_abstention += int(seats * prediction.prob_abstention)
                swing_groups.append(group_code)
            elif prediction.predicted_position == VotePosition.FOR:
                # Unified FOR - adjust for expected cohesion
                for_votes = int(seats * prediction.expected_cohesion)
                estimated_for += for_votes
                estimated_against += int((seats - for_votes) * 0.3)
                estimated_abstention += seats - for_votes - int((seats - for_votes) * 0.3)
            elif prediction.predicted_position == VotePosition.AGAINST:
                # Unified AGAINST
                against_votes = int(seats * prediction.expected_cohesion)
                estimated_against += against_votes
                estimated_for += int((seats - against_votes) * 0.3)
                estimated_abstention += seats - against_votes - int((seats - against_votes) * 0.3)
            else:
                # Abstention
                abstention_votes = int(seats * prediction.expected_cohesion)
                estimated_abstention += abstention_votes
                estimated_for += int((seats - abstention_votes) * 0.5)
                estimated_against += seats - abstention_votes - int((seats - abstention_votes) * 0.5)

            # Identify swing groups (low confidence predictions on large groups)
            if prediction.confidence < 0.6 and seats > 50:
                if group_code not in swing_groups:
                    swing_groups.append(group_code)

        # Calculate margin and outcome
        total_meps = sum(self.GROUP_SEATS.values())
        margin = estimated_for - estimated_against

        # Majority threshold (simple majority of votes cast, excluding abstentions)
        votes_cast = estimated_for + estimated_against
        majority_needed = votes_cast // 2 + 1

        if estimated_for >= majority_needed:
            predicted_outcome = 'PASS'
            confidence = min(0.9, (estimated_for - majority_needed) / 50 * 0.3 + 0.5)
        elif estimated_against >= majority_needed:
            predicted_outcome = 'FAIL'
            confidence = min(0.9, (estimated_against - majority_needed) / 50 * 0.3 + 0.5)
        else:
            predicted_outcome = 'UNCERTAIN'
            confidence = 0.3

        # Sort group predictions by seats
        group_predictions.sort(key=lambda x: self.GROUP_SEATS.get(x.group_code, 0), reverse=True)

        return PlenaryVotePrediction(
            procedure_ref=procedure_ref,
            title=title,
            predicted_outcome=predicted_outcome,
            confidence=confidence,
            predicted_margin=margin,
            estimated_for=estimated_for,
            estimated_against=estimated_against,
            estimated_abstention=estimated_abstention,
            total_meps=total_meps,
            group_predictions=group_predictions,
            swing_groups=swing_groups
        )


# Singleton instance
_predictor_instance: Optional[GroupVotePredictor] = None


def get_group_vote_predictor() -> GroupVotePredictor:
    """Get or create the group vote predictor instance."""
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = GroupVotePredictor()
    return _predictor_instance

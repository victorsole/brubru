"""
Cohesion Analyzer - Phase 3.1

Analyzes voting cohesion for EP political groups, delegations, and sections.

Cohesion measures how unified a group votes:
- 100% = All members vote the same way
- 50% = Split vote
- Lower = Fragmented

Usage:
    analyzer = CohesionAnalyzer()
    group_cohesion = await analyzer.calculate_group_cohesion("EPP")
    policy_splits = await analyzer.identify_policy_splits("EPP")
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from core.database import SessionLocal

logger = logging.getLogger(__name__)


class CohesionLevel(str, Enum):
    """Cohesion level classification."""
    VERY_HIGH = "very_high"  # >= 90%
    HIGH = "high"  # 75-90%
    MODERATE = "moderate"  # 60-75%
    LOW = "low"  # 50-60%
    SPLIT = "split"  # < 50%


@dataclass
class CohesionResult:
    """Result of cohesion calculation."""
    entity_type: str  # 'group', 'delegation', 'section'
    entity_code: str  # e.g., 'EPP', 'DE-EPP', 'Greens'
    cohesion_score: float  # 0.0-1.0
    cohesion_level: CohesionLevel
    votes_analyzed: int
    majority_position: str  # 'FOR', 'AGAINST', 'ABSTENTION'
    position_breakdown: Dict[str, int]  # {'FOR': 150, 'AGAINST': 10, ...}
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


@dataclass
class PolicySplit:
    """Information about a policy area where a group splits."""
    group_code: str
    policy_area: str  # EuroVoc domain or committee
    avg_cohesion: float
    num_split_votes: int  # Votes where cohesion < 75%
    total_votes: int
    example_votes: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class GroupCohesionProfile:
    """Full cohesion profile for a political group."""
    group_code: str
    group_name: str
    overall_cohesion: float
    cohesion_level: CohesionLevel
    total_votes_analyzed: int

    # By policy area
    policy_cohesion: Dict[str, float] = field(default_factory=dict)
    split_policies: List[str] = field(default_factory=list)

    # By delegation
    delegation_cohesion: Dict[str, float] = field(default_factory=dict)
    rebellious_delegations: List[str] = field(default_factory=list)

    # Temporal trends
    monthly_cohesion: List[Dict[str, Any]] = field(default_factory=list)


class CohesionAnalyzer:
    """
    Analyzes voting cohesion for EP entities.

    Uses EP voting data from Phase 1.1 (HowTheyVote import).
    """

    # Cohesion thresholds
    VERY_HIGH_THRESHOLD = 0.90
    HIGH_THRESHOLD = 0.75
    MODERATE_THRESHOLD = 0.60
    LOW_THRESHOLD = 0.50

    def __init__(self, db: Optional[Session] = None):
        self._db = db
        self._owns_db = db is None
        self._cohesion_cache: Dict[str, CohesionResult] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = timedelta(hours=12)

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

    def _get_cohesion_level(self, score: float) -> CohesionLevel:
        """Convert cohesion score to level."""
        if score >= self.VERY_HIGH_THRESHOLD:
            return CohesionLevel.VERY_HIGH
        elif score >= self.HIGH_THRESHOLD:
            return CohesionLevel.HIGH
        elif score >= self.MODERATE_THRESHOLD:
            return CohesionLevel.MODERATE
        elif score >= self.LOW_THRESHOLD:
            return CohesionLevel.LOW
        return CohesionLevel.SPLIT

    def _calculate_agreement_index(
        self,
        votes: Dict[str, int]
    ) -> Tuple[float, str]:
        """
        Calculate Agreement Index (AI) from vote counts.

        AI = max(For, Against, Abstain) / (For + Against + Abstain)

        Returns (score, majority_position)
        """
        for_count = votes.get('FOR', 0)
        against_count = votes.get('AGAINST', 0)
        abstain_count = votes.get('ABSTENTION', 0)

        total = for_count + against_count + abstain_count
        if total == 0:
            return 0.0, 'UNKNOWN'

        max_count = max(for_count, against_count, abstain_count)

        if max_count == for_count:
            majority = 'FOR'
        elif max_count == against_count:
            majority = 'AGAINST'
        else:
            majority = 'ABSTENTION'

        return max_count / total, majority

    async def calculate_group_cohesion(
        self,
        group_code: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Optional[CohesionResult]:
        """
        Calculate cohesion for a political group.

        Args:
            group_code: EP group code (e.g., 'EPP', 'S&D', 'Renew')
            start_date: Start of analysis period
            end_date: End of analysis period

        Returns:
            CohesionResult with overall cohesion score
        """
        try:
            from models.ep_voting import EPMemberVote, EPVote, EPMember, EPGroupMembership

            # Default to last 12 months
            if end_date is None:
                end_date = datetime.now(timezone.utc)
            if start_date is None:
                start_date = end_date - timedelta(days=365)

            # Get all votes for members of this group in the period
            # This query aggregates votes per vote_id for the group
            vote_aggregates = self.db.query(
                EPMemberVote.vote_id,
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
                EPVote.timestamp >= start_date,
                EPVote.timestamp <= end_date
            ).group_by(
                EPMemberVote.vote_id,
                EPMemberVote.position
            ).all()

            if not vote_aggregates:
                return None

            # Aggregate by vote_id
            votes_by_id: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
            for vote_id, position, count in vote_aggregates:
                pos_str = position.value if hasattr(position, 'value') else str(position)
                votes_by_id[str(vote_id)][pos_str] = count

            # Calculate cohesion for each vote, then average
            cohesion_scores = []
            position_totals: Dict[str, int] = defaultdict(int)

            for vote_id, positions in votes_by_id.items():
                score, _ = self._calculate_agreement_index(positions)
                cohesion_scores.append(score)

                for pos, count in positions.items():
                    position_totals[pos] += count

            overall_cohesion = sum(cohesion_scores) / len(cohesion_scores)
            _, majority_pos = self._calculate_agreement_index(position_totals)

            return CohesionResult(
                entity_type='group',
                entity_code=group_code,
                cohesion_score=overall_cohesion,
                cohesion_level=self._get_cohesion_level(overall_cohesion),
                votes_analyzed=len(votes_by_id),
                majority_position=majority_pos,
                position_breakdown=dict(position_totals),
                period_start=start_date,
                period_end=end_date
            )

        except ImportError:
            logger.warning("EP voting models not available")
            return None
        except Exception as e:
            logger.error(f"Error calculating group cohesion: {e}")
            return None

    async def calculate_delegation_cohesion(
        self,
        group_code: str,
        country_code: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Optional[CohesionResult]:
        """
        Calculate cohesion for a national delegation within a group.

        Args:
            group_code: EP group code
            country_code: ISO country code (e.g., 'DE', 'FR')
        """
        try:
            from models.ep_voting import EPMemberVote, EPVote, EPMember, EPGroupMembership

            if end_date is None:
                end_date = datetime.now(timezone.utc)
            if start_date is None:
                start_date = end_date - timedelta(days=365)

            # Get votes for members of this delegation
            vote_aggregates = self.db.query(
                EPMemberVote.vote_id,
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
                EPMember.country_code == country_code,
                EPVote.timestamp >= start_date,
                EPVote.timestamp <= end_date
            ).group_by(
                EPMemberVote.vote_id,
                EPMemberVote.position
            ).all()

            if not vote_aggregates:
                return None

            # Aggregate by vote_id
            votes_by_id: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
            for vote_id, position, count in vote_aggregates:
                pos_str = position.value if hasattr(position, 'value') else str(position)
                votes_by_id[str(vote_id)][pos_str] = count

            cohesion_scores = []
            position_totals: Dict[str, int] = defaultdict(int)

            for vote_id, positions in votes_by_id.items():
                score, _ = self._calculate_agreement_index(positions)
                cohesion_scores.append(score)
                for pos, count in positions.items():
                    position_totals[pos] += count

            overall_cohesion = sum(cohesion_scores) / len(cohesion_scores)
            _, majority_pos = self._calculate_agreement_index(position_totals)

            return CohesionResult(
                entity_type='delegation',
                entity_code=f"{country_code}-{group_code}",
                cohesion_score=overall_cohesion,
                cohesion_level=self._get_cohesion_level(overall_cohesion),
                votes_analyzed=len(votes_by_id),
                majority_position=majority_pos,
                position_breakdown=dict(position_totals),
                period_start=start_date,
                period_end=end_date
            )

        except ImportError:
            logger.warning("EP voting models not available")
            return None
        except Exception as e:
            logger.error(f"Error calculating delegation cohesion: {e}")
            return None

    async def identify_policy_splits(
        self,
        group_code: str,
        min_votes: int = 5,
        cohesion_threshold: float = 0.75
    ) -> List[PolicySplit]:
        """
        Identify policy areas where a group tends to split.

        Uses committee of the vote as proxy for policy area.
        """
        try:
            from models.ep_voting import EPMemberVote, EPVote, EPMember, EPGroupMembership

            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=365)

            # Get votes with committee info
            vote_data = self.db.query(
                EPVote.id,
                EPVote.reference,
                EPMemberVote.position,
                func.count(EPMemberVote.id).label('count')
            ).join(
                EPMemberVote,
                EPMemberVote.vote_id == EPVote.id
            ).join(
                EPMember,
                EPMemberVote.member_id == EPMember.id
            ).join(
                EPGroupMembership,
                and_(
                    EPGroupMembership.member_id == EPMember.id,
                    EPGroupMembership.group_code == group_code
                )
            ).filter(
                EPVote.timestamp >= start_date
            ).group_by(
                EPVote.id,
                EPVote.reference,
                EPMemberVote.position
            ).all()

            if not vote_data:
                return []

            # Group by vote reference (use procedure reference as policy proxy)
            votes_by_ref: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(
                lambda: defaultdict(lambda: defaultdict(int))
            )

            for vote_id, ref, position, count in vote_data:
                # Extract policy area from reference (simplified)
                policy = self._extract_policy_area(ref)
                pos_str = position.value if hasattr(position, 'value') else str(position)
                votes_by_ref[policy][str(vote_id)][pos_str] = count

            # Calculate cohesion per policy area
            policy_splits = []

            for policy, votes in votes_by_ref.items():
                if len(votes) < min_votes:
                    continue

                cohesion_scores = []
                split_count = 0
                examples = []

                for vote_id, positions in votes.items():
                    score, _ = self._calculate_agreement_index(positions)
                    cohesion_scores.append(score)

                    if score < cohesion_threshold:
                        split_count += 1
                        if len(examples) < 3:
                            examples.append({
                                'vote_id': vote_id,
                                'cohesion': score,
                                'positions': positions
                            })

                avg_cohesion = sum(cohesion_scores) / len(cohesion_scores)

                if split_count >= 2 or avg_cohesion < cohesion_threshold:
                    policy_splits.append(PolicySplit(
                        group_code=group_code,
                        policy_area=policy,
                        avg_cohesion=avg_cohesion,
                        num_split_votes=split_count,
                        total_votes=len(votes),
                        example_votes=examples
                    ))

            # Sort by average cohesion (lowest first = most splits)
            policy_splits.sort(key=lambda x: x.avg_cohesion)

            return policy_splits

        except ImportError:
            logger.warning("EP voting models not available")
            return []
        except Exception as e:
            logger.error(f"Error identifying policy splits: {e}")
            return []

    def _extract_policy_area(self, reference: Optional[str]) -> str:
        """
        Extract policy area from vote reference.

        Uses procedure type and committee as proxy.
        """
        if not reference:
            return "UNKNOWN"

        # Try to extract committee from reference
        # Common patterns: "A9-0123/2024", "2024/0001(COD)"
        import re

        # Check for committee prefix (e.g., LIBE, ECON)
        committee_match = re.search(r'([A-Z]{4})', reference)
        if committee_match:
            return committee_match.group(1)

        # Check for procedure type
        proc_match = re.search(r'\(([A-Z]{3})\)', reference)
        if proc_match:
            return proc_match.group(1)

        return "GENERAL"

    async def get_group_profile(
        self,
        group_code: str
    ) -> Optional[GroupCohesionProfile]:
        """
        Get full cohesion profile for a political group.

        Includes overall cohesion, policy breakdowns, and delegation analysis.
        """
        # Get overall cohesion
        overall = await self.calculate_group_cohesion(group_code)
        if not overall:
            return None

        # Get policy splits
        splits = await self.identify_policy_splits(group_code)
        split_policies = [s.policy_area for s in splits]

        # Policy cohesion map
        policy_cohesion = {s.policy_area: s.avg_cohesion for s in splits}

        # Get group name (simplified)
        group_names = {
            'EPP': 'European People\'s Party',
            'S&D': 'Socialists & Democrats',
            'Renew': 'Renew Europe',
            'Greens/EFA': 'Greens/European Free Alliance',
            'ECR': 'European Conservatives and Reformists',
            'ID': 'Identity and Democracy',
            'The Left': 'The Left in the EP',
            'NI': 'Non-Inscrits'
        }

        return GroupCohesionProfile(
            group_code=group_code,
            group_name=group_names.get(group_code, group_code),
            overall_cohesion=overall.cohesion_score,
            cohesion_level=overall.cohesion_level,
            total_votes_analyzed=overall.votes_analyzed,
            policy_cohesion=policy_cohesion,
            split_policies=split_policies
        )


# Singleton instance
_analyzer_instance: Optional[CohesionAnalyzer] = None


def get_cohesion_analyzer() -> CohesionAnalyzer:
    """Get or create the cohesion analyzer instance."""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = CohesionAnalyzer()
    return _analyzer_instance

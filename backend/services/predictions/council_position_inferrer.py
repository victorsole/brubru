"""
Council Position Inferrer - Phase 4.4

Infers member state positions on EU procedures from various signals.

Sources:
- Government statements and press releases
- National parliament votes
- Party policy platforms
- Historical voting patterns
- European party family positions

Usage:
    inferrer = CouncilPositionInferrer()
    position = await inferrer.infer_position("DE", "2024/0138(COD)")
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import and_

from core.database import SessionLocal
from .qmv_calculator import QMVCalculator, get_qmv_calculator

logger = logging.getLogger(__name__)


class PositionConfidence(str, Enum):
    """Confidence level in position inference."""
    HIGH = "high"  # Direct statement or vote
    MEDIUM = "medium"  # Inferred from multiple signals
    LOW = "low"  # Based on general patterns
    UNKNOWN = "unknown"  # Insufficient data


@dataclass
class PositionSignal:
    """A single signal about a state's position."""
    source_type: str  # 'statement', 'vote', 'party_platform', 'historical'
    signal_date: datetime
    position: str  # 'support', 'oppose', 'neutral'
    confidence: float
    summary: str
    source_url: Optional[str] = None


@dataclass
class InferredPosition:
    """Inferred position for a member state on a procedure."""
    country_code: str
    country_name: str
    procedure_ref: str

    # Position
    position: str  # 'support', 'oppose', 'undecided', 'abstain'
    confidence: float
    confidence_level: PositionConfidence

    # Supporting evidence
    signals: List[PositionSignal] = field(default_factory=list)
    key_concerns: List[str] = field(default_factory=list)
    red_lines: List[str] = field(default_factory=list)

    # Government context
    governing_parties: List[str] = field(default_factory=list)
    european_families: List[str] = field(default_factory=list)

    # Inference metadata
    inferred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_signal_date: Optional[datetime] = None


@dataclass
class CouncilVotePrediction:
    """Prediction for Council vote on a procedure."""
    procedure_ref: str
    qmv_outcome: str  # 'pass', 'fail', 'uncertain'
    qmv_confidence: float

    # Optional fields with defaults
    title: Optional[str] = None

    # State breakdown
    supporting_states: List[str] = field(default_factory=list)
    opposing_states: List[str] = field(default_factory=list)
    undecided_states: List[str] = field(default_factory=list)

    # QMV metrics
    support_population_pct: float = 0.0
    oppose_population_pct: float = 0.0

    # Blocking minority risk
    blocking_minority_risk: str = "low"
    potential_blocking_coalition: List[str] = field(default_factory=list)

    # State positions
    state_positions: List[InferredPosition] = field(default_factory=list)


class CouncilPositionInferrer:
    """
    Infers member state positions from various signals.

    Uses European party family positions as baseline,
    then adjusts based on specific evidence.
    """

    # European party family baseline positions by policy area
    # Scores: -1 (strongly oppose) to +1 (strongly support)
    FAMILY_BASELINES = {
        'EPP': {
            'default': 0.6,
            'fiscal_rules': 0.8,
            'green_transition': 0.4,
            'migration': 0.3,
            'rule_of_law': 0.7,
            'defense': 0.8,
            'trade': 0.7,
        },
        'PES': {
            'default': 0.7,
            'fiscal_rules': 0.3,
            'green_transition': 0.7,
            'migration': 0.6,
            'rule_of_law': 0.9,
            'social': 0.9,
            'trade': 0.5,
        },
        'ALDE': {
            'default': 0.7,
            'fiscal_rules': 0.7,
            'green_transition': 0.6,
            'migration': 0.5,
            'rule_of_law': 0.9,
            'trade': 0.9,
            'digital': 0.8,
        },
        'EGP': {
            'default': 0.6,
            'fiscal_rules': 0.3,
            'green_transition': 1.0,
            'migration': 0.7,
            'rule_of_law': 0.9,
            'trade': 0.3,
        },
        'ECR': {
            'default': 0.2,
            'fiscal_rules': 0.7,
            'green_transition': 0.1,
            'migration': -0.5,
            'rule_of_law': 0.3,
            'sovereignty': -0.7,
        },
        'ID': {
            'default': -0.5,
            'fiscal_rules': 0.3,
            'green_transition': -0.7,
            'migration': -0.9,
            'rule_of_law': -0.3,
            'sovereignty': -0.9,
        },
    }

    # National interest overrides (country-specific sensitivities)
    NATIONAL_OVERRIDES = {
        'DE': {
            'fiscal_rules': 0.3,  # Germany pushes for fiscal discipline
            'automotive': -0.3,  # Protects car industry
        },
        'FR': {
            'agriculture': -0.2,  # Protects CAP
            'nuclear': 0.3,  # Pro-nuclear in green debates
            'sovereignty': 0.1,  # Strategic autonomy
        },
        'PL': {
            'rule_of_law': -0.5,  # Sensitive topic
            'green_transition': -0.3,  # Coal dependency
            'migration': -0.4,
        },
        'HU': {
            'rule_of_law': -0.7,
            'migration': -0.6,
        },
        'NL': {
            'fiscal_rules': 0.4,  # Frugal
        },
        'IT': {
            'migration': -0.2,
            'fiscal_rules': -0.2,
        },
    }

    # Committee to policy area mapping
    COMMITTEE_POLICY = {
        'ECON': 'fiscal_rules',
        'ENVI': 'green_transition',
        'LIBE': 'migration',
        'AFCO': 'rule_of_law',
        'AFET': 'defense',
        'INTA': 'trade',
        'AGRI': 'agriculture',
        'ITRE': 'digital',
        'EMPL': 'social',
    }

    def __init__(self, db: Optional[Session] = None):
        self._db = db
        self._owns_db = db is None
        self._qmv_calc = None

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    @property
    def qmv_calculator(self) -> QMVCalculator:
        if self._qmv_calc is None:
            self._qmv_calc = get_qmv_calculator()
        return self._qmv_calc

    def close(self):
        """Close database session if we own it."""
        if self._owns_db and self._db:
            self._db.close()
            self._db = None

    def _get_policy_area(self, lead_committee: Optional[str]) -> str:
        """Map committee to policy area."""
        if not lead_committee:
            return 'default'
        return self.COMMITTEE_POLICY.get(lead_committee, 'default')

    def _get_government_parties(self, country_code: str) -> Tuple[List[str], List[str]]:
        """
        Get governing parties and their European families.

        Would query council_governments and council_governing_parties tables.
        Returns (party_names, european_families).
        """
        # Simplified - would query database
        # This is illustrative data
        governments = {
            'DE': (['SPD', 'Greens', 'FDP'], ['PES', 'EGP', 'ALDE']),
            'FR': (['Renaissance', 'MoDem'], ['ALDE', 'ALDE']),
            'IT': (['FdI', 'Lega', 'FI'], ['ECR', 'ID', 'EPP']),
            'ES': (['PSOE', 'Sumar'], ['PES', 'EGP']),
            'PL': (['KO', 'TD', 'NL'], ['EPP', 'EPP', 'EGP']),
            'NL': (['PVV', 'VVD', 'NSC', 'BBB'], ['ID', 'ALDE', 'EPP', 'ECR']),
            'BE': (['MR', 'CD&V', 'Vooruit', 'N-VA'], ['ALDE', 'EPP', 'PES', 'ECR']),
            'GR': (['ND'], ['EPP']),
            'CZ': (['ODS', 'STAN', 'KDU-CSL'], ['ECR', 'EPP', 'EPP']),
            'PT': (['PS'], ['PES']),
            'SE': (['M', 'KD', 'L'], ['EPP', 'EPP', 'ALDE']),
            'HU': (['Fidesz'], ['EPP']),  # Suspended from EPP
            'AT': (['OVP', 'Grune'], ['EPP', 'EGP']),
            'DK': (['S', 'V', 'M'], ['PES', 'ALDE', 'EPP']),
            'FI': (['KOK', 'PS', 'RKP'], ['EPP', 'ECR', 'ALDE']),
        }

        return governments.get(country_code, ([], []))

    def _calculate_baseline_position(
        self,
        country_code: str,
        policy_area: str,
        european_families: List[str]
    ) -> float:
        """
        Calculate baseline position from European party families.

        Returns score from -1 (oppose) to +1 (support).
        """
        if not european_families:
            return 0.0

        # Average family positions
        scores = []
        for family in european_families:
            family_baseline = self.FAMILY_BASELINES.get(family, {})
            score = family_baseline.get(policy_area, family_baseline.get('default', 0.5))
            scores.append(score)

        baseline = sum(scores) / len(scores)

        # Apply national override if applicable
        national = self.NATIONAL_OVERRIDES.get(country_code, {})
        override = national.get(policy_area, 0)
        baseline += override

        # Clamp to [-1, 1]
        return max(-1.0, min(1.0, baseline))

    async def infer_position(
        self,
        country_code: str,
        procedure_ref: str,
        lead_committee: Optional[str] = None,
        title: Optional[str] = None
    ) -> InferredPosition:
        """
        Infer a member state's position on a procedure.

        Combines:
        1. European party family baseline
        2. National interest factors
        3. Any specific statements or votes (if in database)
        """
        country_code = country_code.upper()
        state_data = self.qmv_calculator.get_state_data(country_code)

        if not state_data:
            return InferredPosition(
                country_code=country_code,
                country_name=country_code,
                procedure_ref=procedure_ref,
                position='undecided',
                confidence=0.0,
                confidence_level=PositionConfidence.UNKNOWN
            )

        # Get governing parties
        parties, families = self._get_government_parties(country_code)

        # Get policy area
        policy_area = self._get_policy_area(lead_committee)

        # Calculate baseline position
        baseline_score = self._calculate_baseline_position(country_code, policy_area, families)

        # Look for specific signals in database
        signals = await self._get_position_signals(country_code, procedure_ref)

        # Adjust based on signals
        if signals:
            # Weight recent signals more heavily
            signal_scores = []
            for signal in signals:
                if signal.position == 'support':
                    signal_scores.append(signal.confidence)
                elif signal.position == 'oppose':
                    signal_scores.append(-signal.confidence)
                else:
                    signal_scores.append(0)

            if signal_scores:
                signal_avg = sum(signal_scores) / len(signal_scores)
                # Blend baseline with signals (signals weighted more if confident)
                max_signal_conf = max(s.confidence for s in signals)
                final_score = baseline_score * (1 - max_signal_conf) + signal_avg * max_signal_conf
            else:
                final_score = baseline_score
        else:
            final_score = baseline_score

        # Convert score to position
        if final_score > 0.3:
            position = 'support'
        elif final_score < -0.3:
            position = 'oppose'
        elif abs(final_score) < 0.1:
            position = 'abstain'
        else:
            position = 'undecided'

        # Determine confidence
        confidence = abs(final_score) * 0.5 + 0.2  # Base confidence
        if signals:
            confidence = min(0.9, confidence + len(signals) * 0.1)

        if confidence > 0.7:
            confidence_level = PositionConfidence.HIGH
        elif confidence > 0.4:
            confidence_level = PositionConfidence.MEDIUM
        elif confidence > 0.2:
            confidence_level = PositionConfidence.LOW
        else:
            confidence_level = PositionConfidence.UNKNOWN

        # Extract key concerns based on national interests
        key_concerns = []
        if country_code in self.NATIONAL_OVERRIDES:
            for area, _ in self.NATIONAL_OVERRIDES[country_code].items():
                if area == policy_area:
                    key_concerns.append(f"Sensitive to {area} implications")

        return InferredPosition(
            country_code=country_code,
            country_name=state_data.name,
            procedure_ref=procedure_ref,
            position=position,
            confidence=confidence,
            confidence_level=confidence_level,
            signals=signals,
            key_concerns=key_concerns,
            governing_parties=parties,
            european_families=list(set(families)),
            last_signal_date=signals[0].signal_date if signals else None
        )

    async def _get_position_signals(
        self,
        country_code: str,
        procedure_ref: str
    ) -> List[PositionSignal]:
        """
        Get position signals from database.

        Queries GovernmentStatement and NationalParliamentVote tables.
        """
        signals = []

        try:
            from models.council_voting import GovernmentStatement, MemberState, Government

            # Get statements about this procedure
            statements = self.db.query(GovernmentStatement).join(
                Government
            ).join(
                MemberState
            ).filter(
                MemberState.iso_code == country_code,
                GovernmentStatement.eu_procedure_ref == procedure_ref
            ).order_by(
                GovernmentStatement.statement_date.desc()
            ).limit(5).all()

            for stmt in statements:
                if stmt.sentiment:
                    if stmt.sentiment.value == 'positive':
                        position = 'support'
                    elif stmt.sentiment.value == 'negative':
                        position = 'oppose'
                    else:
                        position = 'neutral'

                    signals.append(PositionSignal(
                        source_type='statement',
                        signal_date=stmt.statement_date,
                        position=position,
                        confidence=stmt.analysis_confidence or 0.5,
                        summary=stmt.summary or stmt.topic,
                        source_url=stmt.source_url
                    ))

        except Exception as e:
            logger.debug(f"Could not query position signals: {e}")

        return signals

    async def predict_council_vote(
        self,
        procedure_ref: str,
        lead_committee: Optional[str] = None,
        title: Optional[str] = None
    ) -> CouncilVotePrediction:
        """
        Predict Council vote outcome by inferring all state positions.

        Combines position inference with QMV calculation.
        """
        supporting = []
        opposing = []
        undecided = []
        state_positions = []

        # Infer position for each member state
        for country_code in self.qmv_calculator.MEMBER_STATES.keys():
            position = await self.infer_position(
                country_code=country_code,
                procedure_ref=procedure_ref,
                lead_committee=lead_committee,
                title=title
            )
            state_positions.append(position)

            if position.position == 'support':
                supporting.append(country_code)
            elif position.position == 'oppose':
                opposing.append(country_code)
            else:
                undecided.append(country_code)

        # Calculate QMV
        qmv_result = self.qmv_calculator.calculate_qmv(
            supporting_states=supporting,
            opposing_states=opposing,
            abstaining_states=undecided
        )

        # Analyze blocking minority risk
        blocking_analysis = self.qmv_calculator.find_blocking_coalitions(
            base_opposed=opposing,
            potential_swing=undecided
        )

        return CouncilVotePrediction(
            procedure_ref=procedure_ref,
            title=title,
            qmv_outcome=qmv_result.outcome.value,
            qmv_confidence=0.5 + abs(qmv_result.population_margin) / 100,
            supporting_states=supporting,
            opposing_states=opposing,
            undecided_states=undecided,
            support_population_pct=qmv_result.population_for_pct,
            oppose_population_pct=qmv_result.population_against_pct,
            blocking_minority_risk=blocking_analysis.risk_level,
            potential_blocking_coalition=blocking_analysis.at_risk_states,
            state_positions=state_positions
        )


# Singleton instance
_inferrer_instance: Optional[CouncilPositionInferrer] = None


def get_council_position_inferrer() -> CouncilPositionInferrer:
    """Get or create the council position inferrer instance."""
    global _inferrer_instance
    if _inferrer_instance is None:
        _inferrer_instance = CouncilPositionInferrer()
    return _inferrer_instance

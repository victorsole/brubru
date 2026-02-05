"""
QMV Calculator - Phase 4.2

Qualified Majority Voting calculator for Council of the EU.

QMV Rules (Post-Lisbon):
- 55% of member states (15 of 27)
- 65% of EU population
- Blocking minority: 4+ states representing >35% population

Usage:
    calc = QMVCalculator()
    result = calc.calculate_qmv(supporting_states=['DE', 'FR', 'IT'])
    blocking = calc.find_blocking_coalitions(opposed_states=['PL', 'HU'])
"""

import logging
from typing import Optional, Dict, Any, List, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class VoteOutcome(str, Enum):
    """Possible QMV outcomes."""
    PASS = "pass"
    FAIL = "fail"
    UNCERTAIN = "uncertain"


@dataclass
class MemberStateData:
    """Data for a single member state."""
    code: str
    name: str
    population: int  # In thousands
    population_percentage: float


@dataclass
class QMVResult:
    """Result of QMV calculation."""
    outcome: VoteOutcome
    states_for: int
    states_against: int
    states_abstain: int
    population_for_pct: float
    population_against_pct: float

    # Thresholds
    states_threshold: int = 15  # 55% of 27
    population_threshold: float = 65.0

    # Margins
    states_margin: int = 0  # Positive = above threshold
    population_margin: float = 0.0

    # Details
    supporting_states: List[str] = field(default_factory=list)
    opposing_states: List[str] = field(default_factory=list)
    abstaining_states: List[str] = field(default_factory=list)


@dataclass
class BlockingMinority:
    """A potential blocking minority coalition."""
    states: List[str]
    population_percentage: float
    is_valid: bool  # True if meets blocking criteria
    missing_population_pct: float = 0.0  # How much more needed
    missing_states: int = 0  # How many more states needed


@dataclass
class BlockingAnalysis:
    """Analysis of blocking minority risks."""
    procedure_ref: Optional[str] = None
    has_blocking_minority: bool = False
    blocking_coalitions: List[BlockingMinority] = field(default_factory=list)
    at_risk_states: List[str] = field(default_factory=list)  # States that could tip balance
    risk_level: str = "low"  # low, moderate, high
    analysis_notes: List[str] = field(default_factory=list)


class QMVCalculator:
    """
    Calculates Qualified Majority Voting outcomes.

    Uses official EU population data (2024 figures).
    """

    # EU-27 Population Data (2024, in thousands)
    # Source: Eurostat
    MEMBER_STATES = {
        'DE': MemberStateData('DE', 'Germany', 84_359, 18.87),
        'FR': MemberStateData('FR', 'France', 68_070, 15.23),
        'IT': MemberStateData('IT', 'Italy', 58_851, 13.17),
        'ES': MemberStateData('ES', 'Spain', 48_373, 10.82),
        'PL': MemberStateData('PL', 'Poland', 36_754, 8.22),
        'RO': MemberStateData('RO', 'Romania', 19_053, 4.26),
        'NL': MemberStateData('NL', 'Netherlands', 17_942, 4.01),
        'BE': MemberStateData('BE', 'Belgium', 11_787, 2.64),
        'GR': MemberStateData('GR', 'Greece', 10_394, 2.33),
        'CZ': MemberStateData('CZ', 'Czechia', 10_828, 2.42),
        'PT': MemberStateData('PT', 'Portugal', 10_467, 2.34),
        'SE': MemberStateData('SE', 'Sweden', 10_551, 2.36),
        'HU': MemberStateData('HU', 'Hungary', 9_600, 2.15),
        'AT': MemberStateData('AT', 'Austria', 9_132, 2.04),
        'BG': MemberStateData('BG', 'Bulgaria', 6_447, 1.44),
        'DK': MemberStateData('DK', 'Denmark', 5_933, 1.33),
        'FI': MemberStateData('FI', 'Finland', 5_564, 1.24),
        'SK': MemberStateData('SK', 'Slovakia', 5_426, 1.21),
        'IE': MemberStateData('IE', 'Ireland', 5_281, 1.18),
        'HR': MemberStateData('HR', 'Croatia', 3_850, 0.86),
        'LT': MemberStateData('LT', 'Lithuania', 2_860, 0.64),
        'SI': MemberStateData('SI', 'Slovenia', 2_117, 0.47),
        'LV': MemberStateData('LV', 'Latvia', 1_876, 0.42),
        'EE': MemberStateData('EE', 'Estonia', 1_366, 0.31),
        'CY': MemberStateData('CY', 'Cyprus', 920, 0.21),
        'LU': MemberStateData('LU', 'Luxembourg', 672, 0.15),
        'MT': MemberStateData('MT', 'Malta', 542, 0.12),
    }

    # QMV Thresholds
    TOTAL_STATES = 27
    STATES_THRESHOLD_PCT = 55.0
    POPULATION_THRESHOLD_PCT = 65.0
    BLOCKING_MIN_STATES = 4
    BLOCKING_POPULATION_PCT = 35.0

    def __init__(self):
        self.states_threshold = int(self.TOTAL_STATES * self.STATES_THRESHOLD_PCT / 100) + 1
        self.total_population = sum(s.population for s in self.MEMBER_STATES.values())

    def get_state_data(self, code: str) -> Optional[MemberStateData]:
        """Get data for a member state."""
        return self.MEMBER_STATES.get(code.upper())

    def calculate_population_percentage(self, states: List[str]) -> float:
        """Calculate total population percentage for a group of states."""
        total = 0
        for code in states:
            state = self.get_state_data(code)
            if state:
                total += state.population
        return (total / self.total_population) * 100

    def calculate_qmv(
        self,
        supporting_states: List[str],
        opposing_states: Optional[List[str]] = None,
        abstaining_states: Optional[List[str]] = None
    ) -> QMVResult:
        """
        Calculate QMV outcome given state positions.

        Args:
            supporting_states: States voting FOR
            opposing_states: States voting AGAINST
            abstaining_states: States abstaining (count as not supporting)

        Returns:
            QMVResult with outcome and margins
        """
        opposing_states = opposing_states or []
        abstaining_states = abstaining_states or []

        # Validate state codes
        supporting = [s.upper() for s in supporting_states if s.upper() in self.MEMBER_STATES]
        opposing = [s.upper() for s in opposing_states if s.upper() in self.MEMBER_STATES]
        abstaining = [s.upper() for s in abstaining_states if s.upper() in self.MEMBER_STATES]

        # Calculate counts
        states_for = len(supporting)
        states_against = len(opposing)
        states_abstain = len(abstaining)

        # Calculate population percentages
        pop_for = self.calculate_population_percentage(supporting)
        pop_against = self.calculate_population_percentage(opposing)

        # Check thresholds
        states_ok = states_for >= self.states_threshold
        population_ok = pop_for >= self.POPULATION_THRESHOLD_PCT

        # Determine outcome
        if states_ok and population_ok:
            outcome = VoteOutcome.PASS
        elif states_for + states_against + states_abstain < self.TOTAL_STATES:
            # Not all states accounted for
            outcome = VoteOutcome.UNCERTAIN
        else:
            outcome = VoteOutcome.FAIL

        return QMVResult(
            outcome=outcome,
            states_for=states_for,
            states_against=states_against,
            states_abstain=states_abstain,
            population_for_pct=round(pop_for, 2),
            population_against_pct=round(pop_against, 2),
            states_threshold=self.states_threshold,
            population_threshold=self.POPULATION_THRESHOLD_PCT,
            states_margin=states_for - self.states_threshold,
            population_margin=round(pop_for - self.POPULATION_THRESHOLD_PCT, 2),
            supporting_states=supporting,
            opposing_states=opposing,
            abstaining_states=abstaining
        )

    def check_blocking_minority(
        self,
        states: List[str]
    ) -> BlockingMinority:
        """
        Check if a coalition forms a valid blocking minority.

        Blocking minority requires:
        - At least 4 member states
        - Representing >35% of EU population
        """
        valid_states = [s.upper() for s in states if s.upper() in self.MEMBER_STATES]
        pop_pct = self.calculate_population_percentage(valid_states)

        has_min_states = len(valid_states) >= self.BLOCKING_MIN_STATES
        has_min_population = pop_pct > self.BLOCKING_POPULATION_PCT

        is_valid = has_min_states and has_min_population

        missing_pop = max(0, self.BLOCKING_POPULATION_PCT - pop_pct + 0.01)
        missing_states = max(0, self.BLOCKING_MIN_STATES - len(valid_states))

        return BlockingMinority(
            states=valid_states,
            population_percentage=round(pop_pct, 2),
            is_valid=is_valid,
            missing_population_pct=round(missing_pop, 2),
            missing_states=missing_states
        )

    def find_blocking_coalitions(
        self,
        base_opposed: List[str],
        potential_swing: Optional[List[str]] = None
    ) -> BlockingAnalysis:
        """
        Find potential blocking minority coalitions.

        Args:
            base_opposed: States known to oppose
            potential_swing: States that might join opposition

        Returns:
            BlockingAnalysis with possible coalitions
        """
        base_opposed = [s.upper() for s in base_opposed if s.upper() in self.MEMBER_STATES]
        potential_swing = potential_swing or []
        potential_swing = [s.upper() for s in potential_swing if s.upper() in self.MEMBER_STATES]

        # Check if base opposition already forms blocking minority
        base_blocking = self.check_blocking_minority(base_opposed)

        coalitions = []
        at_risk_states = []
        notes = []

        if base_blocking.is_valid:
            coalitions.append(base_blocking)
            notes.append(f"Base opposition already forms blocking minority ({base_blocking.population_percentage:.1f}%)")
        else:
            notes.append(f"Base opposition: {len(base_opposed)} states, {base_blocking.population_percentage:.1f}% population")

            if base_blocking.missing_states > 0:
                notes.append(f"Need {base_blocking.missing_states} more states for blocking minority")
            if base_blocking.missing_population_pct > 0:
                notes.append(f"Need {base_blocking.missing_population_pct:.1f}% more population")

        # Check which swing states could complete a blocking minority
        for swing in potential_swing:
            if swing in base_opposed:
                continue

            test_coalition = base_opposed + [swing]
            result = self.check_blocking_minority(test_coalition)

            if result.is_valid and not base_blocking.is_valid:
                at_risk_states.append(swing)
                coalitions.append(result)
                state_data = self.get_state_data(swing)
                if state_data:
                    notes.append(f"{state_data.name} joining would enable blocking minority")

        # Determine risk level
        if base_blocking.is_valid:
            risk_level = "high"
        elif len(at_risk_states) > 2:
            risk_level = "high"
        elif len(at_risk_states) > 0 or base_blocking.missing_states <= 1:
            risk_level = "moderate"
        else:
            risk_level = "low"

        return BlockingAnalysis(
            has_blocking_minority=base_blocking.is_valid,
            blocking_coalitions=coalitions,
            at_risk_states=at_risk_states,
            risk_level=risk_level,
            analysis_notes=notes
        )

    def get_largest_states(self, n: int = 5) -> List[str]:
        """Get the N largest states by population."""
        sorted_states = sorted(
            self.MEMBER_STATES.values(),
            key=lambda s: s.population,
            reverse=True
        )
        return [s.code for s in sorted_states[:n]]

    def get_minimum_blocking_coalitions(self) -> List[List[str]]:
        """
        Get all minimum-size blocking coalitions (4 states with >35% population).

        Returns combinations of 4 states that form valid blocking minorities.
        """
        from itertools import combinations

        valid_coalitions = []

        # Only check combinations that include at least one large state
        # (optimization - small states alone can't reach 35%)
        large_states = self.get_largest_states(8)  # States that could anchor a coalition

        for anchor in large_states:
            anchor_data = self.get_state_data(anchor)
            if not anchor_data:
                continue

            # Need 3 more states
            other_states = [s for s in self.MEMBER_STATES.keys() if s != anchor]

            for combo in combinations(other_states, 3):
                coalition = [anchor] + list(combo)
                blocking = self.check_blocking_minority(coalition)

                if blocking.is_valid:
                    # Check if this is minimal (removing any state breaks it)
                    is_minimal = True
                    for state in coalition:
                        subset = [s for s in coalition if s != state]
                        if self.check_blocking_minority(subset).is_valid:
                            is_minimal = False
                            break

                    if is_minimal:
                        sorted_coalition = sorted(coalition)
                        if sorted_coalition not in valid_coalitions:
                            valid_coalitions.append(sorted_coalition)

        return valid_coalitions

    def analyze_procedure_risk(
        self,
        procedure_ref: str,
        known_opposed: List[str],
        likely_opposed: List[str],
        policy_area: Optional[str] = None
    ) -> BlockingAnalysis:
        """
        Analyze blocking minority risk for a specific procedure.

        Args:
            procedure_ref: OEIL procedure reference
            known_opposed: States confirmed to oppose
            likely_opposed: States likely to oppose
            policy_area: Policy area for context

        Returns:
            BlockingAnalysis with procedure-specific assessment
        """
        # Combine known and likely opposition
        all_opposed = list(set(known_opposed + likely_opposed))

        analysis = self.find_blocking_coalitions(
            base_opposed=known_opposed,
            potential_swing=likely_opposed
        )
        analysis.procedure_ref = procedure_ref

        # Add policy-specific notes
        if policy_area:
            # Add context based on policy area sensitivities
            sensitive_pairs = {
                'agriculture': ['FR', 'PL', 'ES', 'IT'],
                'fiscal': ['DE', 'NL', 'AT', 'FI'],
                'migration': ['IT', 'GR', 'ES', 'PL', 'HU'],
                'climate': ['PL', 'CZ', 'HU', 'BG'],
                'rule_of_law': ['PL', 'HU'],
            }

            sensitive_states = sensitive_pairs.get(policy_area, [])
            potential_joiners = [s for s in sensitive_states if s not in all_opposed]

            if potential_joiners:
                analysis.analysis_notes.append(
                    f"Policy area '{policy_area}' may concern: {', '.join(potential_joiners)}"
                )

        return analysis


# Singleton instance
_calculator_instance: Optional[QMVCalculator] = None


def get_qmv_calculator() -> QMVCalculator:
    """Get or create the QMV calculator instance."""
    global _calculator_instance
    if _calculator_instance is None:
        _calculator_instance = QMVCalculator()
    return _calculator_instance

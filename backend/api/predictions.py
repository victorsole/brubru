"""
Predictions API - Phase 2.2

REST API endpoints for legislative predictions.

Endpoints:
- POST /api/predictions/timeline/{procedure_ref:path} - Timeline prediction
- POST /api/predictions/outcome/{procedure_ref:path} - Outcome prediction
- GET /api/predictions/model-info - Model information
- GET /api/predictions/stagnation-alerts - Stagnating procedures
"""

import logging
from typing import Optional, List, Dict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .auth import get_current_user
from models.user import User

logger = logging.getLogger(__name__)


def require_tier(user: User, allowed_tiers: List[str]) -> None:
    """
    Check if user has required subscription tier.
    Raises HTTPException if not authorized.
    """
    # Admins bypass tier gating (admin is a role, not a subscription tier)
    if user.subscription_tier not in allowed_tiers and user.role != 'admin':
        raise HTTPException(
            status_code=403,
            detail=f"This feature requires {' or '.join(allowed_tiers)} tier subscription"
        )

router = APIRouter(prefix="/api/predictions", tags=["predictions"])


# ============================================================================
# Pydantic Schemas
# ============================================================================

class TimelinePredictionResponse(BaseModel):
    """Timeline prediction response."""
    procedure_ref: str
    current_status: str
    days_in_status: int
    predicted_days_remaining: int
    confidence: float = Field(ge=0.0, le=1.0)

    # Confidence intervals (ML model only)
    lower_bound_25: Optional[int] = None
    upper_bound_75: Optional[int] = None

    # Model info
    model_version: str = "baseline"
    prediction_method: str = "historical_average"

    # Similar procedures for reference
    similar_procedures: List[dict] = []

    class Config:
        from_attributes = True


class OutcomeProbability(BaseModel):
    """Single outcome probability."""
    outcome: str
    probability: float = Field(ge=0.0, le=1.0)
    description: str = ""


class OutcomePredictionResponse(BaseModel):
    """Outcome prediction response."""
    procedure_ref: str
    current_status: str
    predicted_outcome: str
    confidence: float = Field(ge=0.0, le=1.0)

    # All class probabilities
    probabilities: List[OutcomeProbability] = []

    # Model info
    model_version: str = "baseline"

    # Top factors influencing prediction
    top_factors: List[dict] = []

    class Config:
        from_attributes = True


class StagnationAlertResponse(BaseModel):
    """Stagnation alert response."""
    procedure_ref: str
    title: str
    current_status: str
    days_in_status: int
    stagnation_level: str  # normal, warning, alert, critical
    last_update: Optional[datetime] = None


class ModelInfoResponse(BaseModel):
    """Model information response."""
    timeline_model: dict
    outcome_model: dict


# ============================================================================
# Endpoints
# ============================================================================

@router.post(
    "/timeline/{procedure_ref:path}",
    response_model=TimelinePredictionResponse,
    summary="Predict timeline for a procedure"
)
async def predict_timeline(
    procedure_ref: str,
    use_ml: bool = Query(True, description="Use ML model if available"),
    current_user: User = Depends(get_current_user)
):
    """
    Predict the timeline (days remaining) for a legislative procedure.

    Uses XGBoost model if trained and available, otherwise falls back
    to historical average prediction.

    **Requires:** Yellow or Blue tier subscription.
    """
    require_tier(current_user, ["yellow", "blue"])

    try:
        if use_ml:
            try:
                from services.predictions import get_ml_timeline_predictor
                predictor = get_ml_timeline_predictor()
                prediction = await predictor.predict_with_ml(procedure_ref)

                return TimelinePredictionResponse(
                    procedure_ref=prediction.procedure_ref,
                    current_status=prediction.current_status,
                    days_in_status=prediction.days_in_status,
                    predicted_days_remaining=prediction.predicted_days_remaining,
                    confidence=prediction.confidence,
                    lower_bound_25=prediction.lower_bound_25,
                    upper_bound_75=prediction.upper_bound_75,
                    model_version=prediction.model_version,
                    prediction_method="ml_xgboost" if not prediction.used_fallback else prediction.fallback_reason or "fallback"
                )
            except Exception as ml_error:
                logger.warning(f"ML prediction failed, falling back to baseline: {ml_error}")
                # Fall through to baseline prediction
                use_ml = False

        if not use_ml:
            try:
                from services.predictions import get_timeline_predictor
                predictor = get_timeline_predictor()
                prediction = await predictor.predict_timeline(procedure_ref)

                if prediction:
                    return TimelinePredictionResponse(
                        procedure_ref=prediction.procedure_ref,
                        current_status=prediction.current_status,
                        days_in_status=prediction.days_in_status,
                        predicted_days_remaining=prediction.predicted_days_remaining or 0,
                        confidence=prediction.confidence,
                        model_version="baseline",
                        prediction_method=prediction.based_on,
                        similar_procedures=prediction.similar_procedures
                    )
            except Exception as baseline_error:
                logger.warning(f"Baseline prediction also failed: {baseline_error}")

        # Return a minimal fallback prediction
        return TimelinePredictionResponse(
            procedure_ref=procedure_ref,
            current_status="Unknown",
            days_in_status=0,
            predicted_days_remaining=180,  # Default 6 months
            confidence=0.3,
            model_version="fallback",
            prediction_method="default_estimate"
        )

    except Exception as e:
        logger.error(f"Timeline prediction error: {e}")
        # Return minimal fallback instead of error
        return TimelinePredictionResponse(
            procedure_ref=procedure_ref,
            current_status="Unknown",
            days_in_status=0,
            predicted_days_remaining=180,
            confidence=0.2,
            model_version="error_fallback",
            prediction_method="default_estimate"
        )


@router.post(
    "/outcome/{procedure_ref:path}",
    response_model=OutcomePredictionResponse,
    summary="Predict outcome for a procedure"
)
async def predict_outcome(
    procedure_ref: str,
    current_user: User = Depends(get_current_user)
):
    """
    Predict the final outcome of a legislative procedure.

    Outcomes:
    - **adopted**: Procedure successfully completes
    - **blocked**: Procedure stalls without withdrawal
    - **withdrawn**: Commission withdraws the proposal

    **Requires:** Yellow or Blue tier subscription.
    """
    require_tier(current_user, ["yellow", "blue"])

    try:
        from services.predictions import get_outcome_predictor
        predictor = get_outcome_predictor()
        prediction = await predictor.predict_outcome(procedure_ref)

        return OutcomePredictionResponse(
            procedure_ref=prediction.procedure_ref,
            current_status=prediction.current_status,
            predicted_outcome=prediction.predicted_outcome,
            confidence=prediction.confidence,
            probabilities=[
                OutcomeProbability(
                    outcome=p.outcome,
                    probability=p.probability,
                    description=p.description
                )
                for p in prediction.probabilities
            ],
            model_version=prediction.model_version,
            top_factors=prediction.top_factors
        )

    except Exception as e:
        logger.error(f"Outcome prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/stagnation-alerts",
    response_model=List[StagnationAlertResponse],
    summary="Get stagnating procedures"
)
async def get_stagnation_alerts(
    min_level: str = Query("warning", description="Minimum stagnation level (warning, alert, critical)"),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user)
):
    """
    Get procedures that are stagnating (stuck in current status too long).

    Stagnation levels:
    - **warning**: 6-9 months in current status
    - **alert**: 9-12 months in current status
    - **critical**: > 12 months in current status

    **Requires:** Yellow or Blue tier subscription.
    """
    require_tier(current_user, ["yellow", "blue"])

    try:
        from services.predictions import get_timeline_predictor
        from services.predictions.timeline_predictor import StagnationLevel

        predictor = get_timeline_predictor()

        # Map string to enum
        level_map = {
            'warning': StagnationLevel.WARNING,
            'alert': StagnationLevel.ALERT,
            'critical': StagnationLevel.CRITICAL
        }
        level = level_map.get(min_level.lower(), StagnationLevel.WARNING)

        alerts = await predictor.get_stagnation_alerts(min_level=level, limit=limit)

        return [
            StagnationAlertResponse(
                procedure_ref=a.procedure_ref,
                title=a.title,
                current_status=a.current_status,
                days_in_status=a.days_in_status,
                stagnation_level=a.level.value,
                last_update=a.last_update
            )
            for a in alerts
        ]

    except Exception as e:
        logger.error(f"Stagnation alerts error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/model-info",
    response_model=ModelInfoResponse,
    summary="Get prediction model information"
)
async def get_model_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get information about the loaded prediction models.

    Shows model version, features used, and feature importance.

    **Requires:** Blue tier subscription.
    """
    require_tier(current_user, ["blue"])

    try:
        from services.predictions import get_ml_timeline_predictor, get_outcome_predictor

        timeline_predictor = get_ml_timeline_predictor()
        outcome_predictor = get_outcome_predictor()

        timeline_info = await timeline_predictor.get_model_info()
        outcome_info = await outcome_predictor.get_model_info()

        return ModelInfoResponse(
            timeline_model=timeline_info,
            outcome_model=outcome_info
        )

    except Exception as e:
        logger.error(f"Model info error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/train/timeline",
    summary="Train timeline prediction model (Admin only)"
)
async def train_timeline_model(
    training_data_path: str = Query(..., description="Path to training CSV"),
    current_user: User = Depends(get_current_user)
):
    """
    Train the timeline prediction model.

    **Requires:** Admin role.
    """
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        from services.predictions import get_ml_timeline_predictor

        predictor = get_ml_timeline_predictor()
        metrics = await predictor.train_model(training_data_path)

        if 'error' in metrics:
            raise HTTPException(status_code=400, detail=metrics['error'])

        return {"status": "success", "metrics": metrics}

    except Exception as e:
        logger.error(f"Training error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/train/outcome",
    summary="Train outcome prediction model (Admin only)"
)
async def train_outcome_model(
    training_data_path: str = Query(..., description="Path to training CSV"),
    current_user: User = Depends(get_current_user)
):
    """
    Train the outcome prediction model.

    **Requires:** Admin role.
    """
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        from services.predictions import get_outcome_predictor

        predictor = get_outcome_predictor()
        metrics = await predictor.train_model(training_data_path)

        if 'error' in metrics:
            raise HTTPException(status_code=400, detail=metrics['error'])

        return {"status": "success", "metrics": metrics}

    except Exception as e:
        logger.error(f"Training error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Phase 3: EP Voting Predictions
# ============================================================================

class GroupPositionResponse(BaseModel):
    """Group position prediction response."""
    group_code: str
    group_name: str
    predicted_position: str  # FOR, AGAINST, ABSTENTION, SPLIT
    confidence: float
    expected_cohesion: float
    prob_for: float
    prob_against: float
    prob_abstention: float
    factors: List[dict] = []


class PlenaryVoteResponse(BaseModel):
    """Plenary vote prediction response."""
    procedure_ref: str
    title: Optional[str] = None
    predicted_outcome: str  # PASS, FAIL, UNCERTAIN
    confidence: float
    predicted_margin: int
    estimated_for: int
    estimated_against: int
    estimated_abstention: int
    total_meps: int
    group_predictions: List[GroupPositionResponse]
    swing_groups: List[str]


class DelegationDeviationResponse(BaseModel):
    """Delegation deviation prediction response."""
    country_code: str
    country_name: str
    group_code: str
    deviation_risk: str
    deviation_probability: float
    likely_direction: str
    national_interest_factor: float
    governing_status: str
    reasons: List[str]


class CohesionResponse(BaseModel):
    """Cohesion analysis response."""
    entity_type: str
    entity_code: str
    cohesion_score: float
    cohesion_level: str
    votes_analyzed: int
    majority_position: str
    position_breakdown: Dict[str, int]


@router.post(
    "/vote/ep/{procedure_ref:path}",
    response_model=PlenaryVoteResponse,
    summary="Predict EP plenary vote outcome"
)
async def predict_ep_vote(
    procedure_ref: str,
    lead_committee: Optional[str] = Query(None, description="Lead committee code"),
    rapporteur_group: Optional[str] = Query(None, description="Rapporteur's group"),
    current_user: User = Depends(get_current_user)
):
    """
    Predict the outcome of an EP plenary vote.

    Returns:
    - Overall prediction (PASS/FAIL/UNCERTAIN)
    - Estimated vote counts
    - Group-by-group breakdown
    - Swing groups that could change the outcome

    **Requires:** Yellow or Blue tier subscription.
    """
    require_tier(current_user, ["yellow", "blue"])

    try:
        from services.predictions.group_vote_predictor import get_group_vote_predictor

        predictor = get_group_vote_predictor()
        prediction = await predictor.predict_plenary_vote(
            procedure_ref=procedure_ref,
            lead_committee=lead_committee,
            rapporteur_group=rapporteur_group
        )

        return PlenaryVoteResponse(
            procedure_ref=prediction.procedure_ref,
            title=prediction.title,
            predicted_outcome=prediction.predicted_outcome,
            confidence=prediction.confidence,
            predicted_margin=prediction.predicted_margin,
            estimated_for=prediction.estimated_for,
            estimated_against=prediction.estimated_against,
            estimated_abstention=prediction.estimated_abstention,
            total_meps=prediction.total_meps,
            group_predictions=[
                GroupPositionResponse(
                    group_code=gp.group_code,
                    group_name=gp.group_name,
                    predicted_position=gp.predicted_position.value,
                    confidence=gp.confidence,
                    expected_cohesion=gp.expected_cohesion,
                    prob_for=gp.prob_for,
                    prob_against=gp.prob_against,
                    prob_abstention=gp.prob_abstention,
                    factors=gp.factors
                )
                for gp in prediction.group_predictions
            ],
            swing_groups=prediction.swing_groups
        )

    except Exception as e:
        logger.error(f"EP vote prediction error: {e}")
        # Return fallback prediction instead of error
        return PlenaryVoteResponse(
            procedure_ref=procedure_ref,
            title=None,
            predicted_outcome="UNCERTAIN",
            confidence=0.3,
            predicted_margin=0,
            estimated_for=350,
            estimated_against=200,
            estimated_abstention=70,
            total_meps=720,
            group_predictions=[],
            swing_groups=[]
        )


@router.get(
    "/vote/group/{group_code}",
    response_model=GroupPositionResponse,
    summary="Predict single group position"
)
async def predict_group_position(
    group_code: str,
    procedure_ref: str = Query(..., description="OEIL procedure reference"),
    lead_committee: Optional[str] = Query(None),
    rapporteur_group: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user)
):
    """
    Predict a single group's position on a procedure.

    **Requires:** Yellow or Blue tier subscription.
    """
    require_tier(current_user, ["yellow", "blue"])

    try:
        from services.predictions.group_vote_predictor import get_group_vote_predictor

        predictor = get_group_vote_predictor()
        prediction = await predictor.predict_group_position(
            group_code=group_code,
            procedure_ref=procedure_ref,
            lead_committee=lead_committee,
            rapporteur_group=rapporteur_group
        )

        return GroupPositionResponse(
            group_code=prediction.group_code,
            group_name=prediction.group_name,
            predicted_position=prediction.predicted_position.value,
            confidence=prediction.confidence,
            expected_cohesion=prediction.expected_cohesion,
            prob_for=prediction.prob_for,
            prob_against=prediction.prob_against,
            prob_abstention=prediction.prob_abstention,
            factors=prediction.factors
        )

    except Exception as e:
        logger.error(f"Group position prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/cohesion/{group_code}",
    response_model=CohesionResponse,
    summary="Get group cohesion analysis"
)
async def get_group_cohesion(
    group_code: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get cohesion analysis for a political group.

    Shows how unified a group votes historically.

    **Requires:** Yellow or Blue tier subscription.
    """
    require_tier(current_user, ["yellow", "blue"])

    try:
        from services.predictions.cohesion_analyzer import get_cohesion_analyzer

        analyzer = get_cohesion_analyzer()
        result = await analyzer.calculate_group_cohesion(group_code)

        if not result:
            raise HTTPException(status_code=404, detail="No cohesion data available")

        return CohesionResponse(
            entity_type=result.entity_type,
            entity_code=result.entity_code,
            cohesion_score=result.cohesion_score,
            cohesion_level=result.cohesion_level.value,
            votes_analyzed=result.votes_analyzed,
            majority_position=result.majority_position,
            position_breakdown=result.position_breakdown
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cohesion analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/delegations/{group_code}",
    response_model=List[DelegationDeviationResponse],
    summary="Predict delegation deviations"
)
async def predict_delegations(
    group_code: str,
    procedure_ref: str = Query(..., description="OEIL procedure reference"),
    lead_committee: Optional[str] = Query(None),
    expected_position: str = Query("FOR", description="Expected group position"),
    current_user: User = Depends(get_current_user)
):
    """
    Predict which national delegations might deviate from the group line.

    **Requires:** Blue tier subscription.
    """
    require_tier(current_user, ["blue"])

    try:
        from services.predictions.delegation_predictor import get_delegation_predictor

        predictor = get_delegation_predictor()
        deviations = await predictor.predict_deviations(
            group_code=group_code,
            procedure_ref=procedure_ref,
            lead_committee=lead_committee,
            expected_position=expected_position
        )

        return [
            DelegationDeviationResponse(
                country_code=d.country_code,
                country_name=d.country_name,
                group_code=d.group_code,
                deviation_risk=d.deviation_risk.value,
                deviation_probability=d.deviation_probability,
                likely_direction=d.likely_direction,
                national_interest_factor=d.national_interest_factor,
                governing_status=d.governing_status,
                reasons=d.reasons
            )
            for d in deviations
        ]

    except Exception as e:
        logger.error(f"Delegation prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Phase 4: QMV, Committee, and Council Predictions
# ============================================================================

class QMVResultResponse(BaseModel):
    """QMV calculation result."""
    outcome: str  # PASS, FAIL, INSUFFICIENT_DATA
    states_for: int
    states_against: int
    states_abstain: int
    states_undecided: int
    states_for_pct: float
    population_for_pct: float
    meets_state_threshold: bool
    meets_population_threshold: bool
    blocking_minority_possible: bool
    margin_states: int
    margin_population_pct: float


class BlockingCoalitionResponse(BaseModel):
    """Blocking coalition analysis."""
    has_blocking_minority: bool
    risk_level: str  # LOW, MODERATE, HIGH, CRITICAL
    current_blocking_states: List[str]
    current_blocking_population_pct: float
    potential_coalitions: List[Dict]
    swing_states: List[str]


class CommitteeVoteResponse(BaseModel):
    """Committee vote prediction."""
    committee_code: str
    committee_name: str
    procedure_ref: str
    predicted_outcome: str  # APPROVE, REJECT, AMEND_HEAVILY, SPLIT
    confidence: float
    expected_margin: int
    estimated_for: int
    estimated_against: int
    estimated_abstain: int
    rapporteur_group: Optional[str] = None
    shadow_positions: Dict[str, str] = {}
    amendment_risk: str  # low, moderate, high
    key_groups_to_watch: List[str] = []


class CommitteeInfoResponse(BaseModel):
    """Committee information."""
    code: str
    name: str
    full_members: int
    substitutes: int
    total: int
    group_distribution: Dict[str, int]
    pro_eu_balance: int
    eurosceptic_balance: int


class MemberStatePositionResponse(BaseModel):
    """Member state position on a procedure."""
    country_code: str
    country_name: str
    position: str  # SUPPORT, OPPOSE, UNDECIDED, ABSTAIN
    confidence: float
    key_concerns: List[str]
    red_lines: List[str]
    european_family_positions: Dict[str, str]


class CouncilVoteResponse(BaseModel):
    """Council vote prediction."""
    procedure_ref: str
    title: Optional[str] = None
    predicted_outcome: str  # PASS, FAIL, UNCERTAIN
    confidence: float
    qmv_result: QMVResultResponse
    state_positions: List[MemberStatePositionResponse]
    blocking_risk: BlockingCoalitionResponse
    key_concerns: List[str]
    compromise_areas: List[str]


@router.post(
    "/qmv/calculate",
    response_model=QMVResultResponse,
    summary="Calculate QMV outcome"
)
async def calculate_qmv(
    supporting_states: List[str] = Query(..., description="ISO codes of supporting states"),
    opposing_states: List[str] = Query([], description="ISO codes of opposing states"),
    abstaining_states: List[str] = Query([], description="ISO codes of abstaining states"),
    current_user: User = Depends(get_current_user)
):
    """
    Calculate Qualified Majority Voting (QMV) outcome.

    QMV thresholds:
    - **55% of states** (15 of 27)
    - **65% of EU population**

    Blocking minority:
    - **4+ states** representing **>35% population**

    **Requires:** Yellow or Blue tier subscription.
    """
    require_tier(current_user, ["yellow", "blue"])

    try:
        from services.predictions.qmv_calculator import get_qmv_calculator

        calculator = get_qmv_calculator()
        result = calculator.calculate_qmv(
            supporting_states=supporting_states,
            opposing_states=opposing_states,
            abstaining_states=abstaining_states
        )

        return QMVResultResponse(
            outcome=result.outcome.value,
            states_for=result.states_for,
            states_against=result.states_against,
            states_abstain=result.states_abstain,
            states_undecided=result.states_undecided,
            states_for_pct=result.states_for_pct,
            population_for_pct=result.population_for_pct,
            meets_state_threshold=result.meets_state_threshold,
            meets_population_threshold=result.meets_population_threshold,
            blocking_minority_possible=result.blocking_minority_possible,
            margin_states=result.margin_states,
            margin_population_pct=result.margin_population_pct
        )

    except Exception as e:
        logger.error(f"QMV calculation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/qmv/blocking-analysis",
    response_model=BlockingCoalitionResponse,
    summary="Analyze blocking minority risk"
)
async def analyze_blocking_minority(
    base_opposed: List[str] = Query(..., description="ISO codes of definitely opposing states"),
    potential_swing: List[str] = Query([], description="ISO codes of states that might oppose"),
    current_user: User = Depends(get_current_user)
):
    """
    Analyze blocking minority risk for a Council vote.

    Identifies potential blocking coalitions and swing states.

    **Requires:** Blue tier subscription.
    """
    require_tier(current_user, ["blue"])

    try:
        from services.predictions.qmv_calculator import get_qmv_calculator

        calculator = get_qmv_calculator()
        result = calculator.find_blocking_coalitions(
            base_opposed=base_opposed,
            potential_swing=potential_swing
        )

        return BlockingCoalitionResponse(
            has_blocking_minority=result.has_blocking_minority,
            risk_level=result.risk_level.value,
            current_blocking_states=result.current_blocking_states,
            current_blocking_population_pct=result.current_blocking_population_pct,
            potential_coalitions=[
                {
                    'states': c.states,
                    'population_pct': c.population_pct,
                    'probability': c.probability
                }
                for c in result.potential_coalitions[:5]  # Top 5
            ],
            swing_states=result.swing_states
        )

    except Exception as e:
        logger.error(f"Blocking analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/committee/{committee_code}/vote",
    response_model=CommitteeVoteResponse,
    summary="Predict committee vote outcome"
)
async def predict_committee_vote(
    committee_code: str,
    procedure_ref: str = Query(..., description="OEIL procedure reference"),
    rapporteur_group: Optional[str] = Query(None, description="Rapporteur's political group"),
    shadow_positions: Optional[str] = Query(None, description="JSON dict of shadow positions {group: position}"),
    policy_area: Optional[str] = Query(None, description="Policy area for context"),
    current_user: User = Depends(get_current_user)
):
    """
    Predict the outcome of an EP committee vote.

    Uses committee composition and political dynamics.

    **Requires:** Yellow or Blue tier subscription.
    """
    require_tier(current_user, ["yellow", "blue"])

    try:
        import json
        from services.predictions.committee_predictor import get_committee_predictor

        predictor = get_committee_predictor()

        # Parse shadow positions if provided
        shadow_pos = {}
        if shadow_positions:
            try:
                shadow_pos = json.loads(shadow_positions)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid shadow_positions JSON")

        prediction = await predictor.predict_committee_vote(
            committee_code=committee_code,
            procedure_ref=procedure_ref,
            rapporteur_group=rapporteur_group,
            shadow_positions=shadow_pos,
            policy_area=policy_area
        )

        return CommitteeVoteResponse(
            committee_code=prediction.committee_code,
            committee_name=prediction.committee_name,
            procedure_ref=prediction.procedure_ref,
            predicted_outcome=prediction.predicted_outcome.value,
            confidence=prediction.confidence,
            expected_margin=prediction.expected_margin,
            estimated_for=prediction.estimated_for,
            estimated_against=prediction.estimated_against,
            estimated_abstain=prediction.estimated_abstain,
            rapporteur_group=prediction.rapporteur_group,
            shadow_positions=prediction.shadow_positions,
            amendment_risk=prediction.amendment_risk,
            key_groups_to_watch=prediction.key_groups_to_watch
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Committee vote prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/committee/{committee_code}/info",
    response_model=CommitteeInfoResponse,
    summary="Get committee information"
)
async def get_committee_info(
    committee_code: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get information about an EP committee.

    Returns composition and political balance.

    **Requires:** Yellow or Blue tier subscription.
    """
    require_tier(current_user, ["yellow", "blue"])

    try:
        from services.predictions.committee_predictor import get_committee_predictor

        predictor = get_committee_predictor()
        info = predictor.get_committee_info(committee_code)

        if not info:
            raise HTTPException(status_code=404, detail=f"Committee {committee_code} not found")

        return CommitteeInfoResponse(**info)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Committee info error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/council/vote/{procedure_ref:path}",
    response_model=CouncilVoteResponse,
    summary="Predict Council vote outcome"
)
async def predict_council_vote(
    procedure_ref: str,
    policy_area: Optional[str] = Query(None, description="Policy area code"),
    current_user: User = Depends(get_current_user)
):
    """
    Predict the outcome of a Council of the EU vote.

    Infers member state positions based on:
    - Governing party European family positions
    - National interest sensitivities
    - Historical voting patterns

    **Requires:** Blue tier subscription.
    """
    require_tier(current_user, ["blue"])

    try:
        from services.predictions.council_position_inferrer import get_council_position_inferrer

        inferrer = get_council_position_inferrer()
        prediction = await inferrer.predict_council_vote(
            procedure_ref=procedure_ref,
            policy_area=policy_area
        )

        return CouncilVoteResponse(
            procedure_ref=prediction.procedure_ref,
            title=prediction.title,
            predicted_outcome=prediction.predicted_outcome.value,
            confidence=prediction.confidence,
            qmv_result=QMVResultResponse(
                outcome=prediction.qmv_result.outcome.value,
                states_for=prediction.qmv_result.states_for,
                states_against=prediction.qmv_result.states_against,
                states_abstain=prediction.qmv_result.states_abstain,
                states_undecided=prediction.qmv_result.states_undecided,
                states_for_pct=prediction.qmv_result.states_for_pct,
                population_for_pct=prediction.qmv_result.population_for_pct,
                meets_state_threshold=prediction.qmv_result.meets_state_threshold,
                meets_population_threshold=prediction.qmv_result.meets_population_threshold,
                blocking_minority_possible=prediction.qmv_result.blocking_minority_possible,
                margin_states=prediction.qmv_result.margin_states,
                margin_population_pct=prediction.qmv_result.margin_population_pct
            ),
            state_positions=[
                MemberStatePositionResponse(
                    country_code=sp.country_code,
                    country_name=sp.country_name,
                    position=sp.position.value,
                    confidence=sp.confidence,
                    key_concerns=sp.key_concerns,
                    red_lines=sp.red_lines,
                    european_family_positions=sp.european_family_positions
                )
                for sp in prediction.state_positions
            ],
            blocking_risk=BlockingCoalitionResponse(
                has_blocking_minority=prediction.blocking_risk.has_blocking_minority,
                risk_level=prediction.blocking_risk.risk_level.value,
                current_blocking_states=prediction.blocking_risk.current_blocking_states,
                current_blocking_population_pct=prediction.blocking_risk.current_blocking_population_pct,
                potential_coalitions=[
                    {
                        'states': c.states,
                        'population_pct': c.population_pct,
                        'probability': c.probability
                    }
                    for c in prediction.blocking_risk.potential_coalitions[:5]
                ],
                swing_states=prediction.blocking_risk.swing_states
            ),
            key_concerns=prediction.key_concerns,
            compromise_areas=prediction.compromise_areas
        )

    except Exception as e:
        logger.error(f"Council vote prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/council/position/{country_code}",
    response_model=MemberStatePositionResponse,
    summary="Get inferred member state position"
)
async def get_member_state_position(
    country_code: str,
    procedure_ref: str = Query(..., description="OEIL procedure reference"),
    policy_area: Optional[str] = Query(None, description="Policy area code"),
    current_user: User = Depends(get_current_user)
):
    """
    Get inferred position of a single member state on a procedure.

    **Requires:** Blue tier subscription.
    """
    require_tier(current_user, ["blue"])

    try:
        from services.predictions.council_position_inferrer import get_council_position_inferrer

        inferrer = get_council_position_inferrer()
        position = await inferrer.infer_position(
            country_code=country_code.upper(),
            procedure_ref=procedure_ref,
            policy_area=policy_area
        )

        if not position:
            raise HTTPException(status_code=404, detail=f"Could not infer position for {country_code}")

        return MemberStatePositionResponse(
            country_code=position.country_code,
            country_name=position.country_name,
            position=position.position.value,
            confidence=position.confidence,
            key_concerns=position.key_concerns,
            red_lines=position.red_lines,
            european_family_positions=position.european_family_positions
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Member state position error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Resolution Leading Indicators
# ============================================================================

class ResolutionIndicatorResponse(BaseModel):
    """Resolution as a leading indicator for a legislative procedure."""
    resolution_id: str
    procedure_ref: str
    title: str
    resolution_type: str  # INL, INI, RSP
    adoption_date: Optional[str] = None
    vote_for: int
    vote_against: int
    vote_abstention: int
    vote_total: int
    support_percentage: float
    lead_committee: Optional[str] = None
    rapporteur: Optional[str] = None
    match_method: str
    match_confidence: float
    days_before_legislation: Optional[int] = None
    oeil_url: Optional[str] = None


class ResolutionLeadingIndicatorResponse(BaseModel):
    """Response with resolution leading indicators for a procedure."""
    procedure_ref: str
    title: Optional[str] = None
    resolutions: List[ResolutionIndicatorResponse]
    summary: dict  # Aggregated statistics


@router.get(
    "/resolutions/{procedure_ref:path}",
    response_model=ResolutionLeadingIndicatorResponse,
    summary="Get resolution leading indicators for a procedure"
)
async def get_resolution_leading_indicators(
    procedure_ref: str,
    title: Optional[str] = Query(None, description="Procedure title for similarity search"),
    include_similar: bool = Query(True, description="Include title-similarity matches"),
    current_user: User = Depends(get_current_user)
):
    """
    Get EP resolutions that are linked to a legislative procedure.

    Resolutions (INL, INI, RSP) often precede and predict legislative action.
    This endpoint returns resolutions that:
    - Explicitly cross-reference the procedure (OEIL)
    - Led to Commission follow-up resulting in this legislation
    - Have similar titles (if include_similar=True)

    **Resolution Types:**
    - **INL**: Legislative initiative (EP requests legislation)
    - **INI**: Own-initiative report (non-binding recommendations)
    - **RSP**: Resolution (on current issues, emergencies)

    **Match Methods (confidence):**
    - OEIL_CROSSREF (1.0): Explicit OEIL cross-reference
    - COMMISSION_FOLLOWUP (0.9): Commission followed up with proposal
    - TITLE_SIMILARITY (0.5-0.8): Similar titles detected

    **Requires:** Yellow or Blue tier subscription.
    """
    require_tier(current_user, ["yellow", "blue"])

    try:
        from services.matching.resolution_legislation_matcher import (
            find_resolutions_for_legislation,
            find_related_resolutions_by_similarity
        )

        # Get explicitly linked resolutions
        linked_resolutions = await find_resolutions_for_legislation(procedure_ref)

        # Optionally add similarity-based matches
        if include_similar and title and len(linked_resolutions) < 5:
            similar_resolutions = await find_related_resolutions_by_similarity(
                procedure_ref=procedure_ref,
                procedure_title=title,
                min_similarity=0.3
            )
            # Deduplicate
            linked_ids = {r.resolution_id for r in linked_resolutions}
            for res in similar_resolutions:
                if res.resolution_id not in linked_ids:
                    linked_resolutions.append(res)

        # Build response
        resolution_responses = [
            ResolutionIndicatorResponse(
                resolution_id=r.resolution_id,
                procedure_ref=r.procedure_ref,
                title=r.title,
                resolution_type=r.resolution_type,
                adoption_date=r.adoption_date,
                vote_for=r.vote_for,
                vote_against=r.vote_against,
                vote_abstention=r.vote_abstention,
                vote_total=r.vote_total,
                support_percentage=r.support_percentage,
                lead_committee=r.lead_committee,
                rapporteur=r.rapporteur,
                match_method=r.match_method,
                match_confidence=r.match_confidence,
                days_before_legislation=r.days_before_legislation,
                oeil_url=r.oeil_url
            )
            for r in linked_resolutions
        ]

        # Calculate summary statistics
        summary = {
            "total_resolutions": len(resolution_responses),
            "by_type": {},
            "by_method": {},
            "average_support": 0.0,
            "weighted_sentiment": "NEUTRAL"
        }

        if resolution_responses:
            # Count by type
            for r in resolution_responses:
                summary["by_type"][r.resolution_type] = summary["by_type"].get(r.resolution_type, 0) + 1
                summary["by_method"][r.match_method] = summary["by_method"].get(r.match_method, 0) + 1

            # Calculate weighted average support
            total_votes = sum(r.vote_total for r in resolution_responses if r.vote_total > 0)
            if total_votes > 0:
                weighted_support = sum(
                    r.support_percentage * r.vote_total
                    for r in resolution_responses
                    if r.vote_total > 0
                ) / total_votes
                summary["average_support"] = round(weighted_support, 1)

                # Determine sentiment
                if weighted_support >= 70:
                    summary["weighted_sentiment"] = "STRONG_SUPPORT"
                elif weighted_support >= 55:
                    summary["weighted_sentiment"] = "MODERATE_SUPPORT"
                elif weighted_support >= 45:
                    summary["weighted_sentiment"] = "MIXED"
                else:
                    summary["weighted_sentiment"] = "LOW_SUPPORT"

        return ResolutionLeadingIndicatorResponse(
            procedure_ref=procedure_ref,
            title=title,
            resolutions=resolution_responses,
            summary=summary
        )

    except Exception as e:
        logger.error(f"Resolution indicators error: {e}")
        # Return empty response instead of error
        return ResolutionLeadingIndicatorResponse(
            procedure_ref=procedure_ref,
            title=title,
            resolutions=[],
            summary={
                "total_resolutions": 0,
                "by_type": {},
                "by_method": {},
                "average_support": 0.0,
                "weighted_sentiment": "NO_DATA"
            }
        )


@router.get("/calibration/{procedure_ref:path}", summary="Actual roll-call vs prediction (calibration)")
async def get_calibration(
    procedure_ref: str,
    current_user: User = Depends(get_current_user),
):
    """The actual EP roll-call outcome for a procedure (plenary preferred, else
    committee), so a forecast can be shown against what really happened. Returns
    has_vote=false when no roll-call has been recorded yet."""
    require_tier(current_user, ["yellow", "blue"])
    from core.database import SessionLocal
    from sqlalchemy import text as _t
    db = SessionLocal()
    try:
        row = db.execute(_t("""
            SELECT level, result, votes_for, votes_against, votes_abstention, group_breakdown,
                   vote_date, ta_reference, source_url
            FROM ep_roll_call_votes
            WHERE procedure_ref = :p
            ORDER BY (CASE WHEN level='plenary' THEN 0 ELSE 1 END), vote_date DESC NULLS LAST
            LIMIT 1
        """), {"p": procedure_ref}).fetchone()
        if not row:
            return {"has_vote": False, "procedure_ref": procedure_ref}
        return {
            "has_vote": True, "procedure_ref": procedure_ref,
            "level": row.level, "result": row.result,
            "votes_for": row.votes_for, "votes_against": row.votes_against,
            "votes_abstention": row.votes_abstention,
            "group_breakdown": row.group_breakdown or {},
            "vote_date": row.vote_date.isoformat() if row.vote_date else None,
            "ta_reference": row.ta_reference, "source_url": row.source_url,
        }
    finally:
        db.close()

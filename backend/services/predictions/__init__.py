"""
Prediction Services - Phase 1.4+

Services for legislative predictions and timeline analysis.

Phase 1.4: Basic timeline predictions (historical averages)
Phase 2.1: ML feature extraction, training data export, XGBoost timeline model
Phase 2.2: Outcome prediction, API endpoints
Phase 3: EP voting predictions (cohesion, groups, delegations)
Phase 4: QMV calculator, committee predictions, Council position inference
"""

from .timeline_predictor import TimelinePredictor, get_timeline_predictor
from .feature_extractor import FeatureExtractor, CarriageFeatures, get_feature_extractor
from .ml_timeline_predictor import MLTimelinePredictor, MLPrediction, get_ml_timeline_predictor
from .outcome_predictor import OutcomePredictor, OutcomePrediction, get_outcome_predictor
from .cohesion_analyzer import CohesionAnalyzer, get_cohesion_analyzer
from .group_vote_predictor import GroupVotePredictor, get_group_vote_predictor
from .delegation_predictor import DelegationPredictor, get_delegation_predictor
from .qmv_calculator import QMVCalculator, get_qmv_calculator
from .committee_predictor import CommitteePredictor, get_committee_predictor
from .council_position_inferrer import CouncilPositionInferrer, get_council_position_inferrer

__all__ = [
    # Phase 1.4
    "TimelinePredictor",
    "get_timeline_predictor",
    # Phase 2.1
    "FeatureExtractor",
    "CarriageFeatures",
    "get_feature_extractor",
    "MLTimelinePredictor",
    "MLPrediction",
    "get_ml_timeline_predictor",
    # Phase 2.2
    "OutcomePredictor",
    "OutcomePrediction",
    "get_outcome_predictor",
    # Phase 3
    "CohesionAnalyzer",
    "get_cohesion_analyzer",
    "GroupVotePredictor",
    "get_group_vote_predictor",
    "DelegationPredictor",
    "get_delegation_predictor",
    # Phase 4
    "QMVCalculator",
    "get_qmv_calculator",
    "CommitteePredictor",
    "get_committee_predictor",
    "CouncilPositionInferrer",
    "get_council_position_inferrer",
]

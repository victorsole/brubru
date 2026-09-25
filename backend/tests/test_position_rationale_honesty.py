"""A placeholder cohesion is never shown as a measurement (25 Sep 2026).

With ep_member_votes empty, every group in all 43 snapshots showed "cohesion
0.75" and "Historical pattern favours FOR", which rested on no history at all.
"""
from types import SimpleNamespace

from services.positions.position_aggregator import PositionAggregator, _not_measured


def _gp(prob_for, factors):
    return SimpleNamespace(group_code="S&D", predicted_position="for", expected_cohesion=0.75,
                           prob_for=prob_for, prob_against=0.1, factors=factors)


def test_no_history_no_measured_cohesion_says_so():
    gp = _gp(0.7, [{"factor": "cohesion_not_measured", "value": True}])
    text = PositionAggregator._group_rationale(gp, None)
    assert "not measured" in text
    assert "Historical" not in text
    assert "0.75" not in text
    assert _not_measured(gp)


def test_history_is_named_only_when_used():
    gp = _gp(0.7, [{"factor": "historical_pattern", "value": "70% FOR"}])
    text = PositionAggregator._group_rationale(gp, None)
    assert "Historical voting pattern favours FOR" in text
    assert not _not_measured(gp)


def test_default_stances_do_not_make_a_file_complete():
    groups = [{"group_code": "EPP", "cohesion": None}, {"group_code": "S&D", "cohesion": None}]
    com = {"com_references": ["COM(2026) 1"]}
    council = {"member_states": ["DE"]}
    assert PositionAggregator._completeness(com, {"groups": groups}, council) == "partial"
    measured = [{"group_code": "EPP", "cohesion": 0.9}]
    assert PositionAggregator._completeness(com, {"groups": measured}, council) == "full"


def test_response_model_carries_the_basis():
    from api.predictions import PlenaryVoteResponse
    assert "basis" in PlenaryVoteResponse.model_fields

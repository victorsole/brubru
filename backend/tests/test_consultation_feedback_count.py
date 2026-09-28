"""Consultation response counts are the sum over the initiative's publications (28 Sep 2026).

The old backfill read the initiative id as a publication id and stored another
publication's total (EU Inc.: 61 stored, 2,518 real)."""
import importlib.util
import sys
from pathlib import Path

_p = Path(__file__).resolve().parents[1] / "scripts" / "backfill_consultations_feedback_count.py"
_spec = importlib.util.spec_from_file_location("bcfc", _p)
bcfc = importlib.util.module_from_spec(_spec)
sys.modules["bcfc"] = bcfc
_spec.loader.exec_module(bcfc)


def test_count_is_the_sum_over_publications():
    eu_inc = {"id": 14674, "publications": [
        {"id": 19616, "totalFeedback": 0}, {"id": 19997, "totalFeedback": 879},
        {"id": 19998, "totalFeedback": 1470}, {"id": 23065, "totalFeedback": 169}]}
    assert bcfc.total_feedback(eu_inc) == 2518


def test_missing_fields_count_as_zero():
    assert bcfc.total_feedback({"publications": [{"id": 1}, {"id": 2, "totalFeedback": None}]}) == 0
    assert bcfc.total_feedback({}) == 0


def test_the_list_sync_no_longer_writes_the_count_on_existing_rows():
    src = (Path(__file__).resolve().parents[1] / "services" / "scrapers" /
           "consultation_sync_service.py").read_text()
    assert "existing.feedback_count = item.feedback_count" not in src


def test_scheduled_and_never_on_agency_rows():
    from services.sync.source_registry import sources_for_tier
    specs = {s.key: s for s in sources_for_tier("warm")}
    assert "consultation_counts" in specs
    code = _p.read_text()
    assert code.count("source = 'commission'") >= 3        # every selection excludes agency rows

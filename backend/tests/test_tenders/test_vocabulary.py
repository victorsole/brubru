"""
Tests for the code -> plain-language vocabulary, and for the contract it shares
with the frontend.

The decode exists twice by necessity: the frontend's labels must be localised
into Brubru's six languages, the backend's serve Excel exports and the Chat
context block. Two runtimes, one contract. These tests are what stops them
drifting apart silently -- which is the state they were already in when this
was written: the detail page decoded procedure_type while the spreadsheet of
the same tender wrote "neg-w-call".
"""
import re
from pathlib import Path

import pytest

from services.tenders.vocabulary import (
    AWARD_CRITERIA_TYPES,
    CONTRACT_NATURES,
    PROCEDURE_TYPES,
    award_criteria_label,
    contract_nature_label,
    procedure_label,
)

FRONTEND = Path(__file__).resolve().parents[3] / "frontend" / "src"
DETAIL_TSX = FRONTEND / "components" / "tenders" / "tender_detail.tsx"


def _codes_in_ts_map(source: str, const_name: str) -> set[str]:
    """The quoted keys of a `const NAME: Record<string, string> = { ... }`."""
    match = re.search(rf"const {const_name}[^=]*=\s*\{{(.*?)\}};", source, re.S)
    assert match, f"{const_name} not found in tender_detail.tsx"
    return set(re.findall(r"'([^']+)'\s*:", match.group(1)))


class TestDecoding:
    def test_known_codes_become_readable(self):
        assert procedure_label("neg-w-call") == "Negotiated (with prior call)"
        assert award_criteria_label("best-value") == "Best price-quality ratio"
        assert contract_nature_label("supplies") == "Supplies"

    def test_unknown_code_returns_itself_not_none(self):
        """A gap must stay visible. Blanking it hides both the value and the gap."""
        assert procedure_label("some-new-eforms-code") == "some-new-eforms-code"

    def test_missing_value_stays_missing(self):
        for value in (None, ""):
            assert procedure_label(value) is None
            assert award_criteria_label(value) is None
            assert contract_nature_label(value) is None

    def test_case_and_whitespace_tolerated(self):
        assert procedure_label("  Neg-W-Call ") == "Negotiated (with prior call)"

    def test_no_label_is_blank(self):
        for mapping in (PROCEDURE_TYPES, AWARD_CRITERIA_TYPES, CONTRACT_NATURES):
            for code, label in mapping.items():
                assert label.strip(), f"{code} has an empty label"
                assert label != code, f"{code} was not actually decoded"


class TestFrontendParity:
    """The two maps must cover the same codes, or one surface explains a
    tender and another does not."""

    def test_procedure_codes_match_the_frontend(self):
        ts_codes = _codes_in_ts_map(DETAIL_TSX.read_text(), "PROCEDURE_LABELS_I18N_KEYS")
        py_codes = set(PROCEDURE_TYPES)
        assert py_codes == ts_codes, (
            f"only in backend: {sorted(py_codes - ts_codes)} | "
            f"only in frontend: {sorted(ts_codes - py_codes)}"
        )

    def test_award_criteria_codes_match_the_frontend(self):
        ts_codes = _codes_in_ts_map(DETAIL_TSX.read_text(), "AWARD_CRITERIA_I18N_KEYS")
        py_codes = set(AWARD_CRITERIA_TYPES)
        assert py_codes == ts_codes, (
            f"only in backend: {sorted(py_codes - ts_codes)} | "
            f"only in frontend: {sorted(ts_codes - py_codes)}"
        )


class TestSchemasExposeLabels:
    """The label has to reach the wire, or the Excel export and Chat still
    receive the code."""

    def test_summary_carries_procedure_label(self):
        from schemas.tender_schemas import TenderSummary
        payload = TenderSummary(
            id=1, publication_number="1-2026", title="T",
            procedure_type="neg-w-call", contract_nature="supplies",
        ).model_dump()
        assert payload["procedure_label"] == "Negotiated (with prior call)"
        assert payload["contract_nature_label"] == "Supplies"

    def test_detail_carries_all_three(self):
        from schemas.tender_schemas import TenderDetail
        payload = TenderDetail(
            id=1, publication_number="1-2026", title="T",
            procedure_type="comp-dial", award_criteria_type="best-value",
            contract_nature="works",
        ).model_dump()
        assert payload["procedure_label"] == "Competitive dialogue"
        assert payload["award_criteria_label"] == "Best price-quality ratio"
        assert payload["contract_nature_label"] == "Works"


class TestEveryCodeInProductionIsMapped:
    """Codes actually present in the corpus, from a 28 Aug 2026 GROUP BY.
    A code we serve and cannot name is the whole bug."""

    @pytest.mark.parametrize("code", [
        "open", "neg-w-call", "restricted", "oth-single", "comp-dial",
        "neg-wo-call", "comp-tend",
    ])
    def test_live_procedure_codes(self, code):
        assert code in PROCEDURE_TYPES

    @pytest.mark.parametrize("code", ["quality", "price", "cost", "best-value"])
    def test_live_award_criteria_codes(self, code):
        assert code in AWARD_CRITERIA_TYPES

    @pytest.mark.parametrize("code", ["services", "supplies", "works"])
    def test_live_contract_natures(self, code):
        assert code in CONTRACT_NATURES

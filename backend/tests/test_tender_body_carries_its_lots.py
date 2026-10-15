"""A call for tenders' body carries its lots' names and descriptions (15 Oct 2026).

251 tenders published since July 2024 served under 200 characters on
/api/v2/funding/ft-calls-for-tenders: SEDIA's `description` is often one sentence, and
the lots (an eForms JSON string in the same record) describe what is bought."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ingest_funding_sedia as sedia  # noqa: E402


def _lots(*lots):
    return [json.dumps({"procurementProjectLots": [
        {"procurementProjectLotID": lot_id, "procurementProject": {"name": name, "description": desc}}
        for lot_id, name, desc in lots]})]


def test_each_lot_adds_its_name_and_description():
    md = {"lots": _lots(("LOT-0001", "Medical centre", "Pre-recruitment tests and annual checks."),
                        ("LOT-0002", "Medical advice", "Advice on occupational health."))}
    got = sedia.tender_lots_text(md, "Medical services for Fusion for Energy.")
    assert got == ("Lot 1: Medical centre. Pre-recruitment tests and annual checks.\n"
                   "Lot 2: Medical advice. Advice on occupational health.")


def test_a_lot_repeating_the_tender_adds_nothing():
    md = {"lots": _lots(("PAR-0001", "Provision of Interim Staff services to the EIT",
                         "Provision of Interim Staff services to the EIT."))}
    assert sedia.tender_lots_text(md, "Provision of Interim Staff services to the EIT.") == ""


def test_old_and_malformed_lots_are_skipped():
    assert sedia.tender_lots_text({"lots": ["[]", "not json", json.dumps([1, "x"])]}, "x") == ""


def test_cpv_codes_come_from_the_main_code_then_each_lot():
    md = {"mainCpv": ["79620000"],
          "lots": [json.dumps({"procurementProjectLots": [
              {"procurementProject": {"mainCommodityClassification": {"itemClassificationCode": "79620000"}}},
              {"procurementProject": {"mainCommodityClassification": {"itemClassificationCode": "72000000"}}}]})]}
    assert sedia.tender_cpv_codes(md) == ["79620000", "72000000"]
    assert sedia.tender_cpv_codes({"lots": ["[]"]}) == []

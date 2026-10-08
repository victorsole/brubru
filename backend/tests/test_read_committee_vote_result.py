"""The committee vote reader (8 Oct 2026): both layouts the Parliament uses, and never a guess."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import read_committee_vote_result as r  # noqa: E402

LEAD_LABELS_FIRST = ("... INFORMATION ON ADOPTION BY THE COMMITTEE RESPONSIBLE Date adopted 1.10.2026 "
                     "Result of final vote +: –: 0: 38 1 4 FINAL VOTE BY ROLL CALL BY THE COMMITTEE RESPONSIBLE 38 + NI ...")
OPINION_PAIRS = ("... INFORMATION ON ADOPTION IN COMMITTEE ASKED FOR OPINION Date adopted 10.9.2026 "
                 "Result of final vote + : 25 - : 6 0 : 0 FINAL VOTE BY ROLL CALL BY THE COMMITTEE ASKED FOR OPINION 25 + PPE ...")
DISCHARGE = ("INFORMATION ON ADOPTION BY THE COMMITTEE RESPONSIBLE Date adopted 1.10.2026 "
             "Result of final vote +: –: 0: 1 19 1 FINAL VOTE BY ROLL CALL BY THE COMMITTEE RESPONSIBLE 1 + PfE")


def test_labels_first_layout():
    (b,) = r.parse_vote_blocks(LEAD_LABELS_FIRST)
    assert b == {"committee_role": "lead (responsible)", "date_adopted": "1.10.2026", "result": (38, 1, 4)}


def test_label_value_pairs_layout():
    (b,) = r.parse_vote_blocks(OPINION_PAIRS)
    assert (b["committee_role"], b["date_adopted"], b["result"]) == ("opinion", "10.9.2026", (25, 6, 0))


def test_a_lead_and_an_opinion_block_in_one_report_are_both_returned():
    blocks = r.parse_vote_blocks(OPINION_PAIRS + " ... " + LEAD_LABELS_FIRST)
    assert [x["result"] for x in blocks] == [(25, 6, 0), (38, 1, 4)]


def test_one_in_favour_nineteen_against_is_read_in_the_right_order():
    (b,) = r.parse_vote_blocks(DISCHARGE)
    assert b["result"] == (1, 19, 1)


def test_unreadable_numbers_are_none_not_a_guess():
    (b,) = r.parse_vote_blocks("INFORMATION ON ADOPTION BY THE COMMITTEE RESPONSIBLE Date adopted 1.10.2026 Result of final vote see annex")
    assert b["result"] is None


def test_no_block_means_no_result():
    assert r.parse_vote_blocks("DRAFT REPORT without any adoption information yet") == []


def test_report_reference_becomes_the_doceo_url():
    assert r.report_url("A10-0259/2026").endswith("/A-10-2026-0259_EN.html")

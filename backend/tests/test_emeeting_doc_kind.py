"""doc_kind reads a DV document's filename: a hyphenated VL- prefix is a voting list (3 Nov 2026)."""
import pathlib
import sys

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
sys.path.insert(0, _REPO_ROOT + "/backend")

from services.scrapers.ep_emeeting_client import doc_kind  # noqa: E402


def test_vl_hyphen_prefix_is_a_voting_list():
    assert doc_kind("DV", "VL-Provisional Agreement 2026_CSAD RECAST", None) == "voting_list"
    assert doc_kind("DV", "VL-MfR_on_MRLs_for_flupyradifurone", None) == "voting_list"


def test_existing_voting_list_forms_still_match():
    assert doc_kind("DV", "Final VL_INI", None) == "voting_list"
    assert doc_kind("DV", "Final_VotingList_AFCO", None) == "voting_list"


def test_words_merely_starting_with_vl_stay_miscellaneous():
    assert doc_kind("DV", "Vlaamse position paper", None) == "miscellaneous"
    assert doc_kind("DV", "EMFAstudy", None) == "miscellaneous"

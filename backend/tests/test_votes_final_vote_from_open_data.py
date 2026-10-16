"""A text's plenary vote is its FINAL vote, never an amendment vote (16 Oct 2026).

/api/v2/parliament/votes served 97 amendment or paragraph votes as the vote on a text, and
40 texts Parliament adopted as REJECTED: the Kosovo report "Am 2" 252-305, adopted 412-174.
The picker fell back to the sub-item with the most MEPs recorded when the final vote was by
show of hands. EP Open Data names each adopted text's final vote; it now decides."""
from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

from api.v1.ep_entities import _rollcall_to_item
from scripts.sync_ep_votes import choose_final_subitem, open_data_final, open_data_subject, open_data_vote
from services.scrapers.ep_votes_scraper import ParsedVote, VoteRecord, pick_final_subitem, subitem_with_counts


def _sub(subject, f, a, b, n=0, number="1.1"):
    v = ParsedVote(votes_for=f, votes_against=a, votes_abstention=b,
                   result="adopted" if f > a else "rejected",
                   records=[VoteRecord(f"MEP {i}", "PPE", "+") for i in range(n)])
    return {"subject": subject, "vote": v, "subitem_number": number, "report_ref": "A10-0166/2026"}


KOSOVO = {"1": {"title": "2025 Commission report on Kosovo", "subitems": [
    _sub("Am 2", 252, 305, 89, n=646, number="1.1"),
    _sub("§ 12/2", 401, 160, 70, n=631, number="1.2"),
    _sub("Motion for a resolution (as a whole)", 412, 174, 58, n=644, number="1.3")]},
    "2": {"title": "2025 Commission report on Albania", "subitems": [
    _sub("Motion for a resolution (as a whole)", 483, 103, 52, n=638, number="2.1")]}}


def test_an_amendment_vote_is_never_the_texts_vote():
    only_amendments = [_sub("Am 2", 199, 382, 8, n=589), _sub("§ 3/2", 443, 62, 44, n=549),
                       _sub("Proposal to vote on amendments", 135, 468, 51, n=654)]
    assert pick_final_subitem(only_amendments) is None
    assert pick_final_subitem(KOSOVO["1"]["subitems"])["subject"] == "Motion for a resolution (as a whole)"


def test_the_open_data_counts_find_the_roll_call_whatever_its_title():
    assert subitem_with_counts(KOSOVO, 412, 174, 58)["subitem_number"] == "1.3"
    assert subitem_with_counts(KOSOVO, 483, 103, 52)["subitem_number"] == "2.1"
    assert subitem_with_counts(KOSOVO, 1, 2, 3) is None
    assert subitem_with_counts(KOSOVO, None, None, None) is None


def test_open_data_decides_and_a_show_of_hands_has_no_counts():
    od = open_data_final({"source": "ep_open_data", "result": "adopted", "method": "roll-call",
                          "for": 412, "against": 174, "abstention": 58})
    assert choose_final_subitem(KOSOVO, KOSOVO["1"], od)["subitem_number"] == "1.3"
    hands = open_data_final({"source": "ep_open_data", "result": "adopted", "method": "show of hands",
                             "for": None, "against": None, "abstention": None})
    assert choose_final_subitem(KOSOVO, KOSOVO["1"], hands) is None
    pv = open_data_vote(hands)
    assert (pv.votes_for, pv.votes_against, pv.votes_abstention, pv.result, pv.vote_type) == (
        None, None, None, "adopted", "show of hands")
    assert open_data_subject(hands) == "Final vote (show of hands)"
    assert open_data_subject({"label": "Motion for a resolution (as a whole)"}) == "Motion for a resolution (as a whole)"
    assert open_data_final({"source": "ep_roll_call_votes", "result": "adopted"}) is None
    assert open_data_final(None) is None


def test_without_open_data_the_title_match_still_refuses_an_amendment():
    item = {"subitems": [_sub("Am 1", 186, 336, 37, n=559)]}
    assert choose_final_subitem({"1": item}, item, None) is None


def test_the_route_serves_a_show_of_hands_as_null_counts():
    row = SimpleNamespace(
        id="00000000-0000-0000-0000-000000000002", title="The upcoming EU anti-corruption strategy",
        report_ref="B10-0423/2026", subject="Final vote (show of hands)", procedure_ref="2026/2790(RSP)",
        level="plenary", votes_for=None, votes_against=None, votes_abstention=None, result="adopted",
        ta_reference="P10_TA(2026)0341", updated_at=datetime(2026, 10, 16, 3, 0),
        created_at=datetime(2026, 10, 16, 3, 0),
        source_url="https://www.europarl.europa.eu/doceo/document/PV-10-2026-10-08-RCV_EN.html",
        vote_date=date(2026, 10, 8), sitting_date=date(2026, 10, 8), group_breakdown={},
        country_breakdown={}, last_updated=None, vote_type="show of hands", committee_code="LIBE",
        item_number=None, total_records=0)
    item = _rollcall_to_item(row)
    assert (item.count_for, item.count_against, item.count_abstention, item.result) == (None, None, None, "ADOPTED")
    assert "For:" not in item.body_txt and "Vote type: show of hands" in item.body_txt

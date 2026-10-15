"""Plenary roll-call votes are read from the sitting's RCV XML when its page is interactive (15 Oct 2026).

From some sittings of July 2025 on, the English RCV page is an interactive page the HTML
parser reads as empty: 37 sitting days gave no vote and July-December 2025 held 12."""
from __future__ import annotations

import inspect

from services.scrapers.ep_votes_scraper import parse_plenary_rcv_xml, pick_final_subitem, rcv_xml_url

XML = """<?xml version="1.0" encoding="UTF-8"?>
<PV.RollCallVoteResults xmlns:text="http://openoffice.org/2000/text" Sitting.Date="2025-10-22">
<VoteTitles><VoteTitle DlvId="974702">Situation in Belarus, five years after the fraudulent presidential elections</VoteTitle></VoteTitles>
<RollCallVote.Result Identifier="1" DlvId="974702" Date="2025-10-22 12:00:00"><RollCallVote.Description.Text>RC-B10-0441/2025 – § 3 – Am 2</RollCallVote.Description.Text>
<Result.For Number="2"><Result.PoliticalGroup.List Identifier="PPE"><PoliticalGroup.Member.Name MepId="1">Adamowicz</PoliticalGroup.Member.Name><PoliticalGroup.Member.Name MepId="2">Arłukowicz</PoliticalGroup.Member.Name></Result.PoliticalGroup.List></Result.For>
<Result.Against Number="1"><Result.PoliticalGroup.List Identifier="ESN"><PoliticalGroup.Member.Name MepId="3">Anderson</PoliticalGroup.Member.Name></Result.PoliticalGroup.List></Result.Against>
<Result.Abstention Number="0"></Result.Abstention></RollCallVote.Result>
<RollCallVote.Result Identifier="2" DlvId="974702" Date="2025-10-22 12:01:00"><RollCallVote.Description.Text>RC-B10-0441/2025 – Motion for a resolution (as a whole)</RollCallVote.Description.Text>
<Result.For Number="458"></Result.For><Result.Against Number="18"></Result.Against><Result.Abstention Number="84"></Result.Abstention></RollCallVote.Result>
</PV.RollCallVoteResults>"""


def test_items_take_their_vote_title_and_the_final_vote_its_counts():
    items = parse_plenary_rcv_xml(XML)
    assert list(items) == ["974702"]
    item = items["974702"]
    assert item["title"].startswith("Situation in Belarus")
    assert [s["subitem_number"] for s in item["subitems"]] == ["974702.1", "974702.2"]
    first = item["subitems"][0]["vote"]
    assert (first.votes_for, first.votes_against, first.votes_abstention) == (2, 1, 0)
    assert [(r.name, r.group, r.choice) for r in first.records] == [
        ("Adamowicz", "PPE", "+"), ("Arłukowicz", "PPE", "+"), ("Anderson", "ESN", "-")]
    fin = pick_final_subitem(item["subitems"])["vote"]
    assert (fin.votes_for, fin.votes_against, fin.votes_abstention, fin.result) == (458, 18, 84, "adopted")


def test_the_xml_address_and_the_fallback_in_the_sync():
    from datetime import date
    assert rcv_xml_url(date(2025, 10, 22)).endswith("/PV-10-2025-10-22-RCV_EN.xml")
    from scripts import sync_ep_votes
    src = inspect.getsource(sync_ep_votes)
    assert "parse_plenary_rcv_xml(body)" in src and "fetch_bytes(rcv_xml_url(cand)" in src


def test_broken_xml_gives_nothing():
    assert parse_plenary_rcv_xml(b"<not xml") == {} and parse_plenary_rcv_xml(b"") == {}


def test_a_new_pick_replaces_the_earlier_plenary_vote_on_the_same_text():
    from scripts import sync_ep_votes
    src = inspect.getsource(sync_ep_votes._upsert_vote)
    assert 'EpVote.ta_reference == ta' in src and "EpVote.vote_key != vote_key" in src


class _OeilDb:
    def __init__(self, events):
        self.events = events

    def execute(self, stmt, params):
        events = self.events
        return type("R", (), {"fetchone": lambda _s: (events,)})()


def test_a_committee_vote_takes_oeils_vote_date_before_its_report_is_tabled():
    from datetime import date
    from scripts.sync_ep_votes import _oeil_committee_vote_date
    events = [
        {"date": "2024-02-13", "event_type": "Vote in committee, 1st reading"},
        {"date": "2024-02-19", "event_type": "Committee report tabled for plenary, 1st reading", "description": "A9-0042/2024"},
        {"date": "2025-12-03", "event_type": "Vote in committee, 2nd reading"},
        {"date": "2025-12-04", "event_type": "Committee recommendation tabled for plenary, 2nd reading", "description": "A10-0246/2025"},
    ]
    db = _OeilDb(events)
    assert _oeil_committee_vote_date(db, "2023/0129(COD)", "A10-0246/2025") == date(2025, 12, 3)
    assert _oeil_committee_vote_date(db, "2023/0129(COD)", "A9-0042/2024") == date(2024, 2, 13)
    assert _oeil_committee_vote_date(db, "2023/0129(COD)", "A10-9999/2025") is None


def test_an_undated_vote_is_neither_written_nor_served():
    from scripts import sync_ep_votes
    from api.v1 import ep_entities
    assert 'counts["committee_undated"]' in inspect.getsource(sync_ep_votes)
    assert "RollCallVote.vote_date.isnot(None), RollCallVote.sitting_date.isnot(None)" in inspect.getsource(ep_entities)

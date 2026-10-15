"""Votes are described by their real source and carry their procedure type (15 Oct 2026).

/api/v2/parliament/votes said its rows came from HowTheyVote and linked there, though they
are read from Parliament's own roll-call minutes and link to europarl.europa.eu; and
procedure_type was null on all 688 rows although the procedure reference names it."""
from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

from api.v1.ep_entities import _rollcall_to_item


def _row(**kw):
    base = dict(id="00000000-0000-0000-0000-000000000001", title="Situation in Belarus", report_ref="RC-B10-0441/2025",
                subject="Motion for a resolution (as a whole)", procedure_ref="2025/2901(RSP)", level="plenary",
                votes_for=458, votes_against=18, votes_abstention=84, result="adopted", ta_reference="P10_TA(2025)0230",
                updated_at=datetime(2026, 10, 15, 16, 0), created_at=datetime(2026, 10, 15, 16, 0),
                source_url="https://www.europarl.europa.eu/doceo/document/PV-10-2025-10-22-RCV_EN.html",
                vote_date=date(2025, 10, 22), sitting_date=date(2025, 10, 22),
                group_breakdown={"PPE": {"+": 170, "-": 0, "0": 2}}, country_breakdown={}, last_updated=None,
                vote_type="rcv", committee_code=None, item_number="974702.2", total_records=560)
    base.update(kw)
    return SimpleNamespace(**base)


def test_a_vote_carries_its_procedure_type_and_the_minutes_link():
    item = _rollcall_to_item(_row())
    assert item.procedure_type == "RSP"
    assert item.public_url.startswith("https://www.europarl.europa.eu/doceo/document/PV-10-2025-10-22-RCV")
    assert (item.count_for, item.count_against, item.count_abstention, item.result) == (458, 18, 84, "ADOPTED")


def test_no_procedure_reference_gives_no_type():
    assert _rollcall_to_item(_row(procedure_ref=None)).procedure_type is None


def test_the_route_no_longer_names_howtheyvote_as_its_source():
    from api.v2.parliament.ep_entities import votes_router
    for route in votes_router.routes:
        text = (route.summary or "") + (route.description or "")
        assert "howtheyvote.eu/votes" not in text and "sourced from HowTheyVote" not in text

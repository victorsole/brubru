"""Every resolution procedure carries a document_date (15 Oct 2026).

577 of 958 procedures in GovClipping's walk had none: no adoption and no vote, 484 of them
debates closed without a resolution. Their first OEIL event dates them."""
import uuid
from datetime import date, datetime

from api.v1.resolutions import _row_to_item
from models.ep_resolutions import EPResolution


def _row(**kw):
    r = EPResolution(id=uuid.uuid4(), procedure_ref="2026/2919(RSP)", title="Debate", status="closed_without_resolution",
                     oeil_url="https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=2026/2919(RSP)",
                     created_at=datetime(2026, 10, 9), updated_at=datetime(2026, 10, 9))
    for k, v in kw.items():
        setattr(r, k, v)
    return r


def test_a_closed_debate_is_dated_by_its_first_event():
    events = [{"date": "2026-10-08", "event_type": "debate_in_parliament"},
              {"date": "2026-10-09", "event_type": "end_of_procedure_in_parliament"}]
    assert _row_to_item(_row(), oeil_events=events).document_date == date(2026, 10, 8)


def test_an_adopted_resolution_keeps_its_adoption_date():
    item = _row_to_item(_row(adoption_date=date(2026, 3, 12), vote_date=datetime(2026, 3, 11)),
                        oeil_events=[{"date": "2025-11-02", "event_type": "referral"}])
    assert item.document_date == date(2026, 3, 12)


def test_no_event_no_date():
    assert _row_to_item(_row(), oeil_events=[]).document_date is None

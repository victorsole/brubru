"""Both Have Your Say writers must read a portal record the same way.

Until 25 Sep 2026 sync_consultations.py defaulted to OPEN when no current stage
said OPEN or CLOSED, while sync_have_your_say.py (the owner) derived the status
from every stage. Both run daily, so they rewrote each other: 627 closed->open
"changes" in seven days, and initiatives whose only remaining window is UPCOMING
(CBAM extension 14748, military mobility 14850, air services 14620) were shown
as open for comment. The fixture is real portal output covering every status
shape seen in the first ~1,200 initiatives.
"""
import importlib.util
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.api_clients.have_your_say_client import HaveYourSayClient
from services.scrapers.consultation_sync_service import ConsultationSyncService

HERE = Path(__file__).resolve().parent
RECORDS = json.loads((HERE / "fixtures" / "hys_search_initiatives_2026_09_25.json").read_text())

_spec = importlib.util.spec_from_file_location(
    "sync_have_your_say", HERE.parent / "scripts" / "sync_have_your_say.py")
sweep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sweep)


def _ids(r):
    return str(int(float(r["id"])))


@pytest.mark.parametrize("record", RECORDS, ids=_ids)
def test_parser_and_sweep_agree(record):
    owner = sweep.map_initiative(record)
    ours = HaveYourSayClient.__new__(HaveYourSayClient)._parse_initiative(record)
    if owner is None or ours is None:
        pytest.skip("record without id or title")
    assert getattr(ours.status, "value", ours.status) == owner["status"]
    assert ours.start_date == owner["start_date"]
    assert ours.end_date == owner["end_date"]


@pytest.mark.parametrize("iid", ["14748", "14850", "14620"])
def test_upcoming_only_is_not_open(iid):
    record = next(r for r in RECORDS if _ids(r) == iid)
    ours = HaveYourSayClient.__new__(HaveYourSayClient)._parse_initiative(record)
    assert getattr(ours.status, "value", ours.status) != "open"


def test_update_never_blanks_stored_values():
    svc = ConsultationSyncService.__new__(ConsultationSyncService)
    svc._db = SimpleNamespace(add=lambda obj: None)
    existing = SimpleNamespace(
        id="x", status="closed", title="T", short_title="S", description="Full text",
        dg_responsible="CLIMA", policy_areas=["Climate"], start_date=date(2026, 1, 1),
        end_date=date(2026, 2, 1), feedback_count=412, portal_url="u", feedback_url="f",
        consultation_type="call_for_evidence", relevance_score=0, scraped_at=None,
        last_updated=None)
    item = SimpleNamespace(
        status="closed", title="T", short_title=None, description=None,
        dg_responsible=None, policy_areas=[], start_date=None, end_date=None,
        feedback_count=0, portal_url="u", feedback_url=None,
        consultation_type="initiative", scraped_at=None)
    svc._calculate_relevance = lambda i: 0
    svc._update_consultation(existing, item)
    assert existing.description == "Full text"
    assert existing.start_date == date(2026, 1, 1) and existing.end_date == date(2026, 2, 1)
    assert existing.feedback_count == 412
    assert existing.dg_responsible == "CLIMA" and existing.policy_areas == ["Climate"]
    assert existing.consultation_type == "call_for_evidence"


def _svc():
    svc = ConsultationSyncService.__new__(ConsultationSyncService)
    svc._db = SimpleNamespace(add=lambda obj: None)
    svc._calculate_relevance = lambda i: 0
    return svc


def _row(status):
    return SimpleNamespace(
        id="x", status=status, title="T", short_title=None, description=None,
        dg_responsible=None, policy_areas=None, start_date=None, end_date=None,
        feedback_count=0, portal_url=None, feedback_url=None,
        consultation_type="initiative", relevance_score=0, scraped_at=None, last_updated=None)


def _item(status):
    return SimpleNamespace(
        status=status, title="T", short_title=None, description=None, dg_responsible=None,
        policy_areas=None, start_date=None, end_date=None, feedback_count=0,
        portal_url=None, feedback_url=None, consultation_type="initiative", scraped_at=None)


@pytest.mark.parametrize("scraped", ["upcoming", "closed", "outcome_published"])
def test_existing_status_left_to_the_sweep_unless_open(scraped):
    from models.public_consultation import ConsultationStatusEnum as E
    row = _row(E.CLOSED)
    changed = _svc()._update_consultation(row, _item(scraped))
    assert row.status == E.CLOSED and changed is False


def test_open_now_is_still_recorded():
    from models.public_consultation import ConsultationStatusEnum as E
    row = _row(E.UPCOMING)
    changed = _svc()._update_consultation(row, _item("open"))
    assert row.status == E.OPEN and changed is True

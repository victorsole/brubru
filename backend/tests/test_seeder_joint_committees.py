"""Joint-committee files must be offered to every responsible committee's users.

The Industrial Accelerator Act 2026/0068(COD) is a joint INTA/ITRE/IMCO file whose
lead_committee column holds INTA only; before 25 Sep 2026 an IMCO user's
"sync from interests" never offered it.

Runs the REAL seeder against the real database. Nothing is written: db.add is
captured and db.commit is a no-op, and the user is a fresh id with no tracks.
"""
import uuid
from types import SimpleNamespace

import pytest

from core.database import SessionLocal
from models.legislative_train import LegislativeCarriage
import services.tracking.tracked_files_seeder as seeder

IAA = "2026/0068(COD)"


def _seeded_refs(monkeypatch, committees):
    monkeypatch.setattr(seeder, "committees_for_interests", lambda i: set(committees))
    monkeypatch.setattr(seeder, "policy_areas_for_interests", lambda i: set())
    monkeypatch.setattr(seeder, "keywords_for_interests", lambda i: set())
    db = SessionLocal()
    added = []
    db.add = added.append
    db.commit = lambda: None
    try:
        user = SimpleNamespace(id=uuid.uuid4(), policy_interests_list=["x"])
        seeder.sync_tracked_files_from_interests(db, user, limit=100000)
        ids = [t.carriage_id for t in added]
        return {r for (r,) in db.query(LegislativeCarriage.oeil_procedure_ref)
                .filter(LegislativeCarriage.id.in_(ids)).all()}
    finally:
        db.rollback()
        db.close()


@pytest.mark.parametrize("committee", ["IMCO", "ITRE", "INTA"])
def test_iaa_offered_to_each_responsible_committee(monkeypatch, committee):
    assert IAA in _seeded_refs(monkeypatch, [committee])


def test_iaa_not_offered_to_an_opinion_committee(monkeypatch):
    # ENVI gives an opinion on the IAA; it is not responsible for it.
    assert IAA not in _seeded_refs(monkeypatch, ["ENVI"])

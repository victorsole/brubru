"""Offline guard for the Phase 3 snapshot join fix.

The original build_snapshot joined num_amendments on the 68-row `amendments` table and
num_documents on `commission_documents.legislative_carriage_id` — both UNPOPULATED, so the
counts were silently 0 across the whole estate. The fix routes amendments to mep_amendments
(by procedure_reference) and documents to commission_documents.celex. These string-source
assertions lock the fix so it cannot silently regress (no DB needed), mirroring the extract
engine's test_config_selectors_no_drift.
"""
import pathlib

_SRC = (pathlib.Path(__file__).resolve().parents[1].parent
        / "services" / "snapshots" / "snapshot_builder.py").read_text()


def test_amendments_join_uses_mep_amendments_by_ref():
    assert "MEPAmendment.procedure_reference == ref" in _SRC
    # the dead 68-row table / FK must NOT be the amendments source again
    assert "Amendment.carriage_id" not in _SRC


def test_documents_join_uses_celex_not_dead_fk():
    assert "CommissionDocument.celex.in_(celex)" in _SRC
    assert "CommissionDocument.legislative_carriage_id" not in _SRC


def test_committee_work_keeps_working_fk():
    assert "CommitteeWorkItem.legislative_carriage_id == cid" in _SRC


def test_ref_dependent_counts_guarded_by_if_ref():
    # amendments/lobby/eprs must sit under `if ref:` so an empty/None ref can't match junk
    body = _SRC.split("if ref:", 1)
    assert len(body) == 2, "expected an `if ref:` guard around ref-linked counts"
    after = body[1]
    for tok in ("MEPAmendment.procedure_reference", "MepLobbyMeeting.procedure_ref",
                "EPRSPublication.related_procedures"):
        assert tok in after, f"{tok} must be inside the if-ref guard"


def test_days_in_status_derived_from_events():
    # the unpopulated carriage column must be backstopped by the OEIL-event derivation
    assert "_last_event_date" in _SRC

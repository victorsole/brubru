"""The consultation-to-file link works for every file, not only EU Inc.

Real database, read-only: after the linking job has run, more than one live file
is linked, and the linker's own function finds them.
"""
import importlib.util
from pathlib import Path

from core.database import SessionLocal

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "link_consultations_to_files", HERE.parent / "scripts" / "link_consultations_to_files.py")
lk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lk)


def test_many_files_are_linked_not_just_eu_inc():
    db = SessionLocal()
    try:
        linked, _unsynced = lk._unsynced_linked_initiatives(db)
        files = set().union(*linked.values())
        assert len(files) >= 20
        assert len(linked) >= 20
        assert "2026/0074(COD)" in files          # EU Inc. is one of them, not the only one
    finally:
        db.close()


def test_several_file_maps_show_their_respondents():
    from sqlalchemy import text
    from models.legislative_train import LegislativeCarriage
    from services.strategy.stakeholder_map import build_file_graph
    db = SessionLocal()
    try:
        linked, _ = lk._unsynced_linked_initiatives(db)
        have = {r[0] for r in db.execute(text("SELECT DISTINCT initiative_id FROM consultation_feedback"))}
        procs = sorted({p for i, ps in linked.items() if i in have for p in ps} - {"2026/0074(COD)"})
        assert len(procs) >= 5
        shown = 0
        for p in procs[:5]:
            c = db.query(LegislativeCarriage).filter_by(oeil_procedure_ref=p).first()
            g = build_file_graph(db, c, [], deep=True)
            shown += any((n.get("meta") or {}).get("kind") == "consultation" for n in g.nodes.values())
        assert shown == 5
    finally:
        db.close()

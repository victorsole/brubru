"""The carriage archive UPDATE must cast the enum and give each row its OWN status.

12 Oct 2026: the first day two carriages qualified, `lower(current_status)` raised
"function lower(carriagestatusenum) does not exist" and the whole sweep exited 1. The same
statement used a LIMIT 1 subquery over ANY(:ids), so every row of a batch would have been
stamped with the first row's status. No database is touched: the SQL text is captured.
"""
import importlib.util
import pathlib
from unittest.mock import MagicMock

_PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "auto_archive_old_items.py"


def _load():
    spec = importlib.util.spec_from_file_location("auto_archive_old_items", _PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_carriage_update_casts_the_enum_and_is_per_row():
    mod = _load()
    db = MagicMock()
    rows = [("t1", "u1", "Title one", "ADOPTED", "2026-01-01"), ("t2", "u2", "Title two", "WITHDRAWN", "2026-01-02")]
    db.execute.return_value.fetchall.return_value = rows
    assert mod.archive_carriages(db, dry_run=False) == 2
    updates = [str(c.args[0]) for c in db.execute.call_args_list if "UPDATE user_carriage_tracks" in str(c.args[0])]
    assert len(updates) == 1
    sql = updates[0]
    assert "current_status::text" in sql, "the enum must be cast before lower()"
    assert "user_carriage_tracks.carriage_id" in sql, "the status must be read per row"
    assert "LIMIT 1" not in sql, "a LIMIT 1 subquery stamps one row's status on all rows"

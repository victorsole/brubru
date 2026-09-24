"""The EP voting tables had been empty since migration 014 (found 24 September 2026).

Not because HowTheyVote stopped publishing, and not because the importer was broken in
any way anyone would notice. Groups are the FIRST step of `scripts/import_howtheyvote.py`,
and HowTheyVote carries a legacy group whose short_label is its own full name --
"Confederal Group of the European United Left - Nordic Green Left", 63 characters --
against a VARCHAR(20). One row raised StringDataRightTruncation, the transaction rolled
back, and members, group memberships and member votes never ran. Nothing downstream ever
reported a problem: the Predictions cohesion analyser inner joins member votes to members,
so with both tables empty it returned None, which reads as "no cohesion data for this
group" rather than "this feature has never had any data at all".

The second defect was quieter. The importer mapped `ID` to `PFE` with the comment "ID
became PfE". Identity and Democracy was dissolved in July 2024 and Patriots for Europe
formed the same month with an overlapping but different membership: two groups, two
voting records. Because the groups upsert matches on the MAPPED code, the ID row updated
the PfE row, so Patriots for Europe would have carried the label "Identity and Democracy",
and all 85 ID memberships would have been counted as PfE, taking it from 100 to 185.

Needs the database.
"""
from __future__ import annotations

import pathlib
import sys

import pytest
from sqlalchemy import text

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from core.database import SessionLocal  # noqa: E402
from services.data_import.howtheyvote_importer import GROUP_CODE_MAP  # noqa: E402


@pytest.fixture(scope="module")
def db():
    s = SessionLocal()
    yield s
    s.close()


def test_a_dissolved_group_keeps_its_own_code():
    """ID is not PfE. A successor group is not the same group."""
    assert GROUP_CODE_MAP.get("ID") == "ID", "Identity and Democracy is being merged into another group"
    assert GROUP_CODE_MAP.get("PFE") == "PFE"


def test_the_two_groups_are_two_rows_with_their_own_names(db):
    rows = dict(db.execute(text(
        "SELECT code, label FROM ep_political_groups WHERE code IN ('ID','PFE')")).fetchall())
    assert set(rows) == {"ID", "PFE"}, f"expected both groups, got {sorted(rows)}"
    assert "Identity" in rows["ID"], rows["ID"]
    assert "Patriots" in rows["PFE"], rows["PFE"]


def test_the_group_label_columns_fit_the_longest_value_the_source_publishes(db):
    """63 characters is what HowTheyVote actually publishes; 20 is what the column held."""
    widths = dict(db.execute(text(
        "SELECT column_name, character_maximum_length FROM information_schema.columns "
        "WHERE table_name = 'ep_political_groups' "
        "AND column_name IN ('label','short_label')")).fetchall())
    for col, width in widths.items():
        assert width >= 100, f"{col} is VARCHAR({width}): the 63-char legacy group name needs room"


@pytest.mark.parametrize("table,minimum", [
    ("ep_political_groups", 8),      # 8 groups sit in the current Parliament
    ("ep_members", 700),             # 720 seats; HowTheyVote also carries members who left
    ("ep_group_memberships", 700),
])
def test_the_table_is_not_empty(db, table, minimum):
    """An empty table here is invisible downstream: the joins simply return nothing."""
    n = db.execute(text(f"SELECT count(*) FROM {table}")).scalar()
    assert n >= minimum, f"{table} holds {n} rows: the HowTheyVote import has not run"


def test_every_membership_points_at_a_group_that_exists(db):
    """A membership whose group_code has no row joins to nothing and vanishes from any
    per-group count, without an error."""
    orphans = db.execute(text(
        "SELECT count(*) FROM ep_group_memberships m "
        "WHERE NOT EXISTS (SELECT 1 FROM ep_political_groups g WHERE g.code = m.group_code)")).scalar()
    assert orphans == 0, f"{orphans} membership(s) name a group that is not in the table"


def test_the_import_is_scheduled():
    """The tables were empty for as long as they existed partly because nothing ran the
    importer: a working script in no cron ages silently (the same week's finding for the
    Brussels lobby crawler, 108 days stale)."""
    cron = (BACKEND / "api" / "cron.py").read_text(encoding="utf-8")
    assert "scripts/import_howtheyvote.py" in cron, "nothing runs the HowTheyVote import"
    # The name appears twice (the results key and the job name); take the call itself.
    block = cron.split('"howtheyvote_members"')[-1][:300]
    assert "--members-only" in block, (
        "the scheduled run must stay members-only: member_votes is ~16M rows")

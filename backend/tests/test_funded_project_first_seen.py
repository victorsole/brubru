"""A funded project's creation_date is when Brubru first saw it, not its last read (2 Nov 2026, register O140:
14,039 of 115,122 were served as created after their last change)."""
import re
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parents[1]


def test_no_loader_writes_first_seen_on_a_re_read():
    for name in ("ingest_cordis_projects.py", "ingest_ft_projects_nonh2020.py", "refresh_project_status.py",
                 "repair_ft_project_coordinators.py", "derive_ft_participants.py"):
        assert "first_seen" not in (BACKEND / "scripts" / name).read_text(encoding="utf-8"), name


def test_the_item_serves_first_seen_not_the_last_read():
    from tests.test_funded_projects_programme_and_source_word import _row
    from api.v1.funding_tenders_collections import _project_to_item
    first, read, changed = datetime(2026, 6, 15, 8, 33), datetime(2026, 11, 1, 5, 32), datetime(2026, 10, 26, 10, 40)
    item = _project_to_item(_row(first_seen=first, scraped_at=read, last_updated=changed))
    assert item.creation_date == first and item.updated_date == changed


def test_the_consolidated_lists_read_it_too():
    from api.v2.funding import awards, partners
    assert "ft_funded_projects.first_seen AT TIME ZONE 'UTC' AS creation_date" in awards._PROJECT_SIDE
    assert "scraped_at" not in awards._PROJECT_SIDE
    source = (BACKEND / "api" / "v2" / "funding" / "partners.py").read_text(encoding="utf-8")
    assert "scraped_at" not in source and source.count("first_seen") >= 3
    assert partners


def test_the_migration_adds_the_column_with_no_row_stamped_by_it():
    sql = (BACKEND / "migrations" / "324_ft_funded_projects_first_seen.sql").read_text(encoding="utf-8")
    # The default is set apart from the ADD: ADD ... DEFAULT would stamp every existing row with today.
    assert re.search(r"ADD COLUMN IF NOT EXISTS first_seen TIMESTAMP;", sql) and "SET DEFAULT now()" in sql


def test_the_fill_keeps_the_change_signal_and_takes_the_earliest_stamp():
    source = (BACKEND / "scripts" / "fill_ft_funded_projects_first_seen.py").read_text(encoding="utf-8")
    assert "set_config('brubru.keep_change_signal', txid_current()::text, true)" in source
    assert "LEAST(scraped_at, last_updated)" in source

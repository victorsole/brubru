"""Endpoints over institutional_publications filter on the change date their items carry.

14 October 2026: /council/council-documents answered ?updated_from= off fetched_at, the
ingestion anchor every upsert moves, while each item carried updated_date = null (672 of
672). A client filtered on a value it could not see, and a re-run that changed nothing
moved every row into "changed since yesterday". /publications and /press-releases did the
same. Migration 290 gave the table updated_at, kept by the touch-if-changed trigger."""
from __future__ import annotations

import pathlib
import re
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from api.v1 import council_documents as cd  # noqa: E402
from models.institutional_publication import InstitutionalPublication  # noqa: E402

CREATED = datetime(2026, 9, 28, 7, 27, tzinfo=timezone.utc)
FETCHED = datetime(2026, 10, 14, 7, 8, tzinfo=timezone.utc)
CHANGED = datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc)


def test_the_model_has_the_change_signal():
    assert "updated_at" in InstitutionalPublication.__table__.columns
    assert InstitutionalPublication.__table__.columns["updated_at"].nullable is False


def test_a_council_item_carries_its_creation_and_its_last_change():
    row = SimpleNamespace(id="x", category="document", title="t", summary=None, url="u", language="en",
                          published_date=CREATED, policy_areas=[], tags=[], html_content="text " * 100,
                          fetched_at=FETCHED, created_at=CREATED, updated_at=CHANGED)
    item = cd._pub_to_item(row)
    assert item.creation_date == CREATED          # not fetched_at, which moves every run
    assert item.updated_date == CHANGED


def test_no_endpoint_filters_a_window_on_fetched_at():
    offenders = []
    for path in (BACKEND / "api").rglob("*.py"):
        src = path.read_text(encoding="utf-8")
        for m in re.finditer(r"InstitutionalPublication\.fetched_at\s*[<>]=\s*updated_(from|to)", src):
            offenders.append(f"{path.relative_to(BACKEND)}: {m.group(0)}")
    assert not offenders, offenders


def test_the_three_endpoints_filter_on_updated_at():
    for rel in ("api/v1/council_documents.py", "api/v1/publications.py", "api/v1/ep_entities.py"):
        src = (BACKEND / rel).read_text(encoding="utf-8")
        assert re.search(r"InstitutionalPublication\.updated_at\s*>=\s*updated_from", src), rel


def test_the_migration_guards_the_column_with_the_shared_trigger():
    sql = (BACKEND / "migrations" / "290_institutional_publications_change_signal.sql").read_text(encoding="utf-8")
    assert "brubru_touch_if_changed('updated_at', 'fetched_at', 'created_at')" in sql
    assert "SET updated_at = fetched_at" in sql

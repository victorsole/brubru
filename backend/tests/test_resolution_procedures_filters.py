"""/resolution-procedures: the filters added or tightened on 12 Oct 2026.

A window ending 28 Sep answered `total: 0` with nothing to say why; an inverted window and
an unknown `order` answered an empty page; an unknown `resolution_type` reached PostgreSQL
and answered 500. `scripts/audit_resolution_procedures_endpoint.py` tests the route against
the database (95 checks); these are the parts that need no database."""
import asyncio
import pathlib
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from api.v1 import resolutions as r

BACKEND = pathlib.Path(__file__).resolve().parents[1]
ARGS = dict(request=MagicMock(), q=None, resolution_type=None, lead_committee=None, rapporteur=None,
            procedure_ref=None, has_commission_followup=None, status=None, published_from=None,
            published_to=None, published_end=None, updated_from=None, updated_to=None, updated_end=None,
            created_from=None, created_to=None, order=None, limit=50, page=1, user=MagicMock(), db=MagicMock())


def _refused(**kw) -> int:
    with pytest.raises(HTTPException) as e:
        asyncio.run(r.list_resolutions(**{**ARGS, **kw}))
    return e.value.status_code


def test_an_inverted_window_is_refused_not_answered_with_an_empty_page():
    lo, hi = datetime(2026, 10, 9, tzinfo=timezone.utc), datetime(2026, 10, 1, tzinfo=timezone.utc)
    assert _refused(updated_from=lo, updated_to=hi) == 422
    assert _refused(created_from=lo, created_to=hi) == 422


def test_an_unknown_order_or_type_or_status_is_refused():
    assert _refused(order="newest") == 422
    assert _refused(resolution_type="COD") == 422      # used to reach the enum column: HTTP 500
    assert _refused(status="voted") == 422


def test_the_v2_route_passes_the_new_filters_through():
    src = (BACKEND / "api" / "v2" / "parliament" / "resolutions.py").read_text()
    assert "created_from=created_from, created_to=created_to, order=order" in src


def test_the_description_documents_them_and_the_empty_window():
    d = r.router.routes[0].description
    for needle in ("`created_from`, `created_to`", "`order`", "updated_asc", "can be empty even though rows exist"):
        assert needle in d, needle


def test_the_coverage_note_names_the_version_it_answers_and_explains_an_empty_window():
    src = (BACKEND / "api" / "v1" / "resolutions.py").read_text()
    assert '"/api/v2/parliament/plenary-adopted-texts"' in src and "request.url.path.startswith(\"/api/v2\")" in src
    assert "EMPTY WINDOW" in src


def test_the_item_schema_declares_self_so_the_item_route_can_carry_it():
    assert "self" in r.ResolutionItem.model_fields

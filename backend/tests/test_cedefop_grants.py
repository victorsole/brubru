"""Cedefop's calls for proposals are grants, served at /funding/cedefop-grants (16 Oct 2026).

API audit, step 2: 89 procedures whose page says "Procurement type: Call for proposals"
(ReferNet partnerships, DG EAC calls) were stored as tenders and served under
/cedefop-tenders. The writer now types them "grant", the route exists with its documents
sub-routes, and the sync map runs the grant ingestor so the type is written at all.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import APIRouter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.scrapers import agency_procurement as ap  # noqa: E402

NOW = datetime(2026, 10, 16, tzinfo=timezone.utc)


@pytest.mark.parametrize("ptype, reference, title, expected", [
    ("Call for proposals", "GP/DVQ/ReferNet_FPA/001/26", "ReferNet Call for proposals", "grant"),
    ("Call for tenders", "AO/DRS/SAN/Dark Fibre/002/2016", "Dark Fiber", "tender"),
    ("Call for expression of interest", "CEDEFOP/2026/CEI/0001", "List of experts", "eoi_call"),
    ("Call for proposals", "", "DG EAC 37/06 - European network", "grant"),   # page type wins
    ("", "GP/D/ReferNet2/002/06", "Refernet", "grant"),                       # no page: the reference
    ("", "Cedefop No GP/D/ReferNet2/002/06", "Refernet", "grant"),
    ("", "AO/RES/JK/Travel/011/14", "Travel Agency Services", "tender"),
    ("", "", "Call for proposals on Higher Education Reforms", "grant"),      # no page, no ref: title
    ("", "CEDEFOP/2026/CEI/0001", "x", "eoi_call"),
])
def test_type_from_page_then_reference_then_title(ptype, reference, title, expected):
    assert ap._cedefop_type(ptype, reference, title) == expected


def test_item_from_a_call_for_proposals_page_is_a_grant():
    row = {"title": "ReferNet Call for proposals", "url": "https://x/refernet", "reference": "GP/001/26",
           "closing": datetime(2026, 4, 1, tzinfo=timezone.utc), "status_raw": "Completed"}
    detail = {"Procurement type": "Call for proposals", "Official Publication Date": "20/02/2026",
              "Closing date": "01/04/2026", "description": [], "documents": []}
    item = ap._cedefop_item(row, detail, NOW)
    assert item.item_type == "grant" and item.extras["type_from_page"] is True


def test_grant_ingestor_exists_and_the_sync_map_runs_it():
    assert callable(ap.ingest_cedefop_grants)
    import scripts.sync_economy as se
    assert se.INGESTORS[("cedefop", "grant")] is ap.ingest_cedefop_grants
    assert se.INGESTORS[("cedefop", "tender")] is ap.ingest_cedefop_tenders


def test_cedefop_grants_route_is_registered_with_its_documents():
    from api.v2.funding import agency_procurement as routes
    paths = {r.path for r in routes.router.routes}
    assert {"/cedefop-grants", "/cedefop-grants/{item_id}", "/cedefop-grants/{item_id}/documents",
            "/cedefop-grants/{item_id}/documents/{document_id}"} <= paths
    assert "/cedefop-tenders" in paths and "/cedefop-calls" in paths

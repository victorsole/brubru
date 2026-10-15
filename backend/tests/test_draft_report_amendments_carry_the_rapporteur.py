"""A draft report's amendments carry its rapporteur(s) as authors (15 Oct 2026).

31,123 of 64,198 amendments on /api/v2/parliament/amendments had no author: all from
draft reports (PR), which tag no author per amendment because every amendment is the
rapporteur's. The cover names them; the parser had a rapporteur_name argument it never used."""
from __future__ import annotations

import inspect

import pytest

from services.parsers.ep_amendment_parser import rapporteurs_from_text
from services.scrapers import ep_amendment_sync_service as sync


@pytest.mark.parametrize("cover,names", [
    ("Committee on the Environment\nRapporteur: Manuela Ripa TITLE \\* MERGEFORMAT PR_COD_1amCom",
     ["Manuela Ripa"]),
    ("Rapporteurs: Tonino Picula, Karlo Ressler\n", ["Tonino Picula", "Karlo Ressler"]),
    ("Rapporteurs: Barbara Thaler, Dominique Riquet,\n", ["Barbara Thaler", "Dominique Riquet"]),
    ("Rapporteur: Victor Negrescu (Section III – Commission)\n", ["Victor Negrescu"]),
    ("Co-rapporteurs: Anna Cavazzini and Christophe Grudler\n", ["Anna Cavazzini", "Christophe Grudler"]),
    ("Committee on Budgets\nno names here", []),
])
def test_the_cover_names_the_rapporteurs(cover, names):
    assert rapporteurs_from_text(cover) == names


def test_the_sync_gives_unsigned_draft_report_amendments_the_rapporteur():
    src = inspect.getsource(sync.EPAmendmentSyncService)
    assert "if doc_type == 'PR':" in src and "pa.authors = list(rapporteurs)" in src


def test_an_empty_author_list_never_erases_a_held_one():
    src = inspect.getsource(sync.EPAmendmentSyncService._upsert_amendment)
    assert "**({'author_names': pa.authors} if pa.authors else {})" in src

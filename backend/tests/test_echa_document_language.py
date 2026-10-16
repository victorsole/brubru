"""An ECHA file's language is read from its name's suffix (16 Oct 2026).

API audit, step 2: all 625 ECHA files were served with language empty while 589 names
end in "_en.pdf" and the like.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.scrapers import agency_procurement as ap  # noqa: E402


def _block(name: str) -> str:
    return (f'<a href="https://echa.europa.eu/documents/10162/2321927/{name}/740927eb-9d69-42c7-9a66-ec6901b5163d'
            f'?t=1">Annex</a>')


@pytest.mark.parametrize("name, lang", [
    ("ojeu_2012_checklist_en.doc", "en"),
    ("contract_award_notice_echa_2009_40_lot_1_en.pdf", "en"),
    ("annex_5_fr.docx", "fr"),
    ("echa_2013_03_pricing_sheet_annex_5_1_4.xlsx", None),      # no suffix
    ("annex_5-11_manpower_v2.doc", None),                        # "v2" is not a language
    ("report_q1.pdf", None),
])
def test_language_from_the_file_name_suffix(name, lang):
    docs = ap._echa_documents(_block(name))
    assert len(docs) == 1 and docs[0]["file_name"] == name and docs[0]["language"] == lang

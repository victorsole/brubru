"""A secondary act's pdf_url is a PDF a browser opens (15 Oct 2026).

1,684 published delegated acts carried publications.europa.eu/resource/celex/<CELEX> as
their PDF and 345 carried none. That address is Cellar's content negotiation for machines:
a browser, or a request asking for a PDF, gets 404. GovClipping's delegated-acts requests
served it on every published act."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from api.v1.w4_endpoints import _secondary_act_to_item
from models.w4_entities import SecondaryAct


def _act(**kw):
    a = SecondaryAct(id=uuid.uuid4(), act_type="delegated", reference="C(2025)8506", title="t",
                     status="published", celex="32026R0880", publication_date=date(2026, 4, 20),
                     source_url="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32026R0880",
                     pdf_url="https://publications.europa.eu/resource/celex/32026R0880",
                     text_body="x" * 600, policy_areas=[], ep_scrutiny={}, council_scrutiny={},
                     first_seen=datetime(2026, 1, 1), last_updated=datetime(2026, 10, 15))
    for k, v in kw.items():
        setattr(a, k, v)
    return a


def test_an_act_in_the_official_journal_gets_eur_lex_pdf():
    item = _secondary_act_to_item(_act())
    assert item.pdf_url == "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32026R0880"
    # ...also when none was stored (345 acts on 15 Oct 2026).
    assert _secondary_act_to_item(_act(pdf_url=None)).pdf_url == item.pdf_url


def test_an_adopted_act_keeps_the_commission_registers_file():
    reg = "https://ec.europa.eu/transparency/documents-register/api/files/C%282026%295161?ersIds=090166e53248ffb6"
    item = _secondary_act_to_item(_act(celex=None, status="adopted", pdf_url=reg, publication_date=None))
    assert item.pdf_url == reg


def test_the_cellar_machine_address_is_never_served():
    item = _secondary_act_to_item(_act(celex=None, status="adopted", publication_date=None))
    assert item.pdf_url is None

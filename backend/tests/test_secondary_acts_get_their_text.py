"""Delegated and implementing acts get the text they have, every day (14 Oct 2026).

No scheduled job fetched these acts' text (the last bodies were written by hand on 1-2
Oct), and 88 delegated acts adopted but not in the Official Journal had none: the
endpoint served a "body" composed from their metadata. The Commission's document
register serves the adopted text; the Official Journal's replaces it on publication."""
from __future__ import annotations

import json
import pathlib

import pytest

from scripts import sync_secondary_act_bodies as job

BACKEND = pathlib.Path(__file__).resolve().parents[1]


def test_the_c_number_is_the_reference_or_one_recorded_by_a_merge():
    assert job.c_number("C(2026)5161", None) == "C(2026)5161"
    merged = [{"reference": "32025R0420"}, {"reference": "C(2024)8742", "source": "x"}]
    assert job.c_number("32025R0420", merged) == "C(2024)8742"
    assert job.c_number("32025R0420", json.dumps(merged)) == "C(2024)8742"
    assert job.c_number("PLANNED:abc", None) is None


def test_english_files_main_document_first_then_annexes_once_each():
    rec = {"attachments": [
        {"main": False, "sequence": 1, "linguisticVersions": {"en": {"ersId": "annex"}}},
        {"main": True, "sequence": 0, "linguisticVersions": {"en": {"ersId": "main"}, "fr": {"ersId": "fr"}}},
        {"main": False, "sequence": 2, "linguisticVersions": {"en": {"ersId": None}}},
        {"main": False, "sequence": 3, "linguisticVersions": {"en": {"ersId": "annex"}}},
    ]}
    assert job.english_files(rec) == ["main", "annex"]


@pytest.fixture
def register(monkeypatch):
    calls = []

    def fake_get(url, timeout=60):
        calls.append(url)
        if "/api/search/" in url:
            return json.dumps(fake_get.record).encode()
        return fake_get.files[url.split("ersIds=")[1]]
    fake_get.record, fake_get.files = {}, {}
    monkeypatch.setattr(job, "_get", fake_get)
    monkeypatch.setattr(job, "pdf_text", lambda data: data.decode())
    monkeypatch.setattr(job.time, "sleep", lambda s: None)
    fake_get.calls = calls
    return fake_get


def test_the_adopted_document_is_main_text_then_annexes(register):
    register.record = [{"attachments": [
        {"main": True, "linguisticVersions": {"en": {"ersId": "m"}}},
        {"main": False, "sequence": 1, "linguisticVersions": {"en": {"ersId": "a"}}}]}]
    register.files = {"m": b"EUROPEAN COMMISSION C(2026) 5161 final COMMISSION DELEGATED REGULATION " * 30,
                      "a": b"ANNEX " * 20}
    txt, html = job.fetch_commission_document("C(2026)5161")
    assert txt.startswith("EUROPEAN COMMISSION") and txt.rstrip().endswith("ANNEX") and html is None
    assert register.calls[0].endswith("/api/search/C%282026%295161?lang=en")


def test_no_text_is_stored_from_nothing(register):
    register.record = []
    assert job.fetch_commission_document("C(2026)1") == "not_in_register"
    register.record = [{"attachments": [{"main": True, "linguisticVersions": {"en": {"ersId": None}}}]}]
    assert job.fetch_commission_document("C(2026)1") == "no_english_file"
    register.record = [{"attachments": [{"main": True, "linguisticVersions": {"en": {"ersId": "m"}}}]}]
    register.files = {"m": b"Error"}
    assert job.fetch_commission_document("C(2026)1").startswith("too_short")


def test_writes_touch_only_what_was_checked_and_skip_acts_with_no_document():
    sql = str(job.STORE)
    assert "coalesce(text_body, '') = '' OR body_source = 'commission_document'" in sql
    assert "planned" not in job.ADOPTED_STAGES and "cancelled" not in job.ADOPTED_STAGES
    # The Official Journal text replaces a Commission document once the act has a CELEX.
    assert "body_source = 'commission_document'" in str(job.DUE_OJ)


def test_it_is_scheduled_and_reads_the_environment():
    reg = (BACKEND / "services" / "sync" / "source_registry.py").read_text(encoding="utf-8")
    assert '"scripts/sync_secondary_act_bodies.py"' in reg
    src = (BACKEND / "scripts" / "sync_secondary_act_bodies.py").read_text(encoding="utf-8")
    assert 'os.environ.get("DATABASE_URL"' in src


def test_labelling_existing_texts_does_not_move_the_change_signal():
    sql = (BACKEND / "migrations" / "292_secondary_acts_body_source.sql").read_text(encoding="utf-8")
    assert sql.index("DISABLE TRIGGER") < sql.index("UPDATE secondary_acts") < sql.index("ENABLE TRIGGER")


def test_the_api_says_where_the_text_came_from():
    from api.v1 import w4_endpoints as api
    assert "body_source" in api.SecondaryActItem.model_fields
    assert 'body_source=getattr(r, "body_source", None) if r.text_body else None' in \
        (BACKEND / "api" / "v1" / "w4_endpoints.py").read_text(encoding="utf-8")


def test_a_document_that_does_not_print_its_own_number_is_refused(register):
    register.record = [{"attachments": [{"main": True, "linguisticVersions": {"en": {"ersId": "m"}}}]}]
    register.files = {"m": b"EUROPEAN COMMISSION C(2026) 5162 final some other act " * 30}
    assert job.fetch_commission_document("C(2026)5161") == "wrong_document"
    assert job.names_itself("Brussels, 9.10.2026 C(2026) 7021 final", "C(2026)7021")
    assert job.names_itself("C(2015)0912 final", "C(2015)912")
    assert not job.names_itself("C(2026) 70210 final", "C(2026)7021")


def test_a_nul_in_an_extracted_text_is_removed():
    assert job.clean("COMMISSION\x00 DELEGATED\n\nREGULATION") == "COMMISSION DELEGATED REGULATION"

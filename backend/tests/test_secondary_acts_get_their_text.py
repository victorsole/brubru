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
    txt, pdf = job.fetch_commission_document("C(2026)5161")
    assert txt.startswith("EUROPEAN COMMISSION") and txt.rstrip().endswith("ANNEX")
    assert register.calls[0].endswith("/api/search/C%282026%295161?lang=en")
    # The link points at the main document served; main text and annexes are one running
    # text, so the API can split it at Articles and Annexes.
    assert pdf.endswith("/api/files/C%282026%295161?ersIds=m") and "\n" not in txt


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


def test_it_is_scheduled_on_a_tier_the_cron_runs_and_reads_the_environment():
    from services.sync.source_registry import MEUB_SOURCES
    spec = next(s for s in MEUB_SOURCES if s.key == "secondary_act_bodies")
    assert spec.tier == "warm" and spec.script == "scripts/sync_secondary_act_bodies.py"
    keys = [s.key for s in MEUB_SOURCES]
    assert keys.index("secondary_act_bodies") == keys.index("regdel_acts") + 1
    src = (BACKEND / "scripts" / "sync_secondary_act_bodies.py").read_text(encoding="utf-8")
    assert 'os.environ.get("DATABASE_URL"' in src


def test_every_scheduled_source_is_on_a_tier_the_cron_runs():
    """A "daily" spec ran nowhere: /api/cron/sync/tier accepts fast and warm only, so
    secondary_act_bodies was first registered where it would never have run (14 Oct
    2026). consultation_stances is the one left there; it has never run (reported)."""
    import re as _re
    from services.sync.source_registry import MEUB_SOURCES
    router = (BACKEND / "api" / "cron.py").read_text(encoding="utf-8")
    accepted = set(_re.search(r'if tier not in \(([^)]*)\)', router).group(1).replace('"', "").replace("'", "")
                   .replace(" ", "").split(","))
    assert accepted == {"fast", "warm"}
    stranded = sorted(s.key for s in MEUB_SOURCES if s.tier not in accepted)
    assert stranded == ["consultation_stances"], stranded


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
    assert job.names_itself("C (2026) 7021 final", "C(2026)7021")            # a PDF artefact
    assert not job.names_itself("C(2026) 70210 final", "C(2026)7021")
    # Cited further down, not on the cover; or quoted by a draft: neither is the act.
    assert not job.names_itself("C(2021) 9342 final amending Decision C(2021) 1051", "C(2021)1051")
    assert not job.names_itself("Brussels, XXX draft COMMISSION REGULATION C(2021) 8860 final", "C(2021)8860")


def test_a_nul_in_an_extracted_text_is_removed():
    assert job.clean("COMMISSION\x00 DELEGATED\n\nREGULATION") == "COMMISSION DELEGATED REGULATION"


def test_transient_faults_are_not_settled_answers():
    for fault in ("register_http_403", "register_http_429", "file_http_503", "register_URLError",
                  "file_IncompleteRead", "http_500", "TimeoutError"):
        assert fault not in job.SETTLED
    for answer in ("not_in_register", "no_english_file", "wrong_document", "http_404"):
        assert answer in job.SETTLED


def test_dates_are_read_from_the_cover_and_the_journal_header():
    from datetime import date
    assert job.dated(job._COVER_DATE, "EUROPEAN COMMISSION Brussels, 9.10.2026 C(2026) 7021 final") == date(2026, 10, 9)
    assert job.dated(job._OJ_HEADER, "Official Journal of the European Union EN L series 2024/1261 8.5.2024 COMM") \
        == date(2024, 5, 8)
    assert job.dated(job._OJ_HEADER, "no header here") is None


def test_an_act_held_without_a_celex_takes_cellars_only_if_no_row_holds_it():
    sql = str(job.ASSIGN)
    assert "coalesce(celex, '') = ''" in sql and "NOT EXISTS (SELECT 1 FROM secondary_acts o WHERE o.celex = :celex)" in sql
    assert "cdm:resource_legal_manuscript_ref" in (BACKEND / "scripts" / "sync_secondary_act_bodies.py").read_text()


def test_page_furniture_is_dropped():
    class P:
        def __init__(self, t): self.t = t
        def extract_text(self): return self.t
    import types, sys
    fake = types.SimpleNamespace(PdfReader=lambda b: types.SimpleNamespace(pages=[P("EN EN EUROPEAN COMMISSION"), P("text EN 3 EN more")]))
    sys.modules["pypdf"], old = fake, sys.modules.get("pypdf")
    try:
        assert job.pdf_text(b"x") == "EUROPEAN COMMISSION text more"
    finally:
        if old is not None:
            sys.modules["pypdf"] = old


def test_one_slow_year_at_cellar_skips_that_year_not_the_lookup(monkeypatch):
    """Cellar timed out on two years' queries on 14 Oct 2026; the others still answered."""
    from types import SimpleNamespace

    rows = [SimpleNamespace(id="a", reference="C(2012)100", merged_from=None),
            SimpleNamespace(id="b", reference="C(2026)200", merged_from=None)]

    class Conn:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, stmt, params=None):
            if "SELECT id, reference, merged_from" in str(stmt):
                return SimpleNamespace(fetchall=lambda: rows)
            self.assigned = params
            return SimpleNamespace(rowcount=1)

    engine = SimpleNamespace(connect=Conn, begin=Conn)

    class Resp:
        def __init__(self, body): self.body = body
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return self.body

    def fake_urlopen(req, timeout=0):
        q = req.data.decode()
        if "C%282012%29" in q:
            raise TimeoutError("The read operation timed out")
        return Resp(json.dumps({"results": {"bindings": [
            {"m": {"value": "C(2026)200/123 - PE"}, "celex": {"value": "32026R0999"}}]}}).encode())
    monkeypatch.setattr(job.urllib.request, "urlopen", fake_urlopen)
    out = job.resolve_celex(engine)
    assert out["assigned"] == 1 and out["failed_years"] == ["2012 (TimeoutError)"]

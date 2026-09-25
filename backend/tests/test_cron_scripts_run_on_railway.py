"""Cron jobs that worked on a laptop and failed on Railway (25 Sep 2026).

Three failures surfaced in `sync_runs` the morning after the Tenderator chain
started recording its children, and auditing them found each was a class:

1. Ten cron-launched scripts read DATABASE_URL from a `.env` file ONLY. Railway
   has no `.env`; the variable is in the environment. Every run exited
   "[FATAL] DATABASE_URL missing", and nine of the ten never wrote a ledger row.
2. The Tenderator translator imported `langdetect` (absent from the Railway image)
   and was built around a local 1.9 GB model the image deliberately excludes. It
   now detects on Railway and reports the untranslated backlog as `degraded`.
3. The MEP snapshot called EP's `/meps/show-current` once, straight after a burst
   of term-list pages, and gave up on EP's pool-exhaustion body in 0 seconds.
"""
from __future__ import annotations

import ast
import asyncio
import os
import pathlib
import re

import pytest

_BACKEND = pathlib.Path(__file__).resolve().parents[1]
_CRON = (_BACKEND / "api" / "cron.py").read_text()
_CRON_SCRIPTS = sorted(set(re.findall(r'"(scripts/[a-z0-9_]+\.py)"', _CRON)))


def _get_env_fn(path: pathlib.Path):
    """Exec a script's module-level `get_env` alone, with ENV pointing nowhere."""
    src = path.read_text()
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name == "get_env":
            ns = {"ENV": pathlib.Path("/nonexistent/.env"), "os": os}
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), ns)
            return ns["get_env"]
    return None


def test_the_cron_launches_scripts():
    # A regex that stops matching would make every test below vacuous.
    assert len(_CRON_SCRIPTS) >= 40


@pytest.mark.parametrize("rel", _CRON_SCRIPTS)
def test_cron_script_reads_database_url_from_the_environment(rel, monkeypatch):
    path = _BACKEND / rel
    if not path.exists():
        pytest.skip(f"{rel} not on disk")
    fn = _get_env_fn(path)
    if fn is None:
        src = path.read_text()
        reads_env_file = bool(re.search(r"\.env[\"']?\)?\.read_text|open\([^)]*\.env", src))
        if reads_env_file and "DATABASE_URL" in src:
            assert re.search(r"os\.environ|os\.getenv|get_database_url|load_dotenv", src), (
                f"{rel} reads DATABASE_URL from a .env file and never from the environment")
        return
    monkeypatch.setenv("DATABASE_URL", "postgresql://railway-env")
    assert fn("DATABASE_URL") == "postgresql://railway-env", (
        f"{rel}.get_env ignores the environment: on Railway it returns '' and the job dies")


def test_runner_turns_a_degraded_line_into_degraded(monkeypatch, tmp_path):
    from api import cron
    script = tmp_path / "child.py"
    script.write_text("print('[x] done')\nprint('[SYNC_STATUS] degraded: 12 rows untranslated')\n")
    res = cron._run_script("child", str(script), [], timeout=30)
    assert res["status"] == "degraded"
    assert "12 rows untranslated" in res["stderr_tail"]


def test_runner_still_reports_a_clean_success(tmp_path):
    from api import cron
    script = tmp_path / "child.py"
    script.write_text("print('[OK] nothing owed')\n")
    assert cron._run_script("child", str(script), [], timeout=30)["status"] == "success"


def test_ted_prefix_is_not_detected_as_english():
    import sys
    sys.path.insert(0, str(_BACKEND / "scripts"))
    from backfill_tenderator_translations import _detection_text
    t = "Germany – Construction work – Ausschreibung von Wärmeversorgungsanlagen"
    assert _detection_text("tenders", t, "") == "Ausschreibung von Wärmeversorgungsanlagen"
    # Not a TED-shaped title: left alone. Other tables: left alone.
    assert _detection_text("tenders", "Plain title", "desc") == "Plain title desc"
    assert _detection_text("ft_calls_for_tenders", t, "") == t


def test_translator_is_honest_without_an_engine(monkeypatch):
    import sys
    sys.path.insert(0, str(_BACKEND / "scripts"))
    import backfill_tenderator_translations as bt
    import builtins
    real_import = builtins.__import__

    def no_transformers(name, *a, **k):
        if name == "transformers":
            raise ImportError("not in the light image")
        return real_import(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", no_transformers)
    assert bt._engine_available() is False


def test_current_meps_retries_a_bad_spell(monkeypatch):
    from api.v1 import meps as m
    calls = {"n": 0}

    async def flaky(patient=False):
        calls["n"] += 1
        return None if calls["n"] < 3 else {"1", "2"}

    async def no_sleep(_s):
        return None
    monkeypatch.setattr(m, "_fetch_current_ids_once", flaky)
    monkeypatch.setattr(m.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(m, "_cached", lambda k: None)
    monkeypatch.setattr(m, "_put", lambda k, v: None)
    assert asyncio.run(m._fetch_current_ids(patient=True)) == {"1", "2"}
    assert calls["n"] == 3


def test_current_meps_request_path_never_waits(monkeypatch):
    from api.v1 import meps as m
    calls = {"n": 0}

    async def down(patient=False):
        calls["n"] += 1
        return None
    monkeypatch.setattr(m, "_fetch_current_ids_once", down)
    monkeypatch.setattr(m, "_cached", lambda k: None)
    assert asyncio.run(m._fetch_current_ids(patient=False)) is None
    assert calls["n"] == 1


_EFORMS = """<?xml version="1.0"?>
<ContractNotice xmlns="urn:oasis:names:specification:ubl:schema:xsd:ContractNotice-2"
 xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
 xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cac:TenderingTerms><cac:AppealTerms><cac:PresentationPeriod>
    <cbc:Description languageID="DEU">Rügeobliegenheit boilerplate</cbc:Description>
  </cac:PresentationPeriod></cac:AppealTerms></cac:TenderingTerms>
  <cac:ProcurementProject>
    <cbc:Name languageID="DEU">Umbau</cbc:Name>
    <cbc:Description languageID="DEU">Umbaumaßnahmen im Gebäude Reha Aufstockung</cbc:Description>
  </cac:ProcurementProject>
  <cac:ProcurementProjectLot><cbc:ID schemeName="Lot">LOT-0001</cbc:ID>
    <cac:ProcurementProject><cbc:Description languageID="DEU">Los 1: Heizung</cbc:Description></cac:ProcurementProject>
  </cac:ProcurementProjectLot>
</ContractNotice>"""


def test_eforms_description_is_the_project_not_the_boilerplate():
    from services.tenders.eforms_parser import EFormsParser
    d = EFormsParser().parse(_EFORMS)["description"]
    assert d.startswith("Umbaumaßnahmen im Gebäude")
    assert "Los 1: Heizung" in d
    assert "Rügeobliegenheit" not in d


def test_backfill_uses_the_ingest_parser_for_eforms():
    import sys
    sys.path.insert(0, str(_BACKEND / "scripts"))
    from backfill_tenders_description import extract_description
    assert extract_description(_EFORMS).startswith("Umbaumaßnahmen")


def test_current_meps_splits_a_stuck_window(monkeypatch):
    """EP answers limit=200&offset=600 with its pool-exhaustion body every time,
    while smaller windows over the same people answer (25 Sep 2026)."""
    from api.v1 import meps as m

    class R:
        def __init__(self, payload): self._p = payload
        def raise_for_status(self): pass
        def json(self): return self._p

    people = [{"identifier": str(i)} for i in range(718)]

    async def fake_get(hc, path, params, patient=False):
        assert path == "/meps/show-current"
        off, lim = params["offset"], params["limit"]
        if off == 600 and lim == 200:
            return R({"error": "Pending acquire queue has reached its maximum size of 100"})
        return R({"data": people[off:off + lim]})
    monkeypatch.setattr(m, "_ep_get", fake_get)
    monkeypatch.setattr(m, "_identifier", lambda x: x["identifier"])
    ids = asyncio.run(m._fetch_current_ids_once(patient=True))
    assert ids is not None and len(ids) == 718

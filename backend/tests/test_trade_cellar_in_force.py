"""Both trade backfills read Cellar's in-force flag and end-of-validity date (register O234).

Until 6 Nov 2026 hydrate_metadata did bool(meta["inForce"]) on the raw SPARQL literal: '0' is a
non-empty string, so every act Cellar marks not in force was stored as in force (31995R0823,
ended 14 Oct 1995, read in force). It also read a key the query never returns
(dateEndValidity; the client's variable is ?dateEnd), so date_end_validity was empty on every row.

These tests run the REAL CellarSPARQLClient.get_celex_metadata (only the network call is faked)
into the REAL hydrate_metadata of each script, so a renamed SPARQL variable fails here too.
"""
import asyncio
import importlib.util
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _BACKEND / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SCRIPTS = {
    "backfill_eu_trade_defence": "eu_trade_defence_measures",
    "backfill_eu_trade_agreements": "eu_trade_agreements",
}


def _fake_client(raw_rows, calls):
    from services.api_clients import cellar_sparql_client as real

    class _Client(real.CellarSPARQLClient):
        async def select(self, query, *a, **k):
            calls.append(query)
            return [dict(r) for r in raw_rows]

        async def close(self):
            return None

        async def get_available_languages(self, celex):
            return []

        async def get_eurovoc_concepts(self, celex):
            return []

    return real, _Client


# What Cellar's SPARQL endpoint returns: literals as strings, an absent OPTIONAL as a missing key.
ENDED_1995 = {"work": "http://publications.europa.eu/resource/cellar/x", "date": "1995-04-10",
              "title": "Commission Regulation (EC) No 823/95", "inForce": "0",
              "dateInForce": "1995-04-12", "dateEnd": "1995-10-14"}
IN_FORCE = {**ENDED_1995, "inForce": "1", "dateEnd": "9999-12-31"}
NO_STATUS = {k: v for k, v in ENDED_1995.items() if k not in ("inForce", "dateEnd")}


@pytest.mark.parametrize("script", sorted(SCRIPTS))
@pytest.mark.parametrize("row, in_force, end", [
    (ENDED_1995, False, "1995-10-14"),
    (IN_FORCE, True, "9999-12-31"),
    (NO_STATUS, None, None),
])
def test_hydrate_reads_the_raw_literal_and_the_end_date(monkeypatch, script, row, in_force, end):
    mod = _load(script)
    calls = []
    real, fake = _fake_client([row], calls)
    monkeypatch.setattr(real, "CellarSPARQLClient", fake)
    meta = asyncio.run(mod.hydrate_metadata("31995R0823"))
    assert calls and "?dateEnd" in calls[0], "the metadata query did not run through the real client"
    assert meta["in_force"] is in_force
    assert meta["date_end_validity"] == end
    assert mod.to_iso(meta["date_end_validity"]) == end


@pytest.mark.parametrize("script", sorted(SCRIPTS))
def test_a_failed_or_empty_cellar_read_is_unknown_not_false(monkeypatch, script):
    mod = _load(script)
    real, fake = _fake_client([], [])
    monkeypatch.setattr(real, "CellarSPARQLClient", fake)
    meta = asyncio.run(mod.hydrate_metadata("31995R0823"))
    assert meta["in_force"] is None and meta["date_end_validity"] is None


@pytest.mark.parametrize("script, table", sorted(SCRIPTS.items()))
def test_the_upsert_never_writes_unknown_over_a_stored_flag(script, table):
    sql = _load(script).UPSERT_SQL
    assert f"in_force = COALESCE(EXCLUDED.in_force, {table}.in_force)" in sql
    assert "in_force = EXCLUDED.in_force," not in sql


def test_the_chat_says_unknown_when_no_status_is_recorded():
    src = (_BACKEND / "services" / "ai" / "context_builder.py").read_text()
    line = '{True: "in force", False: "historical"}.get(r.get("in_force"), "in-force status not recorded")'
    assert src.count(line) == 2, "both trade blocks (agreements, defence measures) use the three states"
    assert 'inf = "in force" if r.get("in_force") else "historical"' not in src


@pytest.mark.parametrize("script", sorted(SCRIPTS))
def test_cellar_placeholder_dates_are_not_stored(monkeypatch, script):
    # 22026A02066, read 6 Nov 2026: signed, not yet in force; Cellar gives entry into force
    # 1001-01-01 (no date) and end of validity 9999-12-31 (no end date).
    mod = _load(script)
    row = {**IN_FORCE, "inForce": "0", "dateInForce": "1001-01-01", "dateEnd": "9999-12-31"}
    real, fake = _fake_client([row], [])
    monkeypatch.setattr(real, "CellarSPARQLClient", fake)
    meta = asyncio.run(mod.hydrate_metadata("22026A02066"))
    assert meta["in_force"] is False
    assert mod.to_iso(meta["date_in_force"]) is None
    assert mod.to_iso("1002-02-02") is None
    assert mod.to_iso(meta["date_end_validity"]) == "9999-12-31"
    assert mod.to_iso("2026-10-31T00:00:00") == "2026-10-31"

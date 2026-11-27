"""/laws serves what the CELEX states and the Publications Office's metadata for each law (Victor, 16 Oct 2026)."""
import inspect
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))


def _sql(clauses):
    return " AND ".join(str(c.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
                        for c in clauses)


def test_celex_info_reads_every_part():
    from services.celex_types import celex_info
    ai = celex_info("32024R1689")
    assert (ai["sector"], ai["sector_name"], ai["year"], ai["number"]) == ("3", "Legal acts", 2024, 1689)
    assert (ai["document_type_code"], ai["document_type"], ai["corrected_act"]) == ("R", "Regulation", None)
    assert celex_info("32006R1907R(01)")["corrected_act"] == "32006R1907"
    assert celex_info("22009A0619(01)R(01)")["corrected_act"] == "22009A0619(01)"
    assert celex_info("32014H0729(21)")["corrected_act"] is None  # (NN) is a further document, not a corrigendum
    assert celex_info("21972A0722(05)")["document_type"].startswith("Agreement")  # sector 2: A is an agreement
    assert celex_info("52021PC0206")["document_type_code"] == "PC"
    assert celex_info("C/2025/03118")["sector"] is None and celex_info(None)["year"] is None


def test_the_table_builder_reads_the_same_labels():
    from services import celex_types
    sys.path.insert(0, str(_BACKEND.parent))
    from backend.scripts import build_leg_table
    # imported under two names (services., backend.services.), so compare the values and the defining file
    assert build_leg_table.TYPE_LABELS == celex_types.TYPE_LABELS
    assert inspect.getsourcefile(build_leg_table.base_of) == inspect.getsourcefile(celex_types.base_of)


def test_a_law_item_carries_the_new_fields():
    from api.v1.laws import _law_item
    row = SimpleNamespace(id=1, celex="32016R0679", title="Regulation (EU) 2016/679", doc_type="Regulation",
                          doc_type_normalized="Regulation", date=None, oj_reference=None, legal_basis=[],
                          created_at=None, updated_at=None, body_txt=None, body_html=None, eurovoc=None,
                          eurovoc_domain=None, alias="General Data Protection Regulation", acronym="GDPR",
                          authors=["CONSIL", "EP"], in_force=True, eli="http://data.europa.eu/eli/reg/2016/679/oj",
                          entry_into_force=None, procedures=["2012/0011"])
    it = _law_item(row)
    assert (it.sector, it.year, it.number, it.document_type_code, it.document_type) == ("3", 2016, 679, "R", "Regulation")
    assert (it.alias, it.acronym, it.authors, it.in_force, it.procedures) == (
        "General Data Protection Regulation", "GDPR", ["CONSIL", "EP"], True, ["2012/0011"])
    assert it.entry_into_force == [] and it.corrected_act is None
    old = SimpleNamespace(**{k: v for k, v in vars(row).items() if k not in ("alias", "acronym", "authors", "in_force",
                                                                             "eli", "entry_into_force", "procedures")})
    assert _law_item(old).authors == [] and _law_item(old).in_force is None  # a row read before migration 301


def test_each_filter_compiles_to_what_it_says():
    from api.v1.laws import metadata_filters
    assert "LIKE '3%%'" in _sql(metadata_filters(sector="3")) or "LIKE '3%'" in _sql(metadata_filters(sector="3"))
    assert "substr(eu_laws.celex, 2, 4) = '2024'" in _sql(metadata_filters(year=2024))
    assert "0*1689([^0-9]|$)" in _sql(metadata_filters(number=1689))
    assert "^3[0-9]{4}R[0-9]" in _sql(metadata_filters(document_type="regulation"))
    assert _sql(metadata_filters(document_type="R")) == _sql(metadata_filters(document_type="Regulation"))
    assert "32016R0679" in _sql(metadata_filters(alias="GDPR"))
    assert "'unknown name'" in _sql(metadata_filters(alias="Unknown Name")).lower()
    assert "'COM' = ANY (eu_laws.authors)" in _sql(metadata_filters(author="com"))
    assert "in_force IS true" in _sql(metadata_filters(in_force=True))
    assert "'2021/0106' = ANY (eu_laws.procedures)" in _sql(metadata_filters(procedure="2021/106(COD)"))
    assert "LIKE '32024R1689R(%%'" in _sql(metadata_filters(corrects="32024r1689")) or \
           "LIKE '32024R1689R(%'" in _sql(metadata_filters(corrects="32024r1689"))
    assert metadata_filters() == []


def test_a_descriptor_without_a_label_still_filters():
    from api.v1.laws import metadata_filters
    assert "^[0-9CE][0-9]{4}PC[0-9]" in _sql(metadata_filters(document_type="PC"))


@pytest.mark.parametrize("kw", [{"sector": "Z"}, {"document_type": "treaty of nowhere"}, {"procedure": "COD 106"},
                                {"corrects": "3%"}, {"corrects": "32024R1689R(01)"}])
def test_a_wrong_filter_value_is_a_422(kw):
    from api.v1.laws import metadata_filters
    with pytest.raises(HTTPException) as e:
        metadata_filters(**kw)
    assert e.value.status_code == 422 and e.value.detail["reason_code"] == "invalid_filter"


NEW = ("sector", "year", "number", "document_type", "alias", "author", "in_force", "procedure", "corrects")


def test_v1_and_v2_take_the_same_filters():
    from api.v1 import laws
    from api.v2.legislative import eur_lex
    p1 = set(inspect.signature(laws.list_laws).parameters) - {"request", "user", "db"}
    p2 = set(inspect.signature(eur_lex.list_laws).parameters) - {"request", "user", "db"}
    assert p1 == p2 and set(NEW) <= p1


def test_v2_passes_the_new_filters_to_v1(monkeypatch):
    import asyncio
    from api.v2.legislative import eur_lex
    seen = {}

    async def fake_v1(request, **kw):
        seen.update(kw)
        return SimpleNamespace(data=[])

    monkeypatch.setattr(eur_lex._v1_laws, "list_laws", fake_v1)
    base = {k: None for k in inspect.signature(eur_lex.list_laws).parameters if k not in ("request",)}
    base.update(include_orphans=False, include_body=True, limit=10, page=1, sector="3", year=2024, alias="GDPR",
                in_force=True, corrects="32024R1689")
    asyncio.run(eur_lex.list_laws(None, **base))
    assert (seen["sector"], seen["year"], seen["alias"], seen["in_force"], seen["corrects"]) == ("3", 2024, "GDPR", True, "32024R1689")


_DUMP = _BACKEND.parent / "docs" / "LEG_2026-10"


@pytest.mark.skipif(not _DUMP.is_dir(), reason="the LEG_2026-10 export is not on this machine")
def test_the_metadata_is_read_from_the_work_and_dates_keep_their_type():
    # the audit of 16 Oct: one list mixed entry into force (EV), application (MA) and effect (PE) dates, and the
    # table's ELI regex stopped at "(" (32014D0026 is .../26(1)/oj)
    sys.path.insert(0, str(_BACKEND.parent))
    from backend.scripts.leg_export_metadata import folder_of_celex, rdf_facts
    f = folder_of_celex()
    gdpr, ai, dec = (rdf_facts(_DUMP, f[c]) for c in ("32016R0679", "32024R1689", "32014D0026"))
    assert gdpr["entry_into_force"] == ["2016-05-24"] and gdpr["application_dates"] == ["2018-05-25"]
    assert ai["entry_into_force"] == ["2024-08-01"] and len(ai["application_dates"]) == 4 and ai["procedures"] == ["2021/0106"]
    assert dec["eli"] == "http://data.europa.eu/eli/dec/2014/26(1)/oj" and dec["effect_dates"] == ["2014-01-20"]
    assert gdpr["authors"] == ["CONSIL", "EP"] and gdpr["in_force"] is True


def test_dates_keep_their_type_and_placeholders_are_dropped():
    # audit of the backfill, 16 Oct 2026: 1001-01-01 and 1002-02-02 are the Publications Office's placeholders
    sys.path.insert(0, str(_BACKEND.parent))
    from backend.scripts.leg_export_metadata import place_dates
    got = place_dates([("2024-08-01", "EV"), ("2025-02-02", "MA"), ("2025-08-02", "MA/PROV"), ("2026-01-01", "APPLICATION"),
                       ("2014-01-20", "PE"), ("2019-09-16", ""), ("2020-01-01", "DATPUB"), ("1001-01-01", "EV"), ("1002-02-02", "MA")])
    assert got == {"entry_into_force": ["2019-09-16", "2020-01-01", "2024-08-01"],
                   "application_dates": ["2025-02-02", "2025-08-02", "2026-01-01"], "effect_dates": ["2014-01-20"]}
    assert place_dates([("1001-01-01", "EV")]) == {"entry_into_force": None, "application_dates": None, "effect_dates": None}


def test_a_lettered_procedure_is_kept():
    sys.path.insert(0, str(_BACKEND.parent))
    from backend.scripts.leg_export_metadata import procedure_number
    assert procedure_number("http://publications.europa.eu/resource/procedure/2011_901A") == "2011/0901A"
    assert procedure_number("http://publications.europa.eu/resource/procedure/2012_11") == "2012/0011"
    assert procedure_number("http://publications.europa.eu/resource/internal_proc/ABC123") is None


def test_a_later_export_never_blanks_merges_procedures_and_leaves_in_force():
    sys.path.insert(0, str(_BACKEND.parent))
    from backend.scripts.leg_export_metadata import merged
    assert merged("procedures", ["2012/0011"], None) == ["2012/0011"]          # Cellar's procedure survives
    assert merged("procedures", ["2012/0011"], ["2012/0012"]) == ["2012/0011", "2012/0012"]
    assert merged("eli", "http://data.europa.eu/eli/reg/2016/679/oj", None) == "http://data.europa.eu/eli/reg/2016/679/oj"
    assert merged("in_force", False, True) is False                             # the daily refresh owns it
    assert merged("in_force", None, True) is True
    assert merged("authors", ["COM"], ["COM", "SANTE"]) == ["COM", "SANTE"]


def test_the_procedure_filter_takes_a_letter_and_any_case():
    from api.v1.laws import metadata_filters
    assert "'2011/0901A' = ANY (eu_laws.procedures)" in _sql(metadata_filters(procedure="2011/0901A(COD)"))
    assert "'2020/0361' = ANY (eu_laws.procedures)" in _sql(metadata_filters(procedure="2020/0361(cod)"))


def test_cellar_down_stops_the_run_instead_of_splitting(monkeypatch):
    # audit of 16 Oct 2026: with Cellar refusing, batches of 80 split into 159 calls each and the daily job hit its
    # 30-minute timeout blind; now four failed calls in a row stop it with a reason
    import urllib.request
    sys.path.insert(0, str(_BACKEND.parent))
    from backend.scripts import leg_export_metadata as lem
    calls = []

    def refuse(*a, **k):
        calls.append(1)
        raise OSError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr(lem.time, "sleep", lambda s: None)
    with pytest.raises(lem.CellarDown):
        lem.cellar_facts([f"3202{i % 10}R{i:04d}" for i in range(400)], groups=("dossier",))
    assert len(calls) == lem.Budget.FAILS_IN_A_ROW


def test_a_spent_time_budget_stops_the_run(monkeypatch):
    sys.path.insert(0, str(_BACKEND.parent))
    from backend.scripts import leg_export_metadata as lem
    b = lem.Budget(seconds=1)
    b.deadline -= 5
    with pytest.raises(lem.CellarDown):
        lem.cellar_facts(["32016R0679"], groups=("dossier",), budget=b)


def _fake_cellar(monkeypatch, lem, slow=(), down=False):
    """Cellar as the refresher meets it: a query naming a law in `slow` times out, every other answers each law it
    names (in force) and the control law with its procedure. Returns the list of batches asked."""
    import io
    import json as _json
    import re as _re
    import urllib.parse
    import urllib.request
    asked = []

    def urlopen(req, timeout=None):
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(req.full_url).query)["query"][0]
        celexes = _re.findall(r'"([^"]+)"\^\^', q)
        asked.append(celexes)
        if down or any(c in slow for c in celexes):
            raise TimeoutError("The read operation timed out")
        rows = [{"c": {"value": c}, "f": {"value": "1"}} for c in celexes if c != lem.CONTROL]
        rows.append({"c": {"value": lem.CONTROL}, "f": {"value": "1"},
                     "s": {"value": "http://publications.europa.eu/resource/procedure/2012_11"}})
        return io.BytesIO(_json.dumps({"results": {"bindings": rows}}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(lem.time, "sleep", lambda s: None)
    return asked


def test_one_batch_cellar_cannot_answer_does_not_stop_the_run(monkeypatch):
    # 24-27 Nov 2026: rows 6720-6799 timed out every night while Cellar was up; the retry and the first halving made
    # four failures in a row, the run stopped at 19% as "Cellar unreachable" and the cron job went red four nights
    sys.path.insert(0, str(_BACKEND.parent))
    from backend.scripts import leg_export_metadata as lem
    laws = [f"3201{i % 10}R{i:04d}" for i in range(400)]
    slow = laws[130]
    asked = _fake_cellar(monkeypatch, lem, slow={slow})
    budget = lem.Budget()
    got = lem.cellar_facts(laws, groups=("dossier",), budget=budget, log=lambda m: None)
    assert slow not in got                                     # the law Cellar cannot answer stays unknown
    assert set(got) == set(laws) - {slow}                      # every other law of every batch is read
    assert all(v["in_force"] is True and v["seen"] for v in got.values())
    assert budget.failed == 0
    timed_out = [b for b in asked if slow in b]
    sizes = [len(b) - 1 for b in timed_out]
    assert sizes == [80, 40, 20, 10, 5, 2, 1]                  # halved down to the law itself, no size asked twice
    assert sum(1 for b in asked if b == [lem.CONTROL]) == len(timed_out)      # the control alone after each


def test_a_cellar_that_is_down_still_stops_after_four_calls(monkeypatch):
    sys.path.insert(0, str(_BACKEND.parent))
    from backend.scripts import leg_export_metadata as lem
    asked = _fake_cellar(monkeypatch, lem, down=True)
    budget = lem.Budget()
    with pytest.raises(lem.CellarDown):
        lem.cellar_facts([f"3201{i % 10}R{i:04d}" for i in range(400)], groups=("dossier",), budget=budget)
    assert len(asked) == lem.Budget.FAILS_IN_A_ROW == budget.failed
    assert [len(b) - 1 for b in asked] == [80, 0, 80, 0]       # the batch, the control alone, and both once more


def test_a_cellar_that_goes_down_during_a_split_stops_the_run(monkeypatch):
    sys.path.insert(0, str(_BACKEND.parent))
    from backend.scripts import leg_export_metadata as lem
    laws = [f"3201{i % 10}R{i:04d}" for i in range(160)]
    asked = _fake_cellar(monkeypatch, lem, slow={laws[10]})
    import urllib.request
    up = urllib.request.urlopen

    def goes_down(req, timeout=None):
        if len(asked) >= 4:                                    # after the first halving
            asked.append(["down"])
            raise OSError("connection refused")
        return up(req, timeout=timeout)

    monkeypatch.setattr(urllib.request, "urlopen", goes_down)
    with pytest.raises(lem.CellarDown):
        lem.cellar_facts(laws, groups=("dossier",), log=lambda m: None)
    assert asked.count(["down"]) == lem.Budget.FAILS_IN_A_ROW

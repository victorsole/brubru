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
    assert _law_item(old).authors == [] and _law_item(old).in_force is None  # a row read before migration 293


def test_each_filter_compiles_to_what_it_says():
    from api.v1.laws import metadata_filters
    assert "LIKE '3%%'" in _sql(metadata_filters(sector="3")) or "LIKE '3%'" in _sql(metadata_filters(sector="3"))
    assert "substr(eu_laws.celex, 2, 4) = '2024'" in _sql(metadata_filters(year=2024))
    assert "0*1689([^0-9]|$)" in _sql(metadata_filters(number=1689))
    assert "^3[0-9]{4}R[0-9]" in _sql(metadata_filters(document_type="regulation"))
    assert _sql(metadata_filters(document_type="R")) == _sql(metadata_filters(document_type="Regulation"))
    assert "'gdpr'" in _sql(metadata_filters(alias="GDPR")).lower()
    assert "'COM' = ANY (eu_laws.authors)" in _sql(metadata_filters(author="com"))
    assert "in_force IS true" in _sql(metadata_filters(in_force=True))
    assert "'2021/0106' = ANY (eu_laws.procedures)" in _sql(metadata_filters(procedure="2021/106(COD)"))
    assert "LIKE '32024R1689R(%%'" in _sql(metadata_filters(corrects="32024r1689")) or \
           "LIKE '32024R1689R(%'" in _sql(metadata_filters(corrects="32024r1689"))
    assert metadata_filters() == []


@pytest.mark.parametrize("kw", [{"sector": "Z"}, {"document_type": "treaty of nowhere"}, {"procedure": "COD 106"}])
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
def test_the_importer_reads_the_same_metadata_as_the_backfill():
    # two writers of the same columns must agree: the importer reads the RDF, the backfill the tables built from it
    import csv
    import random
    sys.path.insert(0, str(_BACKEND.parent))
    from backend.scripts.leg_export_metadata import export_metadata, sources, wanted
    table, folders, aliases = sources()
    rows = [r for r in csv.DictReader((_BACKEND / "data/leg_2026-10_table/leg_2026-10_folders.csv").open(encoding="utf-8-sig"))
            if r["has_text"] == "yes"]
    random.seed(16)
    for r in random.sample(rows, 150) + [r for r in rows if r["celex"] in ("32024R1689", "32022R2065", "32006R1907R(01)")]:
        w = {k: v for k, v in wanted(r["celex"], None, table, folders, aliases).items() if k not in ("alias", "acronym")}
        assert export_metadata(_DUMP, r["folder"], r["celex"]) == w, r["celex"]

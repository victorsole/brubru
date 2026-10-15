"""The importer takes each folder's CELEX from the dump's metadata, never from the text (14 Oct 2026).

224 rows were inserted without CELEX because the parser found none in the file, so the check that the
act was already held never ran; 35 corrigenda took the CELEX their text names.
"""
from backend.scripts.import_corpus_update import celex_for, folder_celex

U = "00000dbc-76cd-11ed-9887-01aa75ed71a1"
OTHER = "11111111-2222-3333-4444-555555555555"


def _rdf(tmp_path, body):
    (tmp_path / U).mkdir()
    (tmp_path / U / "tree_non_inferred.rdf").write_text(f"<rdf:RDF>{body}</rdf:RDF>")
    return tmp_path


def _celex(prefix, value):
    return f'<{prefix}:resource_legal_id_celex rdf:datatype="http://www.w3.org/2001/XMLSchema#string">{value}</{prefix}:resource_legal_id_celex>'


def test_folder_celex_reads_the_metadata(tmp_path):
    assert folder_celex(_rdf(tmp_path, _celex("j.0", "32022D2391")), U) == "32022D2391"


def test_folder_celex_any_namespace_prefix(tmp_path):
    assert folder_celex(_rdf(tmp_path, _celex("j.3", "32024R1689") * 2), U) == "32024R1689"


def test_folder_celex_none_when_absent_or_ambiguous(tmp_path):
    assert folder_celex(tmp_path, U) is None  # no metadata file
    assert folder_celex(_rdf(tmp_path, _celex("j.0", "32024R1689") + _celex("j.0", "32024R1690")), U) is None
    other = tmp_path / "x"
    other.mkdir()
    assert folder_celex(_rdf(other, "<j.0:resource_legal_id_celex_other>3</j.0:resource_legal_id_celex_other>"), U) is None


def test_celex_for_outcomes():
    held = {"32024R1689": U, "32025R0026": OTHER}
    assert celex_for(U, "32024R1689", "32024R1689", held) == ("32024R1689", "keep")
    assert celex_for(U, "32024R1690", None, held) == ("32024R1690", "fill")  # new row
    assert celex_for(U, "32024R1690", "", held) == ("32024R1690", "fill")  # row an earlier import left empty
    assert celex_for(U, "32024R1690", "32024R1689", held) == ("32024R1689", "conflict")  # never re-keyed
    assert celex_for(U, None, "32024R1689", held) == ("32024R1689", "none")
    assert celex_for(U, None, None, held) == (None, "none")


def test_a_mis_keyed_row_is_a_conflict_not_a_duplicate():
    # its folder's CELEX is held elsewhere, but the row carries another one: a person must see it
    assert celex_for(U, "32025R0026", "32024R1689", {"32025R0026": OTHER, "32024R1689": U}) == ("32024R1689", "conflict")


def test_folder_celex_rejects_a_value_that_is_not_a_celex(tmp_path):
    assert folder_celex(_rdf(tmp_path, _celex("j.0", "http://example.org/x")), U) is None


def test_an_act_held_by_another_row_is_not_inserted_again():
    # the 13 Oct case: the parser finds no CELEX, the Cellar sync's row already holds the act
    assert celex_for(U, "32025R0026", None, {"32025R0026": OTHER}) == (None, "held")

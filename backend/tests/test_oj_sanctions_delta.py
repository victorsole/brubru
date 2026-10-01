"""The OJ sanctions parser against real acts, checked by each act's own recital counts.

Fixtures are the Cellar XHTML of five regulations (fetched 1 Oct 2026). The expected
numbers come from the recitals ("10 persons and 17 entities should be added", "104
individuals and 71 entities ... should be [replaced]"), not from the parser.
"""
from collections import Counter
from pathlib import Path

from services.scrapers.oj_sanctions_delta import parse_act

FIX = Path(__file__).parent / "fixtures" / "oj_sanctions"


def _parse(celex, title=""):
    return parse_act(celex, (FIX / f"{celex}.html").read_text(), title)


def test_russia_children_listing_matches_recital():
    p = _parse("32026R2184")
    assert Counter((e.action, e.subject_type) for e in p.entries) == {("added", "P"): 10, ("added", "E"): 17}
    assert all(e.base_regulation == "269/2014" for e in p.entries)
    assert p.entries[0].name.startswith("Oleg Ivanovich SLADKEVICH")
    assert str(p.entries[0].date_of_listing) == "2026-09-28"


def test_russia_review_replaces_104_persons_and_71_entities():
    p = _parse("32026R2160")
    c = Counter((e.action, e.subject_type) for e in p.entries)
    assert c[("replaced", "P")] == 104 and c[("replaced", "E")] == 71
    assert sum(1 for e in p.entries if e.action == "deleted") == 7


def test_entries_inline_after_the_lead_sentence():
    p = _parse("32026R1880")
    assert [(e.action, e.subject_type, e.entry_number) for e in p.entries] == [
        ("added", "P", "45"), ("added", "P", "46"), ("added", "E", "10")]


def test_annex_move_is_one_add_and_one_delete_per_person():
    p = _parse("32026R2191")
    added = {e.name.split(" Designation")[0].upper() for e in p.entries if e.action == "added"}
    deleted = {e.name.upper() for e in p.entries if e.action == "deleted"}
    assert added == deleted and len(added) == 5
    assert {e.annex for e in p.entries if e.action == "added"} == {"I"}
    assert {e.annex for e in p.entries if e.action == "deleted"} == {"Ia"}
    assert not any(e.name.startswith(("ELI", "ANNEX")) for e in p.entries)


def test_terrorist_list_set_out_in_the_annex():
    p = _parse("32026R1878")
    assert {e.action for e in p.entries} == {"list_replaced"}
    assert Counter(e.subject_type for e in p.entries) == {"P": 13, "E": 23}
    assert {e.base_regulation for e in p.entries} == {"2580/2001"}

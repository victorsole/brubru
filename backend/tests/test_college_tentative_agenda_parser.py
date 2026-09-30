"""Parser for the College tentative agenda (SEC documents), fixed 30 Sep 2026.

SEC(2026) 2579 exposed two faults: a sub-bullet swallowed the next item
("2040 vision for fisheries and aquaculture" vanished into the migration
package's last bullet and was reported as dropped), and the page-2 header was
glued onto the Consumer package's last bullet.
"""
import importlib.util
import pathlib

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "sync_college_tentative_agendas", _ROOT / "scripts" / "sync_college_tentative_agendas.py")
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

TEXT = (_ROOT / "tests" / "fixtures" / "sec_2026_2579_tentative_agenda.txt").read_text()


def _items():
    return mod.parse_items(TEXT)


def test_every_item_is_found_with_its_member():
    got = [(i["meeting_date_provisional"], i["item"], i["responsible"]) for i in _items()]
    assert len(got) == 17
    assert ("28/10/2026", "2040 vision for fisheries and aquaculture", "FITTO") in got
    assert ("6/10/2026", "Revision of the Standardisation Regulation", "SÉJOURNÉ") in got
    assert ("18/11/2026", "Quantum Act", "VIRKKUNEN") in got
    assert ("24/11/2026", "Update of rules on unfair trading practices in the food chain", "FITTO") in got


def test_sub_bullets_end_at_the_cell_boundary():
    by = {i["item"]: i["sub_items"] for i in _items()}
    assert by["Border and migration package"] == [
        "Strengthening Frontex and enhancing its operations",
        "Digitalisation of the return process",
        "European annual asylum and migration report",
    ]
    assert by["Consumer package"] == ["Digital Fairness Act", "Consumer enforcement initiative"]


def test_page_header_never_reaches_an_item():
    for i in _items():
        for text in [i["item"], *i["sub_items"]]:
            assert "SEC(2026)" not in text and "Date of" not in text and "(tbc)" not in text


def test_events_column_is_dropped():
    for i in _items():
        assert "EP Plenary" not in i["item"] and "European Council" not in i["item"]

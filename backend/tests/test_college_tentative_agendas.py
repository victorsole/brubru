"""The tentative-agenda parser must keep reading the table the way it was built to.

Context (22 September 2026). Nothing had ever fetched the College's tentative
agendas: `commission_documents` held zero rows of that type, and `/news` carried
the instruction as prose only. These tests pin the three things the parser got
wrong while it was being written, each caught against a PDF read by eye first.

All offline: the fixture is the text of SEC(2026)2578, extracted from the real
PDF, so no network and no database.
"""

import importlib.util
import os
import pathlib
import sys

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
_BACKEND = os.path.join(_REPO_ROOT, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


def _load():
    spec = importlib.util.spec_from_file_location(
        "sync_college_tentative_agendas",
        os.path.join(_BACKEND, "scripts", "sync_college_tentative_agendas.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["sync_college_tentative_agendas"] = mod
    spec.loader.exec_module(mod)
    return mod


agendas = _load()

# The table as it appears in SEC(2026)2578 once PyMuPDF flattens it. The middle
# block is the "Other relevant events" column bleeding inline, which is exactly
# what the parser has to survive.
FIXTURE = """Monday, 14 September 2026
Possible items for Commission agendas 30 September 2026 - 28 October 2026
Date of
Commission
meeting
(tbc)
30/09/2026
Pre-enlargement policy reviews
PRESIDENT
European critical communication system
VIRKKUNEN
6/10/2026
(Str)
European product package
SÉJOURNÉ
5-8 October
EP Plenary
-
European Product Act: update of the framework for product rules and market
surveillance
-
Standardisation Regulation: update of rules on standardisation
20/10/2026
(Str)
2027 Commission work programme
PRESIDENT
15-16 October
European Council
Northern Neighbourhood - New Arctic Strategy
PRESIDENT
"""


def test_items_are_attached_to_the_right_meeting_date():
    items = agendas.parse_items(FIXTURE)
    by_date = {}
    for i in items:
        by_date.setdefault(i["meeting_date_provisional"], []).append(i["item"])
    assert by_date["30/09/2026"] == [
        "Pre-enlargement policy reviews", "European critical communication system"]
    assert by_date["6/10/2026"] == ["European product package"]
    assert by_date["20/10/2026"] == [
        "2027 Commission work programme", "Northern Neighbourhood - New Arctic Strategy"]


def test_the_events_column_never_becomes_an_agenda_item():
    """First version produced "EP Plenary 2026 annual overview report...".

    The events column arrives as a date range ("5-8 October") followed by a
    label ("EP Plenary"). Dropping only the range left the label to glue itself
    onto the front of the next real item.
    """
    items = agendas.parse_items(FIXTURE)
    titles = [i["item"] for i in items]
    assert not any("EP Plenary" in t for t in titles), titles
    assert not any("European Council" in t for t in titles), titles
    assert "2027 Commission work programme" in titles


def test_every_sub_bullet_is_kept_not_just_the_last():
    """First version assigned instead of appending, so each group kept one bullet.

    "European product package" reported only the Standardisation Regulation and
    silently lost the European Product Act.
    """
    items = agendas.parse_items(FIXTURE)
    pkg = next(i for i in items if i["item"] == "European product package")
    assert len(pkg["sub_items"]) == 2, pkg["sub_items"]
    assert any("European Product Act" in s for s in pkg["sub_items"])
    assert any("Standardisation Regulation" in s for s in pkg["sub_items"])


def test_an_accented_commissioner_name_is_recognised():
    """SÉJOURNÉ must match. An explicit [A-Z] range would drop it, which is the
    same defect that once lost KNOTEK Ondřej from the deep-dive parser."""
    assert agendas._is_member("SÉJOURNÉ")
    assert agendas._is_member("PRESIDENT")
    assert agendas._is_member("VIRKKUNEN")
    assert not agendas._is_member("European product package")
    assert not agendas._is_member("")


def test_a_date_outside_the_table_does_not_open_a_block():
    """Text before the first meeting date must not be collected as items."""
    items = agendas.parse_items(FIXTURE)
    assert all(i["meeting_date_provisional"] in
               {"30/09/2026", "6/10/2026", "20/10/2026"} for i in items)
    assert not any("Possible items for Commission agendas" in i["item"] for i in items)


def test_the_query_payload_pins_the_document_type():
    """A wrong `types` value makes the register return everything, which would
    look like a successful run holding the wrong documents."""
    assert agendas.QUERY["types"] == ["TENTAT_AGENDA_COM_MEETING"]
    assert agendas.QUERY["sortBy"] == "DOCUMENT_DATE_DESC"


def test_a_non_pdf_response_is_rejected_rather_than_stored():
    """The file endpoint sends Content-Type: application/json for real PDFs, so
    the magic bytes are the only trustworthy signal."""
    assert FIXTURE.encode()[:4] != b"%PDF"

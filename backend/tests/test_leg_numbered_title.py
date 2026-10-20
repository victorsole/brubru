"""A law whose title is only its type takes the number it prints under it (Victor, 20 Oct 2026).

Ten Decisions of Parliament's Secretary-General (OJ C, staff matters) were titled "Decision": the export's metadata
and the Formex parser both give the bare word; the act prints "Decision" and, below it, <NO.DOC.C>2014/C 34/01.
"""
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND.parent))

from backend.scripts.leg_folder import numbered_title  # noqa: E402

ACT = ('<?xml version="1.0" encoding="UTF-8"?><ACT><BIB.INSTANCE><NO.DOC.C>ignored 1/1</NO.DOC.C></BIB.INSTANCE>'
       "<TITLE><TI><P>Decision</P><NO.DOC.C>2014/C 34/01</NO.DOC.C></TI></TITLE>"
       "<PREAMBLE><P>THE SECRETARY-GENERAL OF THE EUROPEAN PARLIAMENT,</P></PREAMBLE></ACT>")


def test_a_bare_type_takes_the_number_printed_under_the_title(tmp_path):
    f = tmp_path / "C_2014034EN.01000101.xml"
    f.write_text(ACT, encoding="utf-8")
    assert numbered_title("Decision", f) == "Decision 2014/C 34/01"


def test_anything_else_is_left_as_it_is(tmp_path):
    f = tmp_path / "act.xml"
    f.write_text(ACT, encoding="utf-8")
    assert numbered_title("Commission Decision (EU) 2022/348 of 17 June 2021", f) == "Commission Decision (EU) 2022/348 of 17 June 2021"
    assert numbered_title("Decision", tmp_path / "missing.xml") == "Decision"
    assert numbered_title("Decision", None) == "Decision"
    assert numbered_title(None, f) is None
    g = tmp_path / "no_number.xml"
    g.write_text("<ACT><TITLE><TI><P>Decision</P><NO.DOC.C>see below</NO.DOC.C></TI></TITLE></ACT>", encoding="utf-8")
    assert numbered_title("Decision", g) == "Decision"
    h = tmp_path / "outside_title.xml"  # a number outside the TITLE is not the act's
    h.write_text("<ACT><BIB.INSTANCE><NO.DOC.C>2014/C 34/01</NO.DOC.C></BIB.INSTANCE><TITLE><TI><P>Decision</P></TI></TITLE></ACT>",
                 encoding="utf-8")
    assert numbered_title("Decision", h) == "Decision"
    k = tmp_path / "after_title.xml"  # nor one after it
    k.write_text("<ACT><TITLE><TI><P>Decision</P></TI></TITLE><PREAMBLE><NO.DOC.C>2014/C 34/01</NO.DOC.C></PREAMBLE></ACT>",
                 encoding="utf-8")
    assert numbered_title("Decision", k) == "Decision"


def test_the_importer_applies_it():
    src = (_BACKEND / "scripts" / "import_corpus_update.py").read_text()
    assert 'fields["title"] = numbered_title(usable_title(m["title"]) or fields["title"], xml_path)' in src

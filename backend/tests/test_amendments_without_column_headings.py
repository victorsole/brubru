"""An amendment's texts carry no column headings and its type says what it does (16 Oct 2026).

The parser kept the table headings when they share a row with the text: 63,730 proposed
texts began "Amendment", 59,798 originals "Text proposed by the Commission". A new
provision's original column held the heading alone, so 10,279 additions read
'modification'; "Amendment / deleted" read 'modification' 4,464 times."""
from __future__ import annotations

import io

from docx import Document

from scripts.backfill_amendment_column_headers import corrected
from services.parsers.ep_amendment_parser import EPAmendmentParser, strip_column_header


def _docx(rows_by_amendment):
    doc = Document()
    for n, (left, right, group) in enumerate(rows_by_amendment, 1):
        doc.add_paragraph("<Amend>Amendment <NumAm>%d</NumAm>" % n)
        doc.add_paragraph("<Members>Fabienne Keller</Members>")
        if group:
            doc.add_paragraph("<AuNomDe>{%s}on behalf of</AuNomDe>" % group)
        doc.add_paragraph("<Article>Article 2 – paragraph 1 – point 9 a (new)</Article>")
        # The EP's table: a merged empty first row, then the headings row, then the text
        # row (CJ13-PR-787767, read 16 Oct 2026). The old skip only looked at row 0.
        heading_left, *left_text = left.split("\n")
        heading_right, *right_text = right.split("\n")
        t = doc.add_table(rows=3, cols=2)
        t.cell(0, 0).merge(t.cell(0, 1))
        t.cell(1, 0).text, t.cell(1, 1).text = heading_left, heading_right
        t.cell(2, 0).text, t.cell(2, 1).text = "\n".join(left_text), "\n".join(right_text)
        doc.add_paragraph("</Amend>")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_the_parser_drops_the_headings_and_types_each_amendment():
    raw = _docx([
        ("Text proposed by the Commission", "Amendment\n(9a)'baseline' means the status of the indicator", "Renew"),
        ("Text proposed by the Commission\n2. Member States shall ensure", "Amendment\ndeleted", None),
        ("Present text\n(b) the operator", "Amendment\n(b) the operator and the importer", "LIBE"),
    ])
    got = EPAmendmentParser().parse_docx(raw, committee="LIBE", pe_reference="PE773.119", procedure_ref="2025/0001(COD)")
    assert [(a.original_text, a.amendment_type) for a in got] == [
        ("", "addition"), ("2. Member States shall ensure", "suppression"), ("(b) the operator", "modification")]
    assert got[0].proposed_text.startswith("(9a)")
    assert (got[0].political_group, got[0].on_behalf_of_group) == ("Renew", True)
    assert (got[2].political_group, got[2].on_behalf_of_group) == (None, False)


def test_a_heading_is_only_removed_when_it_is_the_whole_first_line():
    assert strip_column_header("Amendment of Regulation (EU) 2019/1020") == "Amendment of Regulation (EU) 2019/1020"
    assert strip_column_header("Draft motion for a resolution\n1. Calls on") == "1. Calls on"
    assert strip_column_header("Council position") == ""


def test_the_backfill_rewrites_a_stored_row_as_the_parser_reads_it():
    row = {"original_text": "Text proposed by the Commission", "proposed_text": "Amendment\n(10a) new point",
           "amendment_type": "modification", "political_group": "LIBE", "on_behalf_of_group": True}
    assert corrected(row) == {"o": "", "p": "(10a) new point", "t": "addition", "g": None, "b": False}
    clean = {"original_text": "x", "proposed_text": "y", "amendment_type": "modification",
             "political_group": "EPP", "on_behalf_of_group": False}
    assert corrected(clean) is None

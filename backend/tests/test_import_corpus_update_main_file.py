"""The importer picks an act's main file by what it contains, never an annex page or the cover page (15 Oct 2026).

Keeping a row's earlier file on every import had left 7,352 rows on an ANNEX page and 2,849 filled from the cover
page: titled "ANNEX" or "Official Journal of the European Union", typed Annex or Table of Contents.
"""
import re
from types import SimpleNamespace

from backend.scripts.import_corpus_update import main_file, rdf_meta, strip_number_prefix, title_match, type_label

U = "00000dbc-76cd-11ed-9887-01aa75ed71a1"


class TitleParser:
    """Stands in for FormexParser: the title is the file's <TI> text."""

    def parse_file(self, path):
        m = re.search(r"<TI>(.*?)</TI>", path.read_text())
        return SimpleNamespace(title=m.group(1) if m else "")


def _folder(tmp_path, files):
    fmx = tmp_path / U / "fmx4"
    fmx.mkdir(parents=True)
    for name, body in files.items():
        (fmx / name).write_bytes(body if isinstance(body, bytes) else body.encode())
    return tmp_path


def _x(root, title=""):
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<{root} xmlns:xsi="x"><TI>{title}</TI></{root}>'


def test_the_act_not_its_annex_or_cover_page(tmp_path):
    c = _folder(tmp_path, {"L_2016299EN.01002601.doc.xml": _x("DOC"), "L_2016299EN.01002601.xml": _x("ACT"),
                           "L_2016299EN.01002801.xml": _x("ANNEX")})
    picked, score = main_file(c, U, "32016R1929", lambda: None, TitleParser())
    assert picked.name == "L_2016299EN.01002601.xml" and score is None


def test_a_corrigendum_takes_the_republished_act_else_its_notice(tmp_path):
    # Victor, 14 and 15 Oct 2026: the republished act carries the articles, legal basis and citations
    c = _folder(tmp_path, {"L_2012121EN.01003801.xml": _x("CORR"), "L_2012121EN.01003802.xml": _x("ACT")})
    assert main_file(c, U, "32012D0234R(01)", lambda: None, TitleParser())[0].name == "L_2012121EN.01003802.xml"
    d = _folder(tmp_path / "d", {"L_2012121EN.01003801.xml": _x("CORR"), "L_2012121EN.01003901.xml": _x("ANNEX")})
    assert main_file(d, U, "32012D0234R(01)", lambda: None, TitleParser())[0].name == "L_2012121EN.01003801.xml"


def test_on_a_tie_the_current_file_stays(tmp_path):
    c = _folder(tmp_path, {"A.01000101.xml": _x("ACT", "Council Decision on fishing"),
                           "A.01000201.xml": _x("ACT", "Council Decision on fishing")})
    cur = c / U / "fmx4" / "A.01000201.xml"
    assert main_file(c, U, "32020D0001", lambda: "Council Decision on fishing", TitleParser(), current=cur)[0] == cur


def test_several_act_files_the_title_decides(tmp_path):
    c = _folder(tmp_path, {
        "L_2013347EN.01025901.xml": _x("GENERAL", "Joint statement of the European Parliament and of the Council concerning the application"),
        "L_2013347EN.01025902.xml": _x("ACT", "Regulation (EU) No 1299/2013 on specific provisions for the support from the European "
                                              "Regional Development Fund to the European territorial cooperation goal")})
    meta = "Regulation (EU) No 1299/2013 of the European Parliament and of the Council of 17 December 2013 on specific " \
           "provisions for the support from the European Regional Development Fund to the European territorial cooperation goal"
    picked, score = main_file(c, U, "32013R1299", lambda: meta, TitleParser())
    assert picked.name == "L_2013347EN.01025902.xml" and score > 0.4


def test_no_act_file_only_scans(tmp_path):
    c = _folder(tmp_path, {"L_2015252EN.01004901.xml": b"II*\x00" + b"\xff" * 20, "L_2015252EN.01004901.doc.xml": _x("DOC")})
    assert main_file(c, U, "32015D1735", lambda: None, TitleParser()) == (None, None)


def test_title_match_ignores_number_prefix_and_spacing():
    assert title_match("Council Decision of 21 October 2014 on the conclusion of an Agreement",
                       "2014/866/EU: Council Decision of  21\xa0October 2014 on the conclusion of an Agreement") == 1.0
    assert title_match("ANNEX", "Commission Implementing Regulation (EU) 2016/1929 approving Bacillus thuringiensis") == 0.0


def test_type_from_the_celex_letter():
    assert type_label("32016R1929", "Annex") == "Regulation"
    assert type_label("32012D0234R(01)", "Table of Contents") == "Decision"
    assert type_label("32001L0083", None) == "Directive"
    assert type_label("32018Q0217(01)", "Annex") == "Other"  # a letter with no rule: never left on the wrong file's type
    assert type_label("32018Q0217(01)", "Decision") == "Decision"
    assert type_label("21972A0722(05)", None) == "Other"  # sector 2: A is an agreement, not an opinion


def test_number_prefix_dropped():
    assert strip_number_prefix("2014/866/EU: Council Decision of 21 October 2014") == "Council Decision of 21 October 2014"
    assert strip_number_prefix("63/46/Euratom, 63/491/EEC: Decision of 10 July 1963") == "Decision of 10 July 1963"
    assert strip_number_prefix("2004/541/: 2004/541/EC:#Council Decision of 5 July 2004") == "Council Decision of 5 July 2004"
    assert strip_number_prefix("2004/619/ECCouncil Decision of 11 August 2004") == "Council Decision of 11 August 2004"
    assert strip_number_prefix("Regulation (EU) 2016/679 of the European Parliament") == "Regulation (EU) 2016/679 of the European Parliament"


def test_rdf_meta_reads_title_and_date(tmp_path):
    (tmp_path / U).mkdir()
    (tmp_path / U / "tree_non_inferred.rdf").write_text(
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:j.0="http://publications.europa.eu/ontology/cdm#">'
        '<rdf:Description><j.0:expression_uses_language rdf:resource="http://publications.europa.eu/resource/authority/language/FRA"/>'
        '<j.0:expression_title>Decision du Conseil</j.0:expression_title></rdf:Description>'
        '<rdf:Description><j.0:expression_uses_language rdf:resource="http://publications.europa.eu/resource/authority/language/ENG"/>'
        '<j.0:expression_title>Council  Decision\nof 2022</j.0:expression_title></rdf:Description>'
        '<rdf:Description><j.0:work_date_document>2022-11-25</j.0:work_date_document></rdf:Description></rdf:RDF>')
    assert rdf_meta(tmp_path, U) == {"title": "Council Decision of 2022", "date": "2022-11-25"}

"""The importer picks an act's main file by what it contains, never an annex page or the cover page (15 Oct 2026).

Keeping a row's earlier file on every import had left 7,352 rows on an ANNEX page and 2,849 filled from the cover
page: titled "ANNEX" or "Official Journal of the European Union", typed Annex or Table of Contents.
"""
import re
from types import SimpleNamespace

from backend.scripts.import_corpus_update import main_file, title_match, type_label

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


def test_a_corrigendum_takes_its_corr_file(tmp_path):
    c = _folder(tmp_path, {"L_2012121EN.01003801.xml": _x("ACT"), "L_2012121EN.01003802.xml": _x("CORR")})
    assert main_file(c, U, "32012D0234R(01)", lambda: None, TitleParser())[0].name == "L_2012121EN.01003802.xml"
    assert main_file(c, U, "32012D0234", lambda: None, TitleParser())[0].name == "L_2012121EN.01003801.xml"


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

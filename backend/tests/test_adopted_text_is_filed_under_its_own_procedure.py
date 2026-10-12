"""An adopted text is filed under its OWN procedure, never one it cites (12 Oct 2026).

Four adopted texts were filed under a procedure they only cite. The text is stored from
below its heading, where its own reference sits, so the first reference in the stored
text is a citation ("having regard to its resolution of ... (2023/2046(INI))"). One job
filled an empty procedure with that first reference; the job that reads it from EP Open
Data never looked at a row that already had one. The four resolutions were then served as
adopted with no link to their text and no text. Found by comparing every stored procedure
with OEIL: 673 agreed, 4 did not."""
import pathlib
import re

from scripts.backfill_texts_adopted_procedures import CONTRADICTED, REFILE, UNCONFIRMED, settle
from services.scrapers.texts_adopted_scraper import TextsAdoptedScraper

BACKEND = pathlib.Path(__file__).resolve().parents[1]
URL = "https://www.europarl.europa.eu/doceo/document/TA-10-2025-0076_EN.html"

# The real page's shape: the procedure box, the heading, then the text, which cites another.
BOX = ('<table><tr><td><span class="contents">Procedure : </span><a class="ring_ref_link" '
       'href="https://oeil.secure.europarl.europa.eu/oeil/popups/ficheprocedure.do?reference=2024/2052(INI)">'
       '2024/2052(INI)</a></td></tr></table>')
HEADING = ('<table><tr class="doc_title"><td>European Parliament resolution of 6 May 2025 on the control of '
           'the financial activities of the European Investment Bank (<a href="#">2024/2052(INI)</a>)</td></tr></table>')
BODY = ("<table><tr class='contents'><td><p>The European Parliament,</p><p>having regard to its resolution of "
        "28 February 2024 on the financial activities of the European Investment Bank "
        "(<a href='#'>2023/2046(INI)</a>), " + ("having regard to the annual report, " * 12) + "</p></td></tr></table>")


def _procedure(html):
    page = f"<html><body>{html}</body></html>"
    return TextsAdoptedScraper()._parse_detail_page(page, "P10_TA(2025)0076", URL).procedure_ref


def test_the_page_states_its_own_procedure_in_its_box():
    assert _procedure(BOX + HEADING + BODY) == "2024/2052(INI)"


def test_the_heading_states_it_where_there_is_no_box():
    assert _procedure(HEADING + BODY) == "2024/2052(INI)"


def test_a_cited_procedure_is_never_taken_for_the_text_s_own():
    # Neither the box nor the heading: the only reference on the page is a citation.
    assert _procedure(BODY) is None


def test_a_citation_placed_before_the_box_does_not_win_by_coming_first():
    assert _procedure("<p>See also 2023/2046(INI).</p>" + BOX + BODY) == "2024/2052(INI)"


def test_two_sources_must_agree_before_a_text_is_refiled():
    oeil = ["2024/2052(INI)"]
    assert settle("2023/2046(INI)", oeil, "2024/2052(INI)") == "2024/2052(INI)"
    # EP Open Data names a procedure OEIL does not list the text under: nothing is written.
    assert settle("2023/2046(INI)", oeil, "2022/0001(COD)") is None
    # EP Open Data has no answer: OEIL alone corrects nothing.
    assert settle("2023/2046(INI)", oeil, None) is None
    # EP Open Data confirms what is stored: nothing to do.
    assert settle("2023/2046(INI)", oeil, "2023/2046(INI)") is None
    assert settle("2023/2046(INI)", [], "2024/2052(INI)") is None


def test_a_text_oeil_lists_on_two_procedures_is_not_contradicted_by_the_other_one():
    # One vote can close two files (P10_TA(2025)0257: 2025/2195(INL) and 2025/0900(APP)).
    sql = str(CONTRADICTED)
    assert "HAVING NOT bool_or(l.procedure_ref = ta.procedure_ref)" in sql
    assert "procedure_ref IS NOT NULL" in sql


def test_the_by_hand_recheck_covers_the_texts_oeil_cannot_speak_for():
    # OEIL pages are held from 2024 on; a 2013 procedure adopted in 2024 has none. There
    # the second authority is the text's own page (P10_TA(2024)0022, P10_TA(2025)0268).
    sql = str(UNCONFIRMED)
    assert "NOT EXISTS" in sql and "oeil_procedures" in sql and "procedure_ref IS NOT NULL" in sql
    assert settle("2020/0264(COD)", ["2013/0186(COD)"], "2013/0186(COD)") == "2013/0186(COD)"
    # The page could not be read: EP Open Data alone corrects nothing.
    assert settle("2020/0264(COD)", [], "2013/0186(COD)") is None
    src = (BACKEND / "scripts" / "backfill_texts_adopted_procedures.py").read_text(encoding="utf-8")
    # A repeatable flag appends; nargs="+" would keep only the last one given.
    assert 'add_argument("--only", action="append"' in src


def test_refiling_clears_what_was_copied_from_the_wrong_procedure():
    sql = str(REFILE)
    for column in ("legislative_carriage_id = NULL", "rapporteur_name = NULL",
                   "rapporteur_mep_id = NULL", "committees = '{}'"):
        assert column in sql, column
    # Never a blind overwrite: only the row still holding the procedure that was checked.
    assert "procedure_ref = :old" in sql


def test_no_job_reads_a_procedure_out_of_the_stored_text():
    src = (BACKEND / "scripts" / "enrich_ep_texts_and_resolutions.py").read_text(encoding="utf-8")
    assert "SET procedure_ref" not in src


def test_one_job_owns_the_procedure_of_an_adopted_text():
    writers = sorted(
        p.name for p in (BACKEND / "scripts").glob("*.py")
        if re.search(r"UPDATE texts_adopted\b[^;]*?\bSET\b[^;]*?\bprocedure_ref\s*=\s*:",
                     p.read_text(encoding="utf-8", errors="ignore"), re.S))
    assert writers == ["backfill_texts_adopted_procedures.py"], writers

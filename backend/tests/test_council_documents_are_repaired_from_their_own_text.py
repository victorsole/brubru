"""Council register rows are corrected from the document's own text (14 Oct 2026).

The audit found 47 rows dated with a later meeting date instead of the date printed on
them, 4 undated, 22 titled with their bare reference, 21 working documents stored letter
by letter ("B r u s s e l s") and 31 texts cut at 200,000 characters."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from scripts import repair_council_documents as job
from services.scrapers import council_register as reg

NOTICE = ("CM 4133/26 1 EN Council of the European Union General Secretariat Brussels, 25 September 2026 "
          "CM 4133 /26 AGRI COMMUNICATION NOTICE OF MEETING AND PROVISIONAL AGENDA Contact: x Subject: "
          "Working Party on Genetic Resources Date: 14 October 2026 Time: 10:00 Venue: COUNCIL")
SPACED = "B r u s s e l s , 0 3 M a r c h 2 0 2 6 WK 3480/2026 INIT T h i s i s a p a p e r " * 3


def _row(ref="CM-4133-2026-INIT", title="Working Party on Genetic Resources", published=date(2026, 10, 14),
         body=NOTICE, meeting=None):
    return SimpleNamespace(id="00000000-0000-0000-0000-000000000001", external_id=ref, title=title,
                           published=published, html_content=body, meeting_date=meeting)


def _no_fetch(ref):
    raise AssertionError(f"{ref} should not be fetched again")


def test_a_meeting_date_stored_as_the_document_date_is_replaced_by_the_printed_one():
    p = job.plan_row(_row(), _no_fetch)
    assert p["published"] == date(2026, 9, 25)
    assert p["changes"] == {"published": date(2026, 9, 25), "meeting_date": "2026-10-14"}
    assert p["meta"] == {"meeting_date": "2026-10-14"}


def test_a_correct_row_is_left_alone():
    assert job.plan_row(_row(published=date(2026, 9, 25), meeting="2026-10-14"), _no_fetch) is None


def test_a_bare_reference_title_is_read_from_the_heading():
    body = ("CM 4604/26 1 EN Council of the European Union Brussels, 13 October 2026 CM 4604 /26 PTS A LIST OF "
            "ADOPTED 'A' ITEMS COUNCIL OF THE EUROPEAN UNION (General Affairs) ECCL, Luxembourg 13 October 2026")
    p = job.plan_row(_row("CM-4604-2026-INIT", "CM-4604-2026-INIT", date(2026, 10, 13), body, "2026-10-13"),
                     _no_fetch)
    assert p["changes"] == {"title": "List of adopted 'A' items: Council (General Affairs), 13 October 2026"}


def test_a_letter_spaced_text_is_read_again_and_kept_only_when_better():
    good = "Brussels, 03 March 2026 WK 3480/2026 INIT This is a paper intended for a specific community. " * 3
    p = job.plan_row(_row("WK-3480-2026-INIT", "Paper", date(2026, 3, 3), SPACED, None), lambda ref: good)
    assert p["body"] == good and p["changes"]["text"] == "letter-spaced"
    # A fetch that fails, or comes back no better, leaves the stored text as it was.
    assert job.plan_row(_row("WK-3480-2026-INIT", "Paper", date(2026, 3, 3), SPACED, None), lambda ref: None) is None
    assert job.plan_row(_row("WK-3480-2026-INIT", "Paper", date(2026, 3, 3), SPACED, None), lambda ref: SPACED) is None


def test_a_text_cut_at_the_old_cap_is_read_again_whole():
    cut = ("Brussels, 2 June 2025 " + "x" * 10 + " word") * 1
    cut = (cut + " " + "Annex text " * 30000)[:job.OLD_CAP]
    whole = cut + " The end of the annex." * 1000
    p = job.plan_row(_row("ST-9-2025-INIT", "Annex", date(2025, 6, 2), cut, None), lambda ref: whole)
    assert p["body"] == whole and p["changes"]["text"] == "cut at 200,000 characters"


def test_the_update_only_touches_a_row_still_holding_what_was_checked():
    sql = str(job.UPDATE)
    assert "title = :old_title" in sql and "published_date::date IS NOT DISTINCT FROM :old_published" in sql
    assert "md5(coalesce(html_content, '')) = md5(:old_body)" in sql


def test_the_fetcher_reads_a_letter_spaced_page_by_position():
    class Page:
        def __init__(self, plain, layout):
            self.plain, self.layout = plain, layout

        def extract_text(self, extraction_mode="plain"):
            return self.layout if extraction_mode == "layout" else self.plain
    spaced = Page("\n".join("Brussels, 03 March 2026 This is a paper"), "Brussels, 03 March 2026 This is a paper")
    normal = Page("The Council adopted the conclusions set out in the annex to this note today.", "unused")
    assert reg.letter_spaced(spaced.plain) and not reg.letter_spaced(normal.plain)
    assert reg._page_text(spaced) == "Brussels, 03 March 2026 This is a paper"
    assert reg._page_text(normal) == normal.plain


def test_a_subject_that_ran_on_is_cut_back_only_between_two_words():
    body = ("5003/25 1 JAI.1 LIMITE EN Council of the European Union Brussels, 20 December 2024 NOTE "
            "Subject: Use of Pyrotechnics by Criminals 5003/25 2 JAI.1 LIMITE EN 1. Introduction The use")
    ran_on = "Use of Pyrotechnics by Criminals 5003/25 2 JAI.1 LIMITE EN 1. Introduc"
    p = job.plan_row(_row("ST-5003-2025-INIT", ran_on, date(2024, 12, 20), body, None), _no_fetch)
    assert p["changes"] == {"title": "Use of Pyrotechnics by Criminals"}
    # A listing title longer than the parser's 400 characters is never cut mid-word.
    long_title = "Council Decision on " + "Germany, Estonia, Ireland, Croatia, " * 12
    body2 = "Brussels, 2 June 2026 Subject: " + long_title
    assert job.plan_row(_row("ST-10119-2026-ADD-2", long_title, date(2026, 6, 2), body2, None), _no_fetch) is None

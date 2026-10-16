"""An EP committee document is titled as its cover titles it (16 Oct 2026).

394 of 1,908 ep-documents were titled "draft_report for 2025/0267(NLE) (INTA)", 43 with an
empty slot ("draft_report for  (FEMM)"); the stored text's cover names each one."""
from api.v1.ep_entities import _enrich_doc_title, doc_title_from_text

COVER = ("﻿European Parliament 2024-2029 {FEMM}Committee on Women's Rights and Gender Equality 2026/2055(INI) "
         "{25/09/2026}25.9.2026 DRAFT REPORT on menopause beyond a health issue: turning menopause into an economic, "
         "working and social priority (2026/2055(INI)) {FEMM}Committee on Women's Rights and Gender Equality Rapporteur: Lina Gálvez")


def test_the_cover_gives_the_title():
    assert doc_title_from_text(COVER) == ("Draft report on menopause beyond a health issue: turning menopause into an "
                                          "economic, working and social priority")
    assert doc_title_from_text("no heading here") is None


def test_the_template_is_the_last_resort_and_has_no_empty_slot():
    assert _enrich_doc_title("draft_report for 2026/2055(INI) (FEMM)", "2026/2055(INI)", {}, COVER).startswith(
        "Draft report on menopause")
    assert _enrich_doc_title("draft_report for  (FEMM)", None, {}, None) == "draft_report (FEMM)"

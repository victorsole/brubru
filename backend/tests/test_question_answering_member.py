"""A question's answering_commissioner is the Member the answer names (16 Oct 2026).

5,833 answers read "European Commission" there although each says "Answer given by
Executive Vice-President Séjourné on behalf of the European Commission"."""
from __future__ import annotations

from scripts.backfill_parl_question_answers import answering_member_from_text
from scripts.backfill_question_answering_member import wanted


def test_the_member_is_read_from_the_answer():
    assert answering_member_from_text(
        "EN\nP-003585/2026\nAnswer given by Executive Vice-President Séjourné\non behalf of the European Commission\n"
    ) == "Executive Vice-President Séjourné"
    # The extracted text often loses the break before "on behalf".
    assert answering_member_from_text("ENE-004081/2025Answer given by Mr Šefčovičon behalf of the European Commission") \
        == "Mr Šefčovič"
    assert answering_member_from_text("Answer given by High Representative/Vice-President Kallas on behalf of the "
                                      "European Commission") == "High Representative/Vice-President Kallas"
    assert answering_member_from_text("Joint answer given by Mr Brunner and Mr McGrath on behalf of the Commission") \
        == "Mr Brunner and Mr McGrath"
    assert answering_member_from_text("Reply\nThe Council recalls that ...") is None


def test_an_institution_name_never_stands_for_a_member():
    assert wanted("European Commission", "Answer given by Ms Roswall on behalf of the European Commission") == "Ms Roswall"
    assert wanted("Council of the EU", "Reply\nThe Council recalls") is None
    assert wanted("Stéphane SÉJOURNÉ", "no named answer line") == "Stéphane SÉJOURNÉ"

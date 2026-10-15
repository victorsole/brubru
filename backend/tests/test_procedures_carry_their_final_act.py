"""A completed procedure carries the CELEX of its final act, as OEIL links it (15 Oct 2026).

celex_numbers was empty on 2,056 of 2,074 procedures GovClipping walked, 350 of them with
"Final act published in Official Journal" among their events; twelve declared fields were
empty on every row without saying so."""
from scripts.update_carriage_statuses_from_oeil import final_act_celex
from api.v1.procedures import ProcedureItem, _eurlex_of

PAGE = '''<a href="/oeil/en/procedure-file/pdf?reference=2023/0008(COD)&amp;section=FINAL_ACT">Final act</a>
</div><div class="es_links-list"><ul><li><p>
<a href="https://eur-lex.europa.eu/smartapi/cgi/sga_doc?smartapi!celexplus!prod!CELEXnumdoc&amp;lg=EN&amp;numdoc=32025R2458">
<span class="t-x">Regulation 2025/2458</span></a>'''


def test_the_final_act_is_read_after_its_section_marker():
    assert final_act_celex(PAGE) == ["32025R2458"]


def test_a_celex_before_the_final_act_section_is_not_taken():
    other = '<a href="https://eur-lex.europa.eu/x?smartapi!celexplus!prod!CELEXnumdoc&amp;lg=EN&amp;numdoc=32016R0679">'
    assert final_act_celex(other + "<p>no final act yet</p>") == []
    assert final_act_celex(None) == []


def test_the_legal_text_url_follows_the_celex():
    assert _eurlex_of(["32025R2458"]) == "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32025R2458"
    assert _eurlex_of([]) is None


def test_fields_never_filled_say_so():
    for f in ("timeline", "status_history", "eurlex_documents", "days_in_current_status", "expected_completion"):
        assert "Not filled for OEIL procedure files" in (ProcedureItem.model_fields[f].description or ""), f

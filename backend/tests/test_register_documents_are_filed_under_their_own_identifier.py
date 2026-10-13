"""A register document is filed under the identifier it states, never a neighbour's.

13 October 2026, found by comparing every row with what Cellar states for it:
  * 294 rows were corrigenda filed under the act they correct. The feed lists one as
    "CELEX:32011L0089R(02)"; the reader kept the digits before the R, so the row took the 2011
    directive's CELEX, then its date and its text. One (32011D0402(01)R(02), a corrigendum to the
    Parliament's rules on smoking) had become a Commission decision on seeds from Egypt.
  * 4 rows held a CELEX rebuilt from their reference where their own link states another:
    "SWD(2026) 50" gave 52026SC0050, an opinion of the Regulatory Scrutiny Board, and the staff
    working document (52026SC0050(01)) carried the opinion's text.
  * 1 row filed as SWD(2026) 133 is SEC(2026) 133."""
import datetime as dt
from types import SimpleNamespace

from scripts import refile_register_documents as job
from services.api_clients import commission_doc_register_client as client

LINK = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:"


def _row(i, reference, title="A real title", celex=None, link=None, date=None, doc_type="OJ"):
    return SimpleNamespace(id=i, reference=reference, title=title, celex=celex, portal_url=link,
                           publication_date=dt.datetime.fromisoformat(date) if date else None, doc_type=doc_type)


def _held(date):
    return {"dates": {date}, "titles": {"ENG": "x"}}


def test_a_title_that_is_a_corrigendum_s_celex_is_the_row_s_own_identifier():
    assert job.own_corrigendum("32011L0089", "CELEX:32011L0089R(02)") == "32011L0089R(02)"
    assert job.own_corrigendum("32024L2841", "CELEX:32024L2841R(01): Corrigendum to Directive (EU) 2024/2841") == "32024L2841R(01)"
    # The suffix before the R is part of it: 32011D0402 and 32011D0402(01) are different acts.
    assert job.own_corrigendum("32011D0402", "CELEX:32011D0402(01)R(02)") == "32011D0402(01)R(02)"
    # A proposal's later version arrives the same way.
    assert job.own_corrigendum("52025PC0435", "CELEX:52025PC0435R(01)") == "52025PC0435R(01)"
    assert job.own_corrigendum("32011L0089R(02)", "CELEX:32011L0089R(02)") is None   # already refiled
    assert job.own_corrigendum("32026D2285", "Council Decision (CFSP) 2026/2285 of 12 October 2026") is None
    assert job.own_corrigendum("32026D2285", "CELEX:32026D2285") is None             # not a corrigendum


def test_a_row_s_own_link_states_its_celex():
    assert job.own_link_celex("52026SC0050", LINK + "52026SC0050(01)") == "52026SC0050(01)"
    assert job.own_link_celex("52024SC0029", LINK + "52024SC0029R(02)") == "52024SC0029R(02)"
    assert job.own_link_celex("52026SC0702", LINK + "52026SC0702") is None
    assert job.own_link_celex(None, LINK + "52026SC0702") is None   # an empty cell is the fill-in's job
    assert job.own_link_celex("52026SC0702", None) is None


def test_the_series_is_the_one_cellar_states():
    assert job.own_number("SWD(2026) 133", ("SEC", "2026", "133")) == ("SEC(2026)133", "SEC")
    # A later version shares its reference with the first (SWD(2025) 1 final/2): not refiled.
    assert job.own_number("SWD(2025) 1", ("SWD", "2025", "1")) is None
    assert job.own_number("SWD(2026) 702", None) is None
    assert job.own_number("32026D2285", ("SEC", "2026", "1")) is None


def test_each_row_is_refiled_only_where_cellar_holds_what_it_states():
    rows = [
        _row(1, "32011L0089", "CELEX:32011L0089R(02)", celex="32011L0089", date="2011-11-16"),
        _row(2, "32015R0479", "CELEX:32015R0479R(03)", celex="32015R0479"),      # Cellar does not hold it
        _row(3, "SWD(2026) 50", celex="52026SC0050", link=LINK + "52026SC0050(01)", date="2026-02-13", doc_type="SWD"),
        _row(4, "SWD(2024) 29", celex="52024SC0029", link=LINK + "52024SC0029R(02)", date="2024-01-29", doc_type="SWD"),
        _row(5, "SWD(2026) 133", celex="52026SC0133", link=LINK + "52026SC0133", date="2026-04-30", doc_type="SWD"),
        _row(6, "SWD(2026) 702", celex="52026SC0702", link=LINK + "52026SC0702", doc_type="SWD"),
        _row(7, "32026D2285", "Council Decision (CFSP) 2026/2285", celex="32026D2285"),
    ]
    facts = {"32011L0089R(02)": _held("2026-10-08"), "52026SC0050(01)": _held("2026-02-13"),
             "52024SC0029R(02)": _held("2025-12-09")}
    numbers = {"52026SC0050": ("SEC", "2026", "50"), "52026SC0050(01)": ("SWD", "2026", "50"),
               "52024SC0029R(02)": ("SWD", "2024", "29"), "52026SC0133": ("SEC", "2026", "133"),
               "52026SC0702": ("SWD", "2026", "702")}
    todo = job.plan(rows, facts, numbers)
    assert todo["corrigendum"] == [{"rid": 1, "old": "32011L0089", "own": "32011L0089R(02)"}]
    assert todo["not_held_by_cellar"] == [{"reference": "32015R0479", "own": "32015R0479R(03)"}]
    assert todo["celex"] == [
        # The stored date is already this version's own: kept.
        {"rid": 3, "old": "52026SC0050", "own": "52026SC0050(01)", "reference": "SWD(2026) 50", "keep_date": True},
        # The stored date is the first version's: cleared and read again.
        {"rid": 4, "old": "52024SC0029", "own": "52024SC0029R(02)", "reference": "SWD(2024) 29", "keep_date": False},
    ]
    # SWD(2026) 50 is judged on its corrected CELEX: it is a staff working document, not the opinion.
    assert todo["number"] == [{"rid": 5, "old": "SWD(2026) 133", "own": "SEC(2026)133", "doc_type": "SEC", "was": "SWD"}]


def test_an_identifier_another_row_holds_is_never_given_twice():
    rows = [_row(1, "32011L0089", "CELEX:32011L0089R(02)", celex="32011L0089"),
            _row(2, "32011L0089R(02)", "Rectificare la Directiva 2011/89/UE", celex="32011L0089R(02)"),
            _row(3, "SWD(2026) 50", celex="52026SC0050", link=LINK + "52026SC0050(01)", doc_type="SWD"),
            _row(4, "SWD(2026) 51", celex="52026SC0050(01)", link=LINK + "52026SC0050(01)", doc_type="SWD"),
            _row(5, "SWD(2026) 133", celex="52026SC0133", doc_type="SWD"),
            _row(6, "SEC(2026)133", celex=None, doc_type="SEC")]
    todo = job.plan(rows, {"32011L0089R(02)": _held("2026-10-08"), "52026SC0050(01)": _held("2026-02-13")},
                    {"52026SC0133": ("SEC", "2026", "133")})
    assert todo["corrigendum"] == [] and todo["celex"] == [] and todo["number"] == []


def test_refiling_clears_what_was_read_under_the_wrong_identifier():
    sql = str(job.REFILE_CORRIGENDUM)
    for cleared in ("publication_date = NULL", "text_body = NULL", "body_html = NULL", "portal_url = NULL", "pdf_url = NULL"):
        assert cleared in sql, cleared
    assert "reference = :own" in sql and "celex = :own" in sql
    sql_b = str(job.REFILE_CELEX)
    assert "text_body = NULL" in sql_b and "body_html = NULL" in sql_b
    # Never a blind overwrite: only the row still holding the value that was checked.
    assert "reference = :old" in sql and "celex = :old" in sql_b and "reference = :old" in str(job.REFILE_NUMBER)


def test_the_feed_reader_files_a_corrigendum_under_its_own_celex():
    assert client.corrigendum_entry("CELEX:32011L0089R(02)") == ("32011L0089R(02)", "CELEX:32011L0089R(02)")
    assert client.corrigendum_entry("CELEX:32024L2841R(01): Corrigendum to Directive (EU) 2024/2841 of the European Parliament") \
        == ("32024L2841R(01)", "Corrigendum to Directive (EU) 2024/2841 of the European Parliament")
    assert client.corrigendum_entry("CELEX:32011D0402(01)R(02)") == ("32011D0402(01)R(02)", "CELEX:32011D0402(01)R(02)")
    assert client.corrigendum_entry("CELEX:52025PC0435R(01)") == ("52025PC0435R(01)", "CELEX:52025PC0435R(01)")
    assert client.corrigendum_entry("Council Decision (CFSP) 2026/2285 of 12 October 2026") is None
    assert client.corrigendum_entry("") is None


def test_the_cellar_reader_names_a_document_as_cellar_numbers_it():
    # 5YYYYSC numbers staff working documents and SEC documents alike.
    assert client.own_reference("52026SC0702", "SWD", "SWD") == ("SWD(2026) 702", "SWD")
    assert client.own_reference("52026SC0133", "SEC", "SWD") == ("SEC(2026)133", "SEC")
    assert client.own_reference("52025JC0135R(01)", "JOIN", "JOIN") == ("JOIN(2025) 135", "JOIN")
    # Cellar states no number: the series the query asked for, as before.
    assert client.own_reference("52026SC0702", None, "SWD") == ("SWD(2026) 702", "SWD")
    assert client.own_reference("52026SC0050(01)", "SWD", "SWD") == ("SWD(2026) 50", "SWD")

"""public_url for a legislative carriage, whichever register the row came from.

GovClipping walks /api/v2/legislative/oeil/procedures in full. Deriving public_url
from oeil_procedure_ref alone left 1,519 of 3,382 rows serving an empty contracted
datapoint, because the table holds three populations and only one of them is an OEIL
procedure file. These tests pin the fallback order and, as much as anything, pin the
refusal to invent an address for a row that has none.
"""
from types import SimpleNamespace

from api.v1.procedures import _public_url


def _row(**kw):
    base = {"oeil_procedure_ref": None, "celex_numbers": None, "url": None}
    base.update(kw)
    return SimpleNamespace(**base)


def test_oeil_reference_wins_over_everything_else():
    # A row carrying an OEIL reference is a procedure file first: that page is the
    # richer destination, so it must not be shadowed by a CELEX the row also has.
    r = _row(oeil_procedure_ref="2024/0079(COD)", celex_numbers=["32026D2103"],
             url="https://example.org/whatever")
    assert _public_url(r) == (
        "https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=2024/0079(COD)"
    )


def test_adopted_act_falls_back_to_its_celex_on_eurlex():
    r = _row(celex_numbers=["52026PC0146"])
    assert _public_url(r) == (
        "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:52026PC0146"
    )


def test_celex_url_is_the_canonical_form_not_the_stored_one():
    # The stored url is "..././legal-content/AUTO/?uri=CELEX:...", which carries a stray
    # "/./" and uses AUTO; opened in a browser it renders no extractable document. The
    # CELEX must therefore beat the stored url, not the other way round.
    r = _row(celex_numbers=["32026D2103"],
             url="https://eur-lex.europa.eu/./legal-content/AUTO/?uri=CELEX:32026D2103")
    got = _public_url(r)
    assert got == "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32026D2103"
    assert "/./" not in got and "AUTO" not in got


def test_legislative_train_row_uses_its_stored_page():
    u = "https://www.europarl.europa.eu/legislative-train/package-security-union/file-x"
    assert _public_url(_row(url=u)) == u


def test_blank_and_empty_celex_entries_are_skipped():
    r = _row(celex_numbers=["", "  ", "32019R1381"])
    assert _public_url(r).endswith("CELEX:32019R1381")


def test_empty_celex_list_falls_through_to_the_url():
    u = "https://www.europarl.europa.eu/legislative-train/file-y"
    assert _public_url(_row(celex_numbers=[], url=u)) == u


def test_a_row_with_no_address_returns_none_rather_than_a_substitute():
    # 41 carriages have no OEIL reference, no CELEX and no url. An empty field is
    # honest; a directory or search page presented as this file's address is not.
    assert _public_url(_row()) is None
    assert _public_url(_row(url="   ")) is None

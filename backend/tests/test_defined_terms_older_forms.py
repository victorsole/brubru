"""Older acts write their definitions in forms the parser could not read (5 Nov 2026).

REACH Article 3 has 41 points written "1. substance: means ...". The route answered one term, the only quoted one, nested inside
"polymer". Regulation 765/2008 says "shall mean" and answered none. Directives 2001/83 and 2000/31 use a colon alone, under a lead-in
that says the terms bear these meanings, and answered none. The text below is the acts' own, from their consolidated versions.
"""
from types import SimpleNamespace

from services.parsers import definition_store as store
from services.parsers.consolidated_xhtml import parse_consolidated_law
from services.parsers.definition_extractor import extract_definitions_map


def _article(number, text, title=""):
    heading = f'<div class="eli-title"><p class="stitle-article-norm">{title}</p></div>' if title else ""
    return (f'<div class="eli-subdivision" id="art_{number}"><p class="title-article-norm">Article {number}</p>{heading}'
            f'<p class="norm">{text}</p></div>')


def _terms(html):
    return extract_definitions_map(parse_consolidated_law(html))


REACH_ART3 = _article("3", (
    "For the purposes of this Regulation: 1. substance: means a chemical element and its compounds in the natural state; "
    "2. mixture &#9668; : means a mixture or solution composed of two or more substances; "
    "5. polymer: means a substance consisting of molecules. For the purpose of this definition a &#8216;monomer unit&#8217; means the "
    "reacted form of a monomer substance in a polymer; "
    "20. phase-in substance: means a substance which meets at least one of the following criteria: (a) it is listed in EINECS; (b) it was "
    "manufactured in the Community; "
    "25. registrant's own use: means an industrial or professional use by the registrant; "
    "41. alloy: means a metallic material, homogenous on a macroscopic scale."
), "Definitions")


def test_reach_a_bare_term_a_colon_and_means():
    terms = _terms(REACH_ART3)
    assert terms["substance"]["point"] == "1"
    assert terms["substance"]["definition"] == "a chemical element and its compounds in the natural state"
    assert terms["registrant's own use"]["point"] == "25"
    assert terms["alloy"]["definition"] == "a metallic material, homogenous on a macroscopic scale"
    assert "(b) it was manufactured" in terms["phase-in substance"]["definition"]


def test_the_closing_amendment_mark_is_not_part_of_a_term():
    terms = _terms(REACH_ART3)
    assert terms["mixture"]["definition"] == "a mixture or solution composed of two or more substances"
    assert not any("◄" in k or "◄" in v["definition"] for k, v in terms.items())


def test_a_word_after_the_closing_mark_keeps_its_first_letter():
    terms = _terms(_article("3", "1. alpha: means a thing ◄Mixture included; 2. beta: means another thing; 3. gamma: means a third thing"))
    assert terms["alpha"]["definition"] == "a thing Mixture included"


def test_a_quoted_term_nested_in_a_bare_definition_stays():
    terms = _terms(REACH_ART3)
    assert terms["polymer"]["point"] == "5"
    assert terms["monomer unit"]["definition"] == "the reacted form of a monomer substance in a polymer"


def test_regulation_765_2008_shall_mean_with_no_title():
    terms = _terms(_article("2", (
        "Definitions For the purposes of this Regulation the following definitions shall apply: "
        "3. &#8216;manufacturer&#8217; shall mean any natural or legal person who manufactures a product; "
        "4. &#8216;authorised representative&#8217; shall mean any natural or legal person established within the Community; "
        "5. &#8216;importer&#8217; shall mean any natural or legal person who places a product on the market."
    )))
    assert set(terms) == {"manufacturer", "authorised representative", "importer"}
    assert terms["importer"]["definition"].startswith("any natural or legal person who places")


def test_shall_mean_is_enough_to_find_the_article():
    terms = _terms(_article("4", (
        "For the purposes of this Regulation: 1. &#8216;alpha&#8217; shall mean a thing; 2. &#8216;beta&#8217; shall mean another thing; "
        "3. &#8216;gamma&#8217; shall mean a third thing."
    )))
    assert set(terms) == {"alpha", "beta", "gamma"}


def test_directive_2001_83_article_1_a_colon_under_the_lead_in():
    terms = _terms(_article("1", (
        "For the purposes of this Directive, the following terms shall bear the following meanings: "
        "2. Medicinal product : (a) Any substance or combination of substances presented as having properties for treating disease; or "
        "(b) Any substance which may be used in human beings; "
        "3. Substance: Any matter irrespective of origin; "
        "4. Immunological medicinal product: Any medicinal product consisting of vaccines, toxins, serums or allergen products."
    )))
    assert set(terms) == {"medicinal product", "substance", "immunological medicinal product"}
    assert terms["medicinal product"]["point"] == "2"
    assert "(b) Any substance which may be used" in terms["medicinal product"]["definition"]


def test_directive_2000_31_a_quoted_term_and_a_colon_under_the_lead_in():
    terms = _terms(_article("2", (
        "For the purpose of this Directive, the following terms shall bear the following meanings: "
        "(a) &#8216;information society services&#8217; : services within the meaning of Article 1(2) of Directive 98/34/EC; "
        "(b) &#8216;service provider&#8217; : any natural or legal person providing an information society service; "
        "(e) &#8216;consumer&#8217; : any natural person who is acting for purposes outside his trade."
    ), "Definitions"))
    assert set(terms) == {"information society services", "service provider", "consumer"}
    assert terms["service provider"]["point"] == "b"
    assert terms["consumer"]["definition"] == "any natural person who is acting for purposes outside his trade"


def test_a_colon_with_no_lead_in_is_not_a_definition():
    terms = _terms(_article("2", (
        "1. This Regulation applies to: (a) substances, which means chemical elements; "
        "2. Member States shall: (a) designate an authority; "
        "3. The Commission may: (a) adopt a guideline; "
        "4. The Agency shall: (a) publish a list."
    ), "Scope"))
    assert terms == {}


def test_a_number_inside_a_definition_does_not_cut_it_in_two():
    terms = _terms(_article("3", (
        "1. alpha: means a thing referred to in Article 3. 4. Such a thing includes others; "
        "2. beta: means another thing; 3. gamma: means a third thing; 4. delta: means a fourth thing"
    )))
    assert set(terms) == {"alpha", "beta", "gamma", "delta"}
    assert terms["alpha"]["definition"].endswith("Such a thing includes others")
    assert terms["delta"]["point"] == "4"


def test_a_deleted_point_leaves_a_gap_the_parser_crosses():
    terms = _terms(_article("3", "1. alpha: means a thing; 4. beta: means another thing; 5. gamma: means a third thing"))
    assert terms["beta"]["point"] == "4"


def test_quoted_points_read_as_they_did():
    terms = _terms(_article("3", (
        "For the purposes of this Regulation: 1. &#8216;food law&#8217; means the laws governing food; "
        "2. &#8216;food business&#8217; means any undertaking; 3. &#8216;feed&#8217; means any substance intended for animals; "
    ), "Definitions"))
    assert set(terms) == {"food law", "food business", "feed"}


def test_a_stored_answer_from_the_older_parser_is_read_again():
    """REACH's one-term answer is stored on production: it must not outlive this fix, and no script may be needed to clear it."""
    def reader(version):
        return SimpleNamespace(execute=lambda *a, **k: SimpleNamespace(first=lambda: ({"terms": {"x": {}}, "parser_version": version},)))
    assert store._read_consolidated(reader(2), "32006R1907", "02006R1907-20260622") is None
    assert store._read_consolidated(reader(store.CONSOLIDATED_PARSER_VERSION), "32006R1907", "02006R1907-20260622") is not None
    assert store.CONSOLIDATED_PARSER_VERSION >= 3

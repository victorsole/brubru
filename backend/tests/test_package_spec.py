"""Rules for a compliance package, pinned against the defects that motivated them.

Every rule in services/compliance/package_spec.py exists because a real package
shipped broken on 10 August 2026. Each test below names that package, so if a
rule is ever loosened the reason it existed is still on the record.

Pure logic, no database. Run: python3.12 -m pytest tests/test_package_spec.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.compliance.package_spec import (  # noqa: E402
    Finding, Package, from_dict, is_publishable, to_dict, validate,
)


def req(article="Article 1", text="Do the thing.", criticality="important",
        addressee="economic_operator", celex="32024R1689", deadline=None,
        interpretive=None, entity="Companies"):
    return {
        "article": article, "requirement_text": text, "criticality": criticality,
        "addressee": addressee, "law_celex": celex, "deadline": deadline,
        "interpretive": interpretive, "applicable_entity": entity,
    }


def pkg(requirements=None, laws=None, **kw):
    """A package that is healthy unless a test makes it otherwise."""
    reqs = requirements if requirements is not None else [
        req(article=f"Article {i}", text=f"Obligation number {i}.",
            deadline="2026-01-01" if i == 1 else None)
        for i in range(1, 13)
    ]
    return Package(
        id=kw.pop("id", 99),
        name=kw.pop("name", "Test Package"),
        laws=laws if laws is not None else [{"celex": "32024R1689", "title": "AI Act"}],
        requirements=reqs,
        **kw,
    )


def codes(findings):
    return {f.code for f in findings}


# --------------------------------------------------------------- baseline

def test_healthy_package_is_publishable():
    findings = validate(pkg())
    assert is_publishable(findings), [str(f) for f in findings]
    assert not [f for f in findings if f.severity == "error"]


# ----------------------------------------------------------------- errors

def test_no_binding_requirements():
    """Cluster 49 (Tirrenia): 14 requirements, all recitals, 0 analysable."""
    p = pkg(requirements=[req(article=f"Recital {i}", interpretive="true")
                          for i in range(1, 6)])
    assert "no_binding_requirements" in codes(validate(p))
    assert not is_publishable(validate(p))


def test_law_without_requirements():
    """Cluster 18 advertised the DSA and attached nothing to it."""
    p = pkg(laws=[{"celex": "32024R1689", "title": "AI Act"},
                  {"celex": "32022R2065", "title": "Digital Services Act"}])
    f = validate(p)
    assert "law_without_requirements" in codes(f)
    assert any("32022R2065" in (x.where or "") for x in f)


def test_article_label_too_long():
    """Caught during the cluster 17 rebuild by a truncated psycopg2 error."""
    p = pkg(requirements=[req(article="A" * 51)] + [req(article=f"Article {i}")
                                                    for i in range(2, 13)])
    assert "article_label_too_long" in codes(validate(p))


def test_entity_too_long():
    p = pkg(requirements=[req(entity="E" * 101)] + [req(article=f"Article {i}")
                                                    for i in range(2, 13)])
    assert "entity_too_long" in codes(validate(p))


def test_invalid_criticality():
    p = pkg(requirements=[req(criticality="high")] + [req(article=f"Article {i}")
                                                      for i in range(2, 13)])
    assert "invalid_criticality" in codes(validate(p))


def test_invalid_addressee():
    """An unknown addressee is read as a company duty by the analyser."""
    p = pkg(requirements=[req(addressee="the_pope")] + [req(article=f"Article {i}")
                                                        for i in range(2, 13)])
    assert "invalid_addressee" in codes(validate(p))


def test_orphan_requirement():
    p = pkg(requirements=[req(celex="32016R0679")] + [req(article=f"Article {i}")
                                                      for i in range(2, 13)])
    assert "orphan_requirement" in codes(validate(p))


def test_duplicate_requirement_keys_on_text_not_article():
    """The rule that was wrong twice.

    A package covering several acts legitimately repeats an article LABEL, and
    one article legitimately yields several distinct obligations. Only identical
    TEXT is double-counting. Verified against the corpus: 259 same-(law,article)
    groups exist and none share their text.
    """
    same_label_different_law = pkg(
        laws=[{"celex": "32024R1689", "title": "AI Act"},
              {"celex": "32016R0679", "title": "GDPR"}],
        requirements=[req(article="Article 2(1)", text="AI Act duty.", celex="32024R1689"),
                      req(article="Article 2(1)", text="GDPR duty.", celex="32016R0679")]
                     + [req(article=f"Article {i}", text=f"Other {i}.") for i in range(3, 13)])
    assert "duplicate_requirement" not in codes(validate(same_label_different_law))

    same_article_different_text = pkg(
        requirements=[req(article="Article 13", text="Keep documentation."),
                      req(article="Article 13", text="Log events automatically.")]
                     + [req(article=f"Article {i}", text=f"Other {i}.") for i in range(3, 13)])
    assert "duplicate_requirement" not in codes(validate(same_article_different_text))

    genuinely_duplicated = pkg(
        requirements=[req(article="Article 13", text="Keep documentation."),
                      req(article="Article 99", text="keep   DOCUMENTATION.")]
                     + [req(article=f"Article {i}", text=f"Other {i}.") for i in range(3, 13)])
    f = validate(genuinely_duplicated)
    assert "duplicate_requirement" in codes(f), "whitespace and case must not hide a duplicate"


def test_invalid_celex():
    p = pkg(laws=[{"celex": "not-a-celex", "title": "Something"}],
            requirements=[req(celex="not-a-celex") for _ in range(12)])
    assert "invalid_celex" in codes(validate(p))


def test_celex_accepts_two_letter_types():
    """Proposals use PC/DC/JC; a one-letter pattern silently drops them."""
    p = pkg(laws=[{"celex": "52026PC0321", "title": "A proposal"}],
            requirements=[req(article=f"Article {i}", text=f"Duty {i}.", celex="52026PC0321")
                          for i in range(1, 13)])
    assert "invalid_celex" not in codes(validate(p))


# --------------------------------------------------------------- warnings

def test_mostly_not_yours():
    """The threshold migration 210 used to unpublish four packages."""
    reqs = [req(article=f"Article {i}", text=f"Duty {i}.",
                addressee="member_state" if i <= 5 else "economic_operator")
            for i in range(1, 13)]
    assert "mostly_not_yours" in codes(validate(pkg(requirements=reqs)))


def test_everything_is_critical():
    """Cluster 17 marked all 19 of its requirements critical."""
    reqs = [req(article=f"Article {i}", text=f"Duty {i}.", criticality="critical")
            for i in range(1, 13)]
    assert "everything_is_critical" in codes(validate(pkg(requirements=reqs)))


def test_unmarked_recital():
    reqs = [req(article="Recital 71", text="Controllers should consider...")] + \
           [req(article=f"Article {i}", text=f"Duty {i}.") for i in range(2, 13)]
    assert "unmarked_recital" in codes(validate(pkg(requirements=reqs)))

    marked = [req(article="Recital 71", text="Controllers should consider...",
                  interpretive="true")] + \
             [req(article=f"Article {i}", text=f"Duty {i}.") for i in range(2, 13)]
    assert "unmarked_recital" not in codes(validate(pkg(requirements=marked)))


def test_corrigendum_as_source():
    """78 requirements hung off corrigendum rows."""
    p = pkg(laws=[{"celex": "32024R1689", "title": "AI Act"},
                  {"celex": "32024R90780", "title": "Corrigendum to Regulation (EU) 2024/2847"}],
            requirements=[req(article=f"Article {i}", text=f"Duty {i}.") for i in range(1, 13)]
                         + [req(article="Art X", text="Corrected duty.", celex="32024R90780")])
    assert "corrigendum_as_source" in codes(validate(p))


def test_single_case_decision():
    for name in ["Amazon State Aid Decision (Decision (EU) 2018/859)",
                 "China BEV Countervailing Duties (Reg 2024/2754)",
                 "Optical Fibre Cables China Anti-Dumping Duties"]:
        assert "single_case_decision" in codes(validate(pkg(name=name))), name
    assert "single_case_decision" not in codes(validate(pkg(name="AI Act Package")))


def test_thin_package():
    p = pkg(requirements=[req(article=f"Article {i}", text=f"Duty {i}.") for i in range(1, 5)])
    assert "thin_package" in codes(validate(p))


def test_warnings_do_not_block_publication():
    """Only errors block. A thin package is a judgement call, not a defect."""
    p = pkg(requirements=[req(article=f"Article {i}", text=f"Duty {i}.") for i in range(1, 5)])
    f = validate(p)
    assert "thin_package" in codes(f)
    assert is_publishable(f)


# ---------------------------------------------------------------- round trip

def test_dict_round_trip_preserves_findings():
    p = pkg()
    assert [str(x) for x in validate(from_dict(to_dict(p)))] == [str(x) for x in validate(p)]


def test_interpretive_survives_round_trip():
    p = pkg(requirements=[req(article="Article 99", interpretive="true")]
                         + [req(article=f"Article {i}", text=f"Duty {i}.") for i in range(1, 13)])
    back = from_dict(to_dict(p))
    assert len(back.binding()) == len(p.binding())

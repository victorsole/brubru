"""Review-profile rules: what a package may declare about its own table.

The dangerous failure here is silent. A half-declared profile that drops the
status column, or an extracted field the model invents a value for, both produce
a table that looks authoritative and is not. These tests pin the guards.

Run: python3.12 -m pytest tests/test_review_profile.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.compliance.review_profile import (  # noqa: E402
    BUILTIN_COLUMNS, MAX_EXTRACTED_CHARS, build_extraction_prompt,
    clean_extracted, default_profile, extracted_columns, validate_profile,
)


def prof(*columns):
    return {"columns": list(columns)}


def builtin(cid):
    return {"id": cid, "kind": "builtin"}


def extracted(cid, label="Label", prompt="the thing"):
    return {"id": cid, "kind": "extracted", "label": label, "prompt": prompt}


CORE = [builtin("status"), builtin("article"), builtin("obligation")]


# ------------------------------------------------------------------ defaults

def test_none_is_valid_and_means_default():
    assert validate_profile(None) == []
    assert extracted_columns(None) == []
    assert build_extraction_prompt(None) == ""


def test_default_profile_validates():
    assert validate_profile(default_profile()) == []
    assert len(default_profile()["columns"]) == len(BUILTIN_COLUMNS)


# ----------------------------------------------------------------- structure

def test_rejects_non_object_and_empty_columns():
    assert validate_profile([]) and validate_profile({"columns": []})
    assert validate_profile({"columns": "status"})


def test_required_columns_cannot_be_dropped():
    """A review without verdict, article or obligation cannot be read."""
    p = prof(builtin("status"), builtin("article"))
    problems = validate_profile(p)
    assert any("obligation" in x for x in problems)

    assert validate_profile(prof(*CORE)) == []


def test_unknown_builtin_rejected():
    p = prof(*CORE, builtin("vibes"))
    assert any("not a builtin" in x for x in validate_profile(p))


def test_duplicate_id_rejected():
    p = prof(*CORE, builtin("deadline"), builtin("deadline"))
    assert any("declared twice" in x for x in validate_profile(p))


def test_bad_id_shape_rejected():
    for bad in ["Status", "9lives", "has-dash", "", "x" * 41]:
        p = prof(*CORE, {"id": bad, "kind": "builtin"})
        assert validate_profile(p), bad


def test_extracted_needs_prompt_and_label():
    p = prof(*CORE, {"id": "threshold", "kind": "extracted"})
    problems = validate_profile(p)
    assert any("prompt" in x for x in problems)
    assert any("label" in x for x in problems)


def test_extracted_cannot_shadow_a_builtin():
    p = prof(*CORE, {"id": "deadline", "kind": "extracted",
                     "label": "Deadline", "prompt": "the date"})
    assert any("shadows a builtin" in x for x in validate_profile(p))


def test_column_and_extracted_limits():
    many = prof(*CORE, *[extracted(f"f{i}", prompt="x") for i in range(1, 6)])
    assert any("extracted columns" in x for x in validate_profile(many))

    wide = prof(*CORE, *[builtin(c) for c in BUILTIN_COLUMNS],
                *[extracted(f"g{i}") for i in range(1, 4)])
    assert validate_profile(wide)


# -------------------------------------------------------------------- prompt

def test_prompt_is_empty_without_extracted_columns():
    assert build_extraction_prompt(prof(*CORE)) == ""


def test_prompt_names_every_extracted_field_and_forbids_inference():
    p = prof(*CORE, extracted("substance", "Substance", "the restricted substance named"),
             extracted("threshold", "Threshold", "the concentration limit"))
    text = build_extraction_prompt(p)
    assert '"substance"' in text and '"threshold"' in text
    assert "the restricted substance named" in text
    assert "null" in text.lower()
    # The guard that keeps an empty cell empty.
    assert "Do NOT infer" in text


# ------------------------------------------------------------------ cleaning

def test_clean_keeps_only_declared_keys():
    p = prof(*CORE, extracted("substance"), extracted("threshold"))
    out = clean_extracted(p, {"substance": "Lead", "threshold": "0.1%",
                              "hallucinated": "made up"})
    assert out == {"substance": "Lead", "threshold": "0.1%"}


def test_clean_drops_empties_and_null_words():
    p = prof(*CORE, extracted("substance"))
    for value in [None, "", "   ", "null", "N/A", "not stated", "Unknown"]:
        assert clean_extracted(p, {"substance": value}) is None, value


def test_clean_drops_prose_non_answers():
    """A model asked for a field it cannot find answers in prose, not with null.

    All of these came out of the first production run of a profiled package and
    belong in an empty cell rather than in the table as though they were data.
    """
    p = prof(*CORE, extracted("applies_from"))
    for value in ["none stated", "Not explicitly stated in the requirement text",
                  "no specific date stated", "No date stated", "not specified",
                  "Not mentioned in the text", "none provided", "not applicable"]:
        assert clean_extracted(p, {"applies_from": value}) is None, value


def test_clean_keeps_real_values_that_start_like_a_non_answer():
    """The trap in the rule above: real content can open with None or Not."""
    p = prof(*CORE, extracted("applies_from"))
    for value in ["19 July 2026", "QR code", "0.1% by weight",
                  "None of the substances listed exceed the threshold",
                  "Not later than 12 months after entry into force",
                  "from the date of placing on the market"]:
        assert clean_extracted(p, {"applies_from": value}) == {"applies_from": value}, value


def test_clean_rejects_structures_and_truncates():
    p = prof(*CORE, extracted("substance"))
    assert clean_extracted(p, {"substance": {"nested": 1}}) is None
    assert clean_extracted(p, {"substance": ["a", "b"]}) is None
    long = clean_extracted(p, {"substance": "L" * 500})
    assert len(long["substance"]) == MAX_EXTRACTED_CHARS


def test_clean_coerces_numbers():
    p = prof(*CORE, extracted("threshold"))
    assert clean_extracted(p, {"threshold": 0.1}) == {"threshold": "0.1"}


def test_clean_returns_none_without_profile_or_bad_input():
    assert clean_extracted(None, {"x": "y"}) is None
    assert clean_extracted(prof(*CORE), {"x": "y"}) is None
    assert clean_extracted(prof(*CORE, extracted("a")), "not a dict") is None

"""Extracted text carries plain spaces where a PDF has non-breaking ones (16 Oct 2026).

API audit, step 2 (ECHA files): 10 contract award notices read "NUTS code Â  FI181",
pypdf's rendering of a Latin-1 non-breaking space, and 23 texts carried U+00A0.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.documents import text_extract as te  # noqa: E402


def test_non_breaking_spaces_become_spaces():
    # Runs of spaces are kept as they come (tables rely on spacing); only the characters change.
    assert te._clean("NUTS code Â\xa0 FI181\nII.1.3) The notice") == "NUTS code   FI181\nII.1.3) The notice"
    assert te._clean("a\xa0b") == "a b"
    assert "Â" not in te._clean("x Â\xa0y") and "\xa0" not in te._clean("x\xa0y")


def test_a_real_a_circumflex_is_kept():
    assert te._clean("Âne et château") == "Âne et château"

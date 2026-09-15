"""Em/en dash folding in chat answers (audit F1, 15 Sep 2026).

Brubru forbids em-dashes in user-facing text, so `_fold_prose_dashes` rewrites
them in every answer. Its single regex tried to spare numeric ranges with digit
lookarounds, but `\\s*` let a match start at the dash itself, so the lookbehind
saw a space and ranges were corrupted:

    "Week 38 (14 – 20 September 2026)" -> "Week 38 (14 ,  20 September 2026)"
    "The AI Act — adopted 2024 — applies" -> "The AI Act, adopted 2024 , applies"
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from services.ai_service import AIService  # noqa: E402


def fold(text: str) -> str:
    # The method only reads class-level regexes, so no service wiring is needed.
    return AIService._fold_prose_dashes(AIService.__new__(AIService), text)


@pytest.mark.parametrize(
    "src,expected",
    [
        # The two shipped defects.
        ("Week 38 (14 – 20 September 2026)", "Week 38 (14-20 September 2026)"),
        ("The AI Act — adopted 2024 — applies", "The AI Act, adopted 2024, applies"),
        # Numeric ranges, spaced or not, em or en dash.
        ("14–20 September", "14-20 September"),
        ("within 24–48h", "within 24-48h"),
        ("Articles 5—7", "Articles 5-7"),
        ("from 2024–2027", "from 2024-2027"),
        ("pages 10 — 12", "pages 10-12"),
        # Prose breaks.
        ("Brussels — the Council", "Brussels, the Council"),
        ("Brussels—the Council", "Brussels, the Council"),
        ("X — the Y — is Z", "X, the Y, is Z"),
        ("Week 38 — the plenary", "Week 38, the plenary"),
        ("the vote — 2026 will tell", "the vote, 2026 will tell"),
        # Debris.
        ("It was adopted — .", "It was adopted."),
        ("Already a comma, — then this", "Already a comma, then this"),
        ("(— aside)", "(aside)"),
        ("Title —", "Title"),
        # A leading dash is a bullet.
        ("— first point", "- first point"),
        ("  – nested point", "  - nested point"),
        # Nothing to do.
        ("no dashes at all", "no dashes at all"),
        ("", ""),
    ],
)
def test_fold(src, expected):
    assert fold(src) == expected


def test_no_em_or_en_dash_survives_in_prose():
    out = fold("A — b – c 1 – 2 3—4 d—e")
    assert "—" not in out and "–" not in out
    assert out == "A, b, c 1-2 3-4 d, e"


def test_structural_lines_are_untouched():
    src = "\n".join([
        "Intro — text",
        "```",
        "a — b  ,  c",
        "```",
        "| 14 – 20 | x — y |",
        "    indented — code",
        "See https://example.eu/a–b — here",
    ])
    out = fold(src).split("\n")
    assert out[0] == "Intro, text"
    assert out[2] == "a — b  ,  c"
    assert out[4] == "| 14 – 20 | x — y |"
    # `stripped` is lstripped before the 4-space check, so indented lines are
    # folded like prose (nested list items rely on that). Indentation is kept.
    assert out[5] == "    indented, code"
    assert out[6] == "See https://example.eu/a–b, here"


def test_only_folded_lines_get_debris_cleanup():
    src = "Line one — two\nkeep  double , spacing here"
    assert fold(src) == "Line one, two\nkeep  double , spacing here"


def test_markdown_hard_break_survives():
    assert fold("Brussels — the Council  \nnext") == "Brussels, the Council  \nnext"

"""Tender keywords match whole words (29 Sep 2026): "CER" inside "certified"
and "SME" inside "assessment" were matching, which put recycled paper in a
telecom association's feed once EU-institution notices without CPV codes arrived."""
import pytest

from services.tenders.matcher import _keyword_in


@pytest.mark.parametrize("kw,text,hit", [
    ("SME", "remote assessment of english language skills", False),
    ("SME", "open to smes and start-ups", True),
    ("CER", "certified recycled paper, concerning din a4", False),
    ("CER", "obligations under the cer directive", True),
    ("startup", "support to startups in europe", True),
    ("5G", "5g standalone networks", True),
    ("framework contract", "a single framework contract for cleaning", True),
    ("AI act", "compliance with the ai act", True),
    ("EIC", "the eic accelerator", True),
    ("EIC", "a scientific committee", False),
    ("", "anything", False),
])
def test_keyword_in(kw, text, hit):
    assert _keyword_in(kw, text) is hit

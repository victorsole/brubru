"""On the day of the vote the EN texts-adopted contents page links the PROVISIONAL text
in another language (TA-10-2026-0335_FR.html), so a text is first stored with a French
title. The date sync skips texts it already holds; a provisional one must be revisited
until the English version appears (8 Oct 2026), or the French title stays for good."""
from services.scrapers.texts_adopted_sync_service import _is_non_english


def test_a_non_english_doceo_text_is_provisional():
    assert _is_non_english("https://www.europarl.europa.eu/doceo/document/TA-10-2026-0335_FR.html")
    assert _is_non_english("https://www.europarl.europa.eu/doceo/document/TA-10-2026-0335_DE.pdf")


def test_an_english_or_missing_url_is_not_provisional():
    assert not _is_non_english("https://www.europarl.europa.eu/doceo/document/TA-10-2026-0335_EN.html")
    assert not _is_non_english("https://www.europarl.europa.eu/doceo/document/TA-10-2026-0104_EN.pdf")
    assert not _is_non_english(None)
    assert not _is_non_english("")

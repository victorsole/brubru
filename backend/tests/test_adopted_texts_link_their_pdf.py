"""Every adopted text links its PDF (15 Oct 2026: 576 of 763 had none)."""
from api.v1.texts_adopted import TextItem, _ta_pdf


def test_the_pdf_follows_the_reference():
    assert _ta_pdf("P10_TA(2025)0268") == "https://www.europarl.europa.eu/doceo/document/TA-10-2025-0268_EN.pdf"
    assert _ta_pdf("P9_TA(2022)0129") == "https://www.europarl.europa.eu/doceo/document/TA-9-2022-0129_EN.pdf"
    assert _ta_pdf("TA-10-2025-0268") is None and _ta_pdf(None) is None


def test_fields_never_filled_say_so():
    assert "Not filled" in TextItem.model_fields["rapporteur_mep_id"].description
    assert "Not filled" in TextItem.model_fields["related_documents"].description

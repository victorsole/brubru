"""A procedure's text_type follows its OEIL type: NLE is non-legislative (16 Oct 2026)."""
from models.legislative_train import TextTypeEnum
from services.scrapers.oeil_sync_service import text_type_for


def test_types():
    assert text_type_for("2025/0058(COD)") is TextTypeEnum.LEGISLATIVE
    assert text_type_for("2026/0004(NLE)") is TextTypeEnum.NON_LEGISLATIVE
    assert text_type_for("2025/2089(INI)") is TextTypeEnum.NON_LEGISLATIVE
    assert text_type_for("2024/0123(CNS)") is TextTypeEnum.LEGISLATIVE
    assert text_type_for("SWD(2026)0283") is None

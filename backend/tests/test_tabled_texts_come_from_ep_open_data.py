"""Every report and motion tabled in plenary, dated, from EP Open Data (15 Oct 2026).

plenary-tabled-texts held 46 texts since July 2024 (the 'texts submitted' page lists one
session) and none carried a document_date."""
from datetime import date

from scripts import sync_plenary_tabled_texts as job

REPORT = {
    "identifier": "A-10-2025-0001", "document_date": "2025-01-17",
    "title_dcterms": {"en": "REPORT on the draft Council directive as regards VAT rules for the digital age"},
    "is_realized_by": [{"language": "http://publications.europa.eu/resource/authority/language/ENG",
                        "title_alternative": {"en": "REPORT - ... - (15159/2024 - C10-0170/2024 - 2022/0407(CNS)) - "
                                                     "Committee on Economic and Monetary Affairs - Rapporteur: Ľudovít Ódor"},
                        "is_embodied_by": [{"format": "http://publications.europa.eu/resource/authority/file-type/PDF",
                                            "is_exemplified_by": "distribution/reds_iPlRp/A-10-2025-0001/A-10-2025-0001_en.pdf"}]}],
    "workHadParticipation": [
        {"id": "eli/dl/participation/A-10-2025-0001-257010", "participation_role": "def/ep-roles/RAPPORTEUR",
         "participation_in_name_of": "org/ECON"},
        {"id": "eli/dl/participation/A-10-2025-0001-ECON", "participation_role": "def/ep-roles/AUTHOR",
         "participation_in_name_of": "org/ECON"}],
}


def test_a_report_is_dated_with_its_procedure_rapporteur_and_committee():
    row = job.describe(REPORT)
    assert row["ref"] == "A10/2025/0001" and row["day"] == date(2025, 1, 17)
    assert row["proc"] == "2022/0407(CNS)" and row["rapporteur"] == "Ľudovít Ódor" and row["mep"] == "257010"
    assert row["committees"] == ["ECON"]
    assert row["pdf"] == "https://data.europarl.europa.eu/distribution/reds_iPlRp/A-10-2025-0001/A-10-2025-0001_en.pdf"
    assert row["html"] == "https://www.europarl.europa.eu/doceo/document/A-10-2025-0001_EN.html"


def test_a_motions_author_is_a_group_not_a_committee():
    motion = dict(REPORT, identifier="B-10-2025-0265",
                  workHadParticipation=[{"id": "x-ECR", "participation_role": "def/ep-roles/AUTHOR",
                                         "participation_in_name_of": "org/ECR"}])
    row = job.describe(motion)
    assert row["ref"] == "B10/2025/0265" and row["committees"] == []


def test_the_write_never_blanks_text_or_committees():
    sql = str(job.UPSERT)
    assert "length(coalesce(EXCLUDED.full_text, '')) >= 500" in sql
    assert "cardinality(EXCLUDED.committees) > 0" in sql
    assert "document_date = EXCLUDED.document_date" in sql

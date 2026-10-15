"""EPRS authors, policy areas and PDF come from the Think Tank record page (15 Oct 2026).

GovClipping's /parliament/eprs served authors empty on 870 of 871 Think Tank publications:
the sync reads the RSS, which carries no author, and nothing read the record page."""
from __future__ import annotations

import inspect

from scripts import enrich_eprs_records as job


def _section(label: str, *values: str) -> str:
    items = "".join(f'<li><a href="#"><svg></svg><span class="t-x">{v}</span></a></li>' for v in values)
    return (f'<div><h5 class="es_title-h5 mb-2 pb-2 border-bottom">{label}</h5>'
            f'<div class="es_links-list"><ul>{items}</ul></div></div>')


PAGE = ("<main>"
        + _section("Publication type", "Briefing")
        + _section("Author", "GHIRAN-MERVEILLE Anda-Diana", "SCHWARCZ Andr&aacute;s")
        + _section("Policy area", "Economics and Monetary Issues", "Public Health")
        + '<a href="https://www.europarl.europa.eu/RegData/etudes/BRIE/2026/784064/ECTI_BRI(2026)784064_FR.pdf">FR</a>'
        + '<a href="https://www.europarl.europa.eu/RegData/etudes/BRIE/2026/784064/ECTI_BRI(2026)784064_EN.pdf">EN</a>'
        + "</main>")


def test_each_section_gives_its_own_values():
    got = job.parse_record(PAGE)
    assert got["authors"] == ["GHIRAN-MERVEILLE Anda-Diana", "SCHWARCZ András"]
    assert got["areas"] == ["Economics and Monetary Issues", "Public Health"]
    # The English PDF, not the first listed.
    assert got["pdf"].endswith("ECTI_BRI(2026)784064_EN.pdf")


def test_a_record_in_several_languages_gives_the_english_pdf_from_its_picker():
    page = ("<main>" + _section("Author", "SAULNIER Jerome Leon")
            + '<select><option value="DE" data-auto-open-link="https://www.europarl.europa.eu/RegData/etudes/ATAG/2025/767194/EPRS_ATA(2025)767194_DE.pdf">DE</option>'
            + '<option value="EN" data-auto-open-link="https://www.europarl.europa.eu/RegData/etudes/ATAG/2025/767194/EPRS_ATA(2025)767194_EN.pdf">EN</option></select>'
            + "</main>")
    assert job.parse_record(page)["pdf"].endswith("EPRS_ATA(2025)767194_EN.pdf")


def test_a_record_naming_no_author_gives_none():
    page = "<main>" + _section("Policy area", "Environment") + _section("Geographical area", "Ukraine") + "</main>"
    got = job.parse_record(page)
    assert got["authors"] == [] and got["areas"] == ["Environment"] and got["pdf"] is None


def test_only_empty_fields_are_written():
    sql = str(job.STORE)
    assert "coalesce(pdf_url, :pdf)" in sql
    assert "WHEN coalesce(cardinality(authors), 0) = 0" in sql
    assert "WHEN coalesce(cardinality(policy_areas), 0) = 0" in sql


def test_the_record_reader_and_the_text_job_run_after_the_eprs_sync():
    from api import cron
    src = inspect.getsource(cron.cron_sync_warm_12h)
    sync, records, text = (src.index(k) for k in
                           ("sync_eprs_publications.py", "enrich_eprs_records.py", "backfill_eprs_full_text.py"))
    assert sync < records < text

"""RSB opinions come from the Commission's register and their own PDF (15 Oct 2026).

GovClipping's /commission/rsb-opinions held 44 opinions, the latest from August 2022:
the scraper read the Board's evaluation page only, never the register, where the
opinions on impact assessments are filed as SEC documents of type OPIN_IMPACT_ASSESS."""
from __future__ import annotations

import datetime as dt

import pytest

from scripts import sync_rsb_register_opinions as job

# The opening of SEC(2026) 780 as PyMuPDF extracts it.
OPINION = """EUROPEAN COMMISSION
19.06.2026
SEC(2026) 780
REGULATORY SCRUTINY BOARD OPINION
{COM(2026) 780}
{SWD(2026) 785-786-787}
 Impact assessment / European Product Act - update on the rules
on standardisation
This opinion concerns a draft impact assessment which may differ from the final version.
EUROPEAN COMMISSION
REGULATORY SCRUTINY BOARD
Brussels,
RSB
Opinion
Title: Impact assessment / European Product Act - update on the rules
on standardisation
Overall opinion: POSITIVE
(A) Policy context
The standardisation regulation organises the functioning of the European Standardisation System.
(B) Key issues
The Board notes the additional information provided by lead Service(s).
The Board gives a positive opinion.
(C) What to improve
(1) The report should draw on additional evidence.
"""


def test_the_opinion_gives_its_own_date_title_reference_and_verdict():
    got = job.parse_opinion(OPINION)
    assert got["day"] == dt.date(2026, 6, 19)  # the Board's date, not the register's 6 October
    assert got["title"] == "Impact assessment / European Product Act - update on the rules on standardisation"
    assert got["initiative"] == "European Product Act - update on the rules on standardisation"
    assert got["com"] == (2026, 780)
    assert got["verdict"] == "positive"
    assert got["summary"].startswith("The Board notes the additional information")
    assert "What to improve" not in got["summary"]


@pytest.mark.parametrize("line,verdict", [
    ("Overall opinion: POSITIVE WITH RESERVATIONS\n", "positive_with_reservations"),
    ("Overall opinion: NEGATIVE\n", "negative"),
    ("Overall opinion: POSITIVE\n", "positive"),
    ("no verdict printed", "unknown"),
])
def test_each_verdict_the_board_prints(line, verdict):
    assert job.verdict_of(line) == verdict


def test_a_resubmission_takes_the_latest_verdict_and_names_the_earlier_one():
    # SEC(2026)70 prints the second opinion first and the first opinion after it.
    text = (OPINION.replace("Overall opinion: POSITIVE", "Overall 2nd opinion: POSITIVE WITH RESERVATIONS")
            + "\nRSB\nOpinion\nTitle: Impact assessment / European Product Act - update on the rules\n"
              "on standardisation\nOverall opinion: NEGATIVE\n(A) Policy context\n")
    got = job.parse_opinion(text)
    assert got["verdict"] == "positive_with_reservations"
    assert got["summary"].startswith("Resubmitted:") and "(negative)" in got["summary"]


def test_a_document_bundling_several_assessments_says_so():
    text = OPINION + "\nTitle: Impact assessment / European partnership for clean hydrogen\nOverall opinion: NEGATIVE\n"
    got = job.parse_opinion(text)
    assert got["verdict"] == "positive"
    assert got["summary"].startswith("This document holds the Board's opinions on 2 impact assessments")


def test_an_opinion_without_a_verdict_line_keeps_its_title():
    # The 2025 MFF opinions were issued "without qualification": no verdict line.
    text = OPINION.replace("Overall opinion: POSITIVE\n", "")
    got = job.parse_opinion(text)
    assert got["verdict"] == "unknown"
    assert got["title"] == "Impact assessment / European Product Act - update on the rules on standardisation"


@pytest.mark.parametrize("title,kind", [
    ("Impact assessment / Digital Networks Act", "impact_assessment"),
    ("Fitness check of EU consumer law", "fitness_check"),
    ("Evaluation of the Single Market Programme", "evaluation"),
])
def test_the_kind_follows_the_title(title, kind):
    assert job.kind_of(title) == kind


def test_a_register_entry_gives_reference_department_and_the_pdf():
    doc = {"type": "OPIN_IMPACT_ASSESS", "date": "2026-10-06T00:00:00.000+0000", "reference": "SEC(2026)780",
           "responsibleDepartment": "GROW",
           "url": "https://ec.europa.eu/transparency/documents-register/detail?ref=SEC(2026)780",
           "attachments": [{"main": True, "original": "en", "linguisticVersions": {
               "en": {"ersId": "090166e5349f2c6f", "title": "Opinion of the Regulatory Scrutiny Board"}}}]}
    e = job.entry(doc)
    assert e["ref"] == "SEC(2026)780" and e["dg"] == "GROW" and e["listed"] == dt.date(2026, 10, 6)
    assert e["pdf"].endswith("/api/files/SEC(2026)780?ersIds=090166e5349f2c6f")


def test_the_procedure_is_looked_up_by_the_proposal_oeil_lists():
    got = job.procedure_params((2026, 780))
    # OEIL writes the proposal with a four-digit number: COM(2026)0780.
    assert got == {"event": '[{"reference": "COM(2026)0780"}]', "celex": "52026PC0780"}


def test_the_register_job_runs_with_the_rsb_scraper():
    from services.sync.source_registry import sources_for_tier
    keys = [s.key for s in sources_for_tier("warm")]
    assert "rsb_register_opinions" in keys

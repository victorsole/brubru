"""`creation_date` must be the row's first sighting, never its last update.

Measured 16 Oct 2026 by sending GovClipping's morning requests twice, 14 hours apart:
`creation_date` had moved on 4,696 parliamentary questions, 141 tabled texts, 112 votes,
100 adopted texts and 75 TRIS notifications that had merely been re-fetched. The
database had not moved: `first_seen` / `created_at` are pinned by the change trigger. The
routes copied `last_updated` (or `updated_at`) into `creation_date`, so a client could not
tell a new row from an old one, and every re-fetch looked like a fresh document.

The mapping helpers are called directly with plain rows, so the test holds whatever the
database contains; a route-level check per endpoint sits in the live suite.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from api.v1._row_dates import row_created, row_updated

FIRST = datetime(2026, 9, 23, 11, 31, 32)
LATER = datetime(2026, 10, 16, 7, 53, 51)


def _row(**kw):
    base = dict(first_seen=FIRST, scraped_at=LATER, last_updated=LATER)
    base.update(kw)
    return SimpleNamespace(**base)


class TestTheHelper:
    def test_first_seen_wins(self):
        assert row_created(_row()) == FIRST

    def test_created_at_when_the_table_spells_it_so(self):
        r = SimpleNamespace(created_at=FIRST, updated_at=LATER, scraped_at=LATER)
        assert row_created(r) == FIRST

    def test_creation_date_is_the_economy_spelling(self):
        assert row_created({"creation_date": FIRST, "updated_at": LATER}) == FIRST

    def test_never_falls_back_to_a_change_or_scrape_stamp(self):
        r = SimpleNamespace(last_updated=LATER, updated_at=LATER, scraped_at=LATER)
        assert row_created(r) is None

    def test_none_row(self):
        assert row_created(None) is None

    def test_created_and_updated_are_different_questions(self):
        r = _row()
        assert row_created(r) == FIRST and row_updated(r) == LATER


class TestParliamentaryQuestions:
    def test_creation_date_is_first_seen_not_last_updated(self):
        from api.v1.w4_endpoints import _parl_q_to_item
        r = _row(id="q1", question_reference="E-000001/2026", question_type="written",
                 parliamentary_term=10, subject="S", text_question="Q" * 50, text_answer=None,
                 submitted_date=FIRST.date(), answered_date=None, asking_mep_ids=[], asking_mep_names=[],
                 answering_institution=None, answering_commissioner=None, committees=[], procedure_ref=None,
                 related_celex=[], policy_areas=[], source_url="https://www.europarl.europa.eu/x", answer_url=None)
        item = _parl_q_to_item(r)
        assert item.creation_date == FIRST
        assert item.updated_date == LATER


class TestTRIS:
    def test_creation_date_is_first_seen_not_last_updated(self):
        from api.v1.w4_endpoints import _tris_to_item
        r = _row(id="t1", notification_number="2026/0001/BE", notifying_country="BE", title="T",
                 short_summary=None, full_text_summary=None, notification_date=FIRST.date(),
                 standstill_until=None, sector=None, products_or_services=None, main_content=None,
                 commission_observations_url=None, member_state_observations=None, detailed_opinions=None,
                 source_url="https://technical-regulation-information-system.ec.europa.eu/en/notification/1",
                 pdf_url=None, policy_areas=[], related_celex=[])
        item = _tris_to_item(r)
        assert item.creation_date == FIRST
        assert item.updated_date == LATER


class TestAdoptedAndTabledTexts:
    def test_creation_date_is_first_seen_not_last_updated(self):
        from api.v1.texts_adopted import _row_to_item
        r = _row(id="a1", ta_reference="P10_TA(2026)0001", title="T", description=None, text_type="other",
                 procedure_ref=None, parliamentary_term=10, adoption_date=FIRST, committees=[],
                 rapporteur_name=None, rapporteur_mep_id=None, celex_number=None, vote_results=None,
                 related_documents=None, source_url="https://www.europarl.europa.eu/doceo/x",
                 full_text_url=None, pdf_url=None, full_text=None, document_date=FIRST.date())
        item = _row_to_item(r)
        assert item.creation_date == FIRST
        assert item.updated_date == LATER


class TestVotes:
    def test_rollcall_creation_date_is_created_at_not_updated_at(self):
        from api.v1.ep_entities import _rollcall_to_item
        r = SimpleNamespace(id="v1", vote_key="k", level="plenary", procedure_ref="2026/0001(COD)",
                            carriage_id=None, report_ref="A10-0001/2026", ta_reference=None, title="T",
                            subject="Final vote", committee_code="ENVI", vote_date=FIRST.date(),
                            sitting_date=FIRST.date(), item_number=None, result="ADOPTED", votes_for=1,
                            votes_against=0, votes_abstention=0, vote_type="rcv", group_breakdown=None,
                            country_breakdown=None, total_records=1, source_url="https://www.europarl.europa.eu/x",
                            scraped_at=LATER, created_at=FIRST, updated_at=LATER)
        item = _rollcall_to_item(r)
        assert item.creation_date == FIRST
        assert item.updated_date == LATER

    def test_ep_vote_creation_date_is_created_at_not_updated_at(self):
        from api.v1.ep_entities import _vote_row_to_item
        r = SimpleNamespace(id="v2", htv_id=None, timestamp=FIRST, display_title="T", reference=None,
                            description=None, amendment_subject=None, amendment_number=None, is_main=True,
                            procedure_reference=None, procedure_title=None, procedure_type=None,
                            procedure_stage="plenary", count_for=1, count_against=0, count_abstention=0,
                            count_did_not_vote=0, result="ADOPTED", texts_adopted_reference=None,
                            created_at=FIRST, updated_at=LATER)
        item = _vote_row_to_item(r)
        assert item.creation_date == FIRST
        assert item.updated_date == LATER


class TestWebstreams:
    def test_creation_date_is_first_seen_not_last_updated(self):
        from api.v1.webstreams import _row_to_item
        r = SimpleNamespace(id="w1", committee_code="AFET", title="AFET Committee Meeting", meeting_date=FIRST,
                            multimedia_url="https://multimedia.europarl.europa.eu/en/x", video_url=None,
                            event_id="x", language="EN", duration_seconds=None, speaker_count=None,
                            word_count=None, status="pending", related_procedure_refs=[], transcribed_at=None,
                            transcript_text=None, first_seen=FIRST, last_updated=LATER)
        item = _row_to_item(r)
        assert item.creation_date == FIRST
        assert item.updated_date == LATER


class TestTheSourceNoLongerCopiesTheChangeStamp:
    """A grep guard beside the behavioural tests: the pattern that caused the bug must not
    come back under another name."""

    @pytest.mark.parametrize("path", ["api/v1/w4_endpoints.py", "api/v1/texts_adopted.py",
                                      "api/v1/ep_entities.py", "api/v1/webstreams.py", "api/v1/eprs.py"])
    def test_no_mapping_serves_last_updated_as_creation_date(self, path):
        import pathlib
        src = pathlib.Path(__file__).resolve().parents[1].joinpath(path).read_text()
        for bad in ("creation_date=r.last_updated", "creation_date=r.updated_at",
                    "creation_date=vote.updated_at",
                    'creation_date=getattr(r, "last_updated", None)'):
            assert bad not in src, f"{path} still maps {bad}"

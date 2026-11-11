"""O243 (11 Nov 2026): committee meetings were 'PENDING' for ever and the job said success.

No committee meeting has been transcribed since June 2026: the European Parliament's video
service refuses downloads of its recordings (403 on 283 of 284 audio segments of a meeting
of 12 Oct, measured 11 Nov). /parliament/webstreams answered 374 such meetings as PENDING
with five lines of metadata for a body, and the job that registers meetings, which never
transcribes, recorded `success` 344 times.

Now each item says whether it has a transcript and, in words, why not; it carries the agenda
of its own sitting where Brubru can tie exactly one to it; and the job reports the number of
meetings held without a transcript as `degraded`.
"""
import datetime as dt
import importlib
import json
from types import SimpleNamespace

import pytest

from api.v1 import webstreams as ws
from services import committee_meeting_agenda as agenda

TODAY = dt.date(2026, 11, 11)


def _sitt(title):
    return {"type": {"code": "SITT", "value": "1"}, "title": title, "number": None}


def _item(number, title, procedure=None):
    return {"type": None, "title": title, "number": number, "procedure_ref": procedure}


MORNING = [_sitt("10 November 2026, 09.00 - 12.45"), _item(1, "Adoption of agenda"),
           _item(3, " First file ", "2099/0001(COD)")]
TWO_SITTINGS = MORNING + [_sitt("10 November 2026, 14.30 - 18.30"), _item(7, "Afternoon hearing"),
                          _sitt("11 November 2026, 09.00 - 10.00"), _item(9, "Next day")]


# ---- reading the webstream and the agenda ---------------------------------------------

def test_a_webstream_starts_when_its_event_id_says():
    assert agenda.meeting_start("test-committee-meeting_20261110-0930-COMMITTEE-TEST_vd") == (dt.date(2026, 11, 10), 570)
    assert agenda.meeting_start("no-date-here") is None and agenda.meeting_start(None) is None
    assert agenda.meeting_start("x_20261340-0930-COMMITTEE-TEST_vd") is None          # not a date


def test_the_sitting_is_the_one_that_starts_when_the_webstream_starts():
    day = dt.date(2026, 11, 10)
    assert agenda.sitting_items(TWO_SITTINGS, day, 9 * 60) == [
        {"number": 1, "title": "Adoption of agenda", "procedure_refs": []},
        {"number": 3, "title": "First file", "procedure_refs": ["2099/0001(COD)"]}]
    assert [i["title"] for i in agenda.sitting_items(TWO_SITTINGS, day, 14 * 60 + 30)] == ["Afternoon hearing"]
    assert [i["title"] for i in agenda.sitting_items(TWO_SITTINGS, dt.date(2026, 11, 11), 9 * 60)] == ["Next day"]


def test_a_webstream_that_starts_inside_a_sitting_is_that_sitting():
    assert [i["number"] for i in agenda.sitting_items(TWO_SITTINGS, dt.date(2026, 11, 10), 9 * 60 + 15)] == [1, 3]


def test_a_sitting_that_starts_at_the_webstreams_time_wins_over_one_that_merely_contains_it():
    overlapping = MORNING + [_sitt("10 November 2026, 10.00 - 11.00"), _item(5, "Hearing inside the morning")]
    assert [i["number"] for i in agenda.sitting_items(overlapping, dt.date(2026, 11, 10), 10 * 60)] == [5]


def test_a_day_with_one_sitting_is_that_sitting_and_several_without_a_match_are_none():
    day = dt.date(2026, 11, 10)
    assert [i["number"] for i in agenda.sitting_items(MORNING, day, 13 * 60)] == [1, 3]      # the only sitting that day
    assert agenda.sitting_items(TWO_SITTINGS, day, 13 * 60) == []                            # between two: no guess
    assert agenda.sitting_items(TWO_SITTINGS, day, None) == []
    assert agenda.sitting_items(MORNING, dt.date(2026, 11, 12), 9 * 60) == []                # another day
    assert agenda.sitting_items([_item(1, "No sitting marker")], day, 9 * 60) == []
    assert agenda.sitting_items(None, day, 9 * 60) == [] and agenda.sitting_items(["x"], day, 9 * 60) == []


def test_a_marker_that_is_not_a_date_never_lends_its_items_to_the_sitting_before():
    items = MORNING + [_sitt("Coordinators' meeting"), _item(20, "In camera")]
    assert [i["number"] for i in agenda.sitting_items(items, dt.date(2026, 11, 10), 9 * 60)] == [1, 3]


def test_a_committee_meeting_reads_its_own_agenda_and_a_joint_one_the_joint_agenda():
    day, own, joint = dt.date(2026, 11, 10), MORNING, [_sitt("10 November 2026, 09.00 - 09.30"), _item(1, "Joint vote")]
    agendas = [("TEST(2026)1110_1", own), ("CJ05(2026)1110_1", joint)]
    single = agenda.pick_sitting(agendas, "TEST", "test-committee-meeting_20261110-0900-COMMITTEE-TEST_vd", day, 540)
    both = agenda.pick_sitting(agendas, "TEST", "test-othr-committee-meeting_20261110-0900-COMMITTEE-OTHR-TEST_vd", day, 540)
    assert [i["title"] for i in single] == ["Adoption of agenda", "First file"]
    assert [i["title"] for i in both] == ["Joint vote"]


def test_the_same_agenda_published_twice_is_one_and_two_different_ones_are_none():
    day, event = dt.date(2026, 11, 10), "test-committee-meeting_20261110-0900-COMMITTEE-TEST_vd"
    twice = [("TEST(2026)1110_1", MORNING), ("TEST(2026)1110_1P", MORNING)]
    assert len(agenda.pick_sitting(twice, "TEST", event, day, 540)) == 2
    other = [_sitt("10 November 2026, 09.00 - 10.00"), _item(1, "Something else")]
    assert agenda.pick_sitting(twice + [("TEST(2026)1110_2", other)], "TEST", event, day, 540) == []
    assert agenda.pick_sitting([("OTHR(2026)1110_1", MORNING)], "TEST", event, day, 540) == []   # another body's agenda
    assert agenda.pick_sitting([], "TEST", event, day, 540) == []


# ---- the reason, in words --------------------------------------------------------------

def test_why_there_is_no_transcript():
    note = agenda.transcript_note
    assert note(True, "EP", dt.date(2026, 10, 12), TODAY) is None
    assert note(False, "EP", dt.date(2026, 11, 16), TODAY) == agenda.NOTE_NOT_HELD
    assert note(False, "EP", TODAY, TODAY) == agenda.NOTE_NOT_HELD                    # today may still be running
    assert note(False, "EP", dt.date(2026, 10, 12), TODAY) == agenda.NOTE_CLOSED
    assert note(False, None, dt.date(2026, 6, 9), TODAY) == agenda.NOTE_CLOSED
    assert note(False, "EP", dt.date(2026, 6, 8), TODAY) == agenda.NOTE_NONE          # before the recordings closed
    assert note(False, "COUNCIL", dt.date(2026, 10, 12), TODAY) == agenda.NOTE_NONE   # not Parliament's video service
    assert note(False, "EP", None, TODAY) == agenda.NOTE_NONE
    assert "does not allow its recordings to be downloaded" in agenda.NOTE_CLOSED


# ---- the item --------------------------------------------------------------------------

def _row(**over):
    base = dict(id="11111111-1111-1111-1111-111111111111", committee_code="TEST",
                title="TEST Committee Meeting - 12 October 2026", meeting_date=dt.datetime(2026, 10, 12),
                multimedia_url="https://multimedia.europarl.europa.eu/en/test_vd", video_url=None,
                event_id="test-committee-meeting_20261012-1500-COMMITTEE-TEST_vd", language="en",
                duration_seconds=None, speaker_count=None, word_count=None, status="PENDING",
                related_procedure_refs=[], transcribed_at=None, last_updated=dt.datetime(2026, 11, 1),
                first_seen=dt.datetime(2026, 10, 1), transcript_text=None, institution="EP", agenda_items=[])
    return SimpleNamespace(**{**base, **over})


def test_a_meeting_held_without_a_transcript_says_why_in_its_fields_and_its_body():
    item = ws._row_to_item(_row(), today=TODAY)
    assert item.transcript_available is False and item.transcript_note == agenda.NOTE_CLOSED
    import html
    assert item.body_txt.endswith("\n" + agenda.NOTE_CLOSED) and f"<p>{html.escape(agenda.NOTE_CLOSED)}</p>" in item.body_html
    assert "Status: PENDING" in item.body_txt                                       # the stored status is still shown
    assert item.agenda_items == [] and "Agenda of this sitting" not in item.body_txt


def test_the_sittings_agenda_is_in_the_item_and_in_its_body():
    item = ws._row_to_item(_row(agenda_items=[
        {"number": 1, "title": "Adoption of agenda", "procedure_refs": []},
        {"number": 3, "title": "First <file>", "procedure_refs": ["2099/0001(COD)"]},
        {"number": None, "title": "Any other business"}, {"title": "  "}, "not an item"]), today=TODAY)
    assert [a["title"] for a in item.agenda_items] == ["Adoption of agenda", "First <file>", "Any other business"]
    assert item.agenda_items[2]["procedure_refs"] == []
    assert "Agenda of this sitting:\n1. Adoption of agenda\n3. First <file> (2099/0001(COD))\n- Any other business" in item.body_txt
    assert "<li>First &lt;file&gt; (2099/0001(COD))</li>" in item.body_html and item.body_html.count("<li>") == 3


def test_a_meeting_with_a_transcript_has_no_note_and_keeps_its_transcript_as_body():
    item = ws._row_to_item(_row(status="COMPLETED", transcript_text="The Chair opened the meeting.\nSecond line."), today=TODAY)
    assert item.transcript_available is True and item.transcript_note is None
    assert "Transcript:\nThe Chair opened the meeting." in item.body_txt and "No transcript" not in item.body_txt


def test_a_meeting_not_held_yet_says_that():
    item = ws._row_to_item(_row(meeting_date=dt.datetime(2026, 11, 16)), today=TODAY)
    assert item.transcript_note == agenda.NOTE_NOT_HELD and "has not been held" in item.body_txt


def test_the_documentation_no_longer_promises_a_transcript_on_demand():
    v2 = importlib.import_module("api.v2.parliament.webstreams")
    for module in (ws, v2):
        for route in module.router.routes:
            text = route.description or ""
            assert "fires on-demand" not in text
            assert "does not allow its recordings to be downloaded" in text and "transcript_note" in text
    fields = ws.WebstreamItem.model_fields
    assert {"transcript_available", "transcript_note", "agenda_items"} <= set(fields)


# ---- the job ---------------------------------------------------------------------------

class _Session:
    """Answers the three statements of the module with canned rows and records the writes."""

    def __init__(self, meetings, agendas, gap=(0, None)):
        self.meetings, self.agendas, self.gap, self.writes, self.asked, self.commits = meetings, agendas, gap, [], [], 0

    def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        self.asked.append((sql, dict(params or {})))
        if sql.startswith("SELECT id, committee_code"):
            return SimpleNamespace(fetchall=lambda: list(self.meetings))
        if sql.startswith("SELECT meeting_reference, items"):
            return SimpleNamespace(fetchall=lambda: list(self.agendas.get(params["c"], [])))
        if sql.startswith("UPDATE committee_meeting_transcripts"):
            self.writes.append(dict(params))
            return SimpleNamespace()
        if sql.startswith("SELECT count(*) FILTER"):
            return SimpleNamespace(one=lambda: SimpleNamespace(held_without=self.gap[0], last_transcribed=self.gap[1]))
        raise AssertionError(sql)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def close(self):
        pass


def _meeting(i, committee, event_id, refs=None):
    return SimpleNamespace(id=i, committee_code=committee, meeting_date=dt.datetime(2026, 11, 10),
                           event_id=event_id, related_procedure_refs=refs or [])


def test_each_meeting_is_given_the_agenda_of_its_own_sitting_and_only_when_there_is_one():
    session = _Session(
        [_meeting("a", "TEST", "test-committee-meeting_20261110-0900-COMMITTEE-TEST_vd"),
         _meeting("b", "TEST", "test-committee-meeting_20261110-1300-COMMITTEE-TEST_vd"),      # between two sittings
         _meeting("c", "NONE", "none-committee-meeting_20261110-0900-COMMITTEE-NONE_vd")],     # no agenda held
        {"TEST": [SimpleNamespace(meeting_reference="TEST(2026)1109_1", items=TWO_SITTINGS)]})
    assert agenda.attach_agendas(session, today=TODAY) == 1 and session.commits == 1
    (write,) = session.writes
    assert write["i"] == "a" and write["r"] == ["2099/0001(COD)"]
    assert [x["title"] for x in json.loads(write["a"])] == ["Adoption of agenda", "First file"]
    select, update = session.asked[0][0], next(s for s, _ in session.asked if s.startswith("UPDATE"))
    assert "= 'EP'" in select and "<> 'PLENARY'" in select and "agenda_items::text IN ('[]', 'null')" in select
    assert "agenda_items::text IN ('[]', 'null')" in update                         # never over an agenda already there
    assert "array_length(related_procedure_refs, 1), 0) = 0" in update              # nor over procedures already there
    lookups = [p for s, p in session.asked if s.startswith("SELECT meeting_reference")]
    assert lookups[0]["d1"] == dt.date(2026, 11, 10) and lookups[0]["d0"] == dt.date(2026, 11, 6)


def test_nothing_to_attach_writes_and_commits_nothing():
    session = _Session([_meeting("c", "NONE", "none-committee-meeting_20261110-0900-COMMITTEE-NONE_vd")], {})
    assert agenda.attach_agendas(session, today=TODAY) == 0 and session.writes == [] and session.commits == 0


def test_the_gap_counts_parliament_committee_meetings_already_held():
    session = _Session([], {}, gap=(372, dt.datetime(2026, 6, 8)))
    assert agenda.transcript_gap(session, today=TODAY) == {"held_without": 372, "last_transcribed": dt.date(2026, 6, 8)}
    sql, params = session.asked[0]
    assert "meeting_date < :t" in sql and params["t"] == TODAY and "= 'EP'" in sql and "<> 'PLENARY'" in sql


@pytest.fixture
def job(monkeypatch):
    script = importlib.import_module("scripts.sync_committee_transcripts")
    state = {"gap": (372, dt.datetime(2026, 6, 8)), "attach": 3}
    monkeypatch.setattr(script, "SessionLocal", lambda: _Session([], {}, gap=state["gap"]))

    def _attach(session):
        if isinstance(state["attach"], Exception):
            raise state["attach"]
        return state["attach"]
    monkeypatch.setattr(agenda, "attach_agendas", _attach)
    return script, state


def test_the_job_reports_the_meetings_without_a_transcript_as_degraded(job, capsys):
    script, _ = job
    assert script.report_what_is_missing() == 0
    line = next(l for l in capsys.readouterr().out.splitlines() if l.startswith("[SYNC_STATUS] degraded:"))
    assert "372 committee meeting(s) held without a transcript" in line and "08 Jun 2026" in line
    assert "does not allow its recordings to be downloaded" in line and "3 agenda(s) attached" in line


def test_with_every_meeting_transcribed_the_job_is_a_plain_success(job, capsys):
    script, state = job
    state["gap"] = (0, dt.datetime(2026, 11, 10))
    assert script.report_what_is_missing() == 0 and "[SYNC_STATUS]" not in capsys.readouterr().out


def test_agendas_that_cannot_be_attached_fail_the_run(job, capsys):
    script, state = job
    state["attach"] = RuntimeError("no such table")
    assert script.report_what_is_missing() == 1 and "[ERROR] agendas could not be attached" in capsys.readouterr().out


def test_a_discovery_that_fails_exits_non_zero_and_a_good_one_goes_on_to_report(job, monkeypatch):
    script, _ = job
    monkeypatch.setattr(script.sys, "argv", ["sync_committee_transcripts.py"])
    for returned, expected in ((-1, 1), (0, 0), (1, 0), (7, 0)):
        async def _discover(**k):
            return returned
        monkeypatch.setattr(script, "discover_meetings", _discover)
        with pytest.raises(SystemExit) as stop:
            script.main()
        assert stop.value.code == expected


def test_the_job_ends_with_what_the_report_says(job, monkeypatch):
    script, state = job
    state["attach"] = RuntimeError("no such table")
    monkeypatch.setattr(script.sys, "argv", ["sync_committee_transcripts.py"])

    async def _discover(**k):
        return 2
    monkeypatch.setattr(script, "discover_meetings", _discover)
    with pytest.raises(SystemExit) as stop:
        script.main()
    assert stop.value.code == 1                       # the report ran, and its failure is the run's


def test_a_failed_discovery_returns_minus_one(monkeypatch):
    import inspect
    script = importlib.import_module("scripts.sync_committee_transcripts")
    source = inspect.getsource(script.discover_meetings)
    assert "return -1" in source and "return 1\n" not in source

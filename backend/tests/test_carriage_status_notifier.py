"""Tests for the carriage status notifier (audit, 25 August 2026).

Brubru had 613 tracked legislative files and had never sent a single
notification about any of them. These tests pin the three behaviours that stop
the fix from being worse than the bug:

1. A track with no baseline is SEEDED, never notified. Without this, switching
   the feature on fires hundreds of notifications at once about changes that
   happened before anyone was watching.
2. Status comparison is case- and Enum-insensitive. `current_status` is an Enum
   column whose `.value` is lowercase while the raw column is uppercase; a
   mismatch here means "always changed", i.e. a notification for every file for
   every user every night.
3. A failing run reports the failure and does not look like a quiet night.

They exercise the decision logic against in-memory doubles, so they run without
a database and cannot pass merely because the DB happened to be empty.

Run: cd backend && python3.12 -m pytest tests/test_carriage_status_notifier.py -v
"""

import enum
import uuid

import pytest

from services.notifications.carriage_status_notifier import (
    CarriageStatusNotifier,
    NotifierRun,
    _norm,
    _prose,
)


class _StatusEnum(str, enum.Enum):
    """Mirrors the shape of the real CarriageStatusEnum: str subclass, lowercase value."""
    CLOSE_TO_ADOPTION = "close_to_adoption"
    IN_COMMITTEE = "in_committee"
    COMPLETED = "completed"


class _Carriage:
    def __init__(self, status, title="A tracked file", ref="2025/0385(COD)"):
        self.id = uuid.uuid4()
        self.current_status = status
        self.title = title
        self.short_title = title
        self.oeil_procedure_ref = ref


class _Track:
    def __init__(self, carriage, baseline=None):
        self.id = uuid.uuid4()
        self.user_id = uuid.uuid4()
        self.carriage_id = carriage.id
        self.last_notified_status = baseline
        self.last_notified_at = None
        self.notify_on_status_change = True
        self.archived_at = None


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def join(self, *a, **k):
        return self

    def filter(self, *a, **k):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    """Records what would be written, so tests assert on persisted effects."""

    def __init__(self, rows, commit_raises=False):
        self._rows = rows
        self.added = []
        self.committed = False
        self.rolled_back = False
        self._commit_raises = commit_raises

    def query(self, *a, **k):
        return _FakeQuery(self._rows)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        if self._commit_raises:
            raise RuntimeError("connection reset")
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def _run(rows, **kw):
    db = _FakeSession(rows)
    return CarriageStatusNotifier(db).run(**kw), db


class TestNormalisation:
    """The load-bearing helper: both sides of the comparison go through it."""

    def test_enum_and_raw_string_normalise_to_the_same_value(self):
        assert _norm(_StatusEnum.CLOSE_TO_ADOPTION) == _norm("CLOSE_TO_ADOPTION")
        assert _norm(_StatusEnum.CLOSE_TO_ADOPTION) == _norm("close_to_adoption")

    def test_none_and_blank_are_none(self):
        assert _norm(None) is None
        assert _norm("") is None
        assert _norm("   ") is None

    def test_the_lowercase_enum_value_does_not_read_as_a_change(self):
        """The storm case: enum read vs uppercase stored baseline."""
        carriage = _Carriage(_StatusEnum.CLOSE_TO_ADOPTION)
        track = _Track(carriage, baseline="CLOSE_TO_ADOPTION")
        run, db = _run([(track, carriage)])
        assert run.notifications_created == 0
        assert run.unchanged == 1
        assert db.added == []


class TestBaselineSeeding:

    def test_a_track_with_no_baseline_is_never_notified(self):
        carriage = _Carriage(_StatusEnum.COMPLETED)
        track = _Track(carriage, baseline=None)
        run, db = _run([(track, carriage)])
        assert run.notifications_created == 0
        assert run.skipped_no_baseline == 1
        assert db.added == []

    def test_seeding_fills_the_baseline_without_notifying(self):
        carriage = _Carriage(_StatusEnum.COMPLETED)
        track = _Track(carriage, baseline=None)
        run, db = _run([(track, carriage)], seed_baseline=True)
        assert run.baselines_seeded == 1
        assert run.notifications_created == 0
        assert db.added == []
        assert track.last_notified_status == "COMPLETED"

    def test_seeding_stores_the_normalised_form(self):
        carriage = _Carriage(_StatusEnum.IN_COMMITTEE)
        track = _Track(carriage, baseline=None)
        _run([(track, carriage)], seed_baseline=True)
        assert track.last_notified_status == track.last_notified_status.upper()


class TestChangeDetection:

    def test_a_real_change_creates_one_notification_and_moves_the_baseline(self):
        carriage = _Carriage(_StatusEnum.COMPLETED)
        track = _Track(carriage, baseline="IN_COMMITTEE")
        run, db = _run([(track, carriage)])
        assert run.notifications_created == 1
        assert len(db.added) == 1
        assert track.last_notified_status == "COMPLETED"
        assert track.last_notified_at is not None

    def test_a_second_run_after_a_change_is_quiet(self):
        carriage = _Carriage(_StatusEnum.COMPLETED)
        track = _Track(carriage, baseline="IN_COMMITTEE")
        _run([(track, carriage)])
        run2, db2 = _run([(track, carriage)])
        assert run2.notifications_created == 0
        assert run2.unchanged == 1
        assert db2.added == []

    def test_the_message_carries_no_institutional_codes(self):
        carriage = _Carriage(_StatusEnum.COMPLETED, title="Green claims directive")
        track = _Track(carriage, baseline="IN_COMMITTEE")
        _, db = _run([(track, carriage)])
        note = db.added[0]
        for code in ("(COD)", "CELEX", "COM(", "2025/0385"):
            assert code not in note.title, f"{code} leaked into the title"
            assert code not in note.message, f"{code} leaked into the message"
        # the reference is still available, in metadata and the link
        assert note.notif_metadata["oeil_procedure_ref"] == "2025/0385(COD)"

    def test_a_decisive_status_is_high_priority(self):
        carriage = _Carriage(_StatusEnum.COMPLETED)
        track = _Track(carriage, baseline="IN_COMMITTEE")
        _, db = _run([(track, carriage)])
        assert db.added[0].priority == "high"

    def test_an_ordinary_status_is_normal_priority(self):
        carriage = _Carriage(_StatusEnum.IN_COMMITTEE)
        track = _Track(carriage, baseline="TABLED")
        _, db = _run([(track, carriage)])
        assert db.added[0].priority == "normal"

    def test_dry_run_persists_nothing(self):
        carriage = _Carriage(_StatusEnum.COMPLETED)
        track = _Track(carriage, baseline="IN_COMMITTEE")
        run, db = _run([(track, carriage)], dry_run=True)
        assert run.notifications_created == 1     # it reports what it WOULD do
        assert db.added == []                      # but writes nothing
        assert db.rolled_back is True
        assert track.last_notified_status == "IN_COMMITTEE"


class TestSilenceIsNotSuccess:

    def test_a_failed_commit_is_reported_and_the_counts_are_not_claimed(self):
        carriage = _Carriage(_StatusEnum.COMPLETED)
        track = _Track(carriage, baseline="IN_COMMITTEE")
        db = _FakeSession([(track, carriage)], commit_raises=True)
        run = CarriageStatusNotifier(db).run()
        assert not run.ok
        assert run.errors, "a failed commit must leave a trace"
        assert run.notifications_created == 0, (
            "nothing landed, so the run must not report having created anything"
        )

    def test_the_summary_names_every_counter(self):
        run = NotifierRun(tracks_examined=3, notifications_created=1, unchanged=2)
        for key in ("examined", "created", "seeded", "unchanged",
                    "skipped_no_baseline", "errors"):
            assert key in run.summary()


class TestProse:

    @pytest.mark.parametrize("status,expected", [
        ("COMPLETED", "has completed its passage"),
        ("CLOSE_TO_ADOPTION", "is close to adoption"),
        ("ADOPTED", "has been adopted"),
    ])
    def test_known_statuses_read_as_english(self, status, expected):
        assert _prose(status) == expected

    def test_an_unknown_status_still_reads_as_english_not_as_a_code(self):
        out = _prose("SOME_NEW_STAGE")
        assert "_" not in out
        assert out.startswith("is now at")

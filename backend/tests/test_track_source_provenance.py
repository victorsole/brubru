"""Migration 230: every tracking row must say who created it.

Guards the defect found by /users on 10 September 2026: 755 of 932 non-internal
tracked items (81%) were OUR writes -- dormant-claim provisioning and the
Policy-Interest auto-populate -- and nothing in the row said so, so previous runs
counted them as user engagement. The largest holding on the platform (111 items)
was written in exactly two minutes and its owner had tracked nothing.

These tests are static: they read the schema and the source tree. They deliberately
do NOT hit the database with writes, so they run anywhere.
"""
import pathlib
import re

import pytest

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
BACKEND = pathlib.Path(_REPO_ROOT) / "backend"

TRACK_MODELS = {
    "UserCarriageTrack": "models.legislative_train",
    "UserCommissionDocTrack": "models.commission_document",
    "UserCommitteeWorkTrack": "models.committee_work",
    "UserConsultationTrack": "models.public_consultation",
    "UserTextAdoptedTrack": "models.text_adopted",
    "UserVoteTrack": "models.ep_voting",
}

# Writers that create rows on the user's behalf. Each MUST stamp 'provisioned'.
# Derived from the audit in the 10 Sep 2026 session; kept as an explicit list so a
# NEW provisioning script that forgets the stamp shows up as an unlisted writer in
# test_no_unaudited_write_paths below rather than passing silently.
PROVISIONING_WRITERS = [
    "services/tracking/tracked_files_seeder.py",
    "scripts/dormant_claim_provision.py",
    "scripts/seed_efpia_public_affairs_demo.py",
    "scripts/archive_dpp_laws_for_terraqui.py",
    "scripts/seed_jgonzalez_clerens.py",
    "scripts/seed_jmp_acm.py",
    "scripts/seed_ddevant_efpia.py",
    "scripts/seed_ferrmed_demo.py",
    "scripts/rebuild_terraqui_profile.py",
    "scripts/add_industrial_accelerator_act.py",
]

# User-action endpoints. These correctly omit `source` and rely on the DB default
# 'user'. Listed so that adding a new one is a deliberate act.
USER_ACTION_FILES = [
    "api/commission_documents.py",
    "api/committee_work.py",
    "api/legislative_train.py",
    "api/positions.py",
    "api/public_consultations.py",
    "api/texts_adopted.py",
]


@pytest.mark.parametrize("cls_name,module", sorted(TRACK_MODELS.items()))
def test_model_declares_source_nullable_with_user_default(cls_name, module):
    """Three states. NULL must stay reachable: pre-migration rows have unknown
    provenance and stamping them 'user' would hard-code the false reading."""
    mod = __import__(module, fromlist=[cls_name])
    col = getattr(mod, cls_name).__table__.c.source
    assert col.nullable is True, f"{cls_name}.source must stay nullable (NULL = unknown)"
    assert col.server_default is not None, f"{cls_name}.source needs the server default"
    assert "user" in str(col.server_default.arg)


def test_migration_does_not_backfill_history():
    """ADD COLUMN ... DEFAULT in PostgreSQL 11+ rewrites every existing row. The
    migration must add the column bare and SET DEFAULT afterwards, or all historic
    rows get stamped 'user' -- exactly the defect this column exists to remove."""
    sql = (BACKEND / "migrations" / "230_user_tracks_source.sql").read_text(encoding="utf-8")
    add_lines = [l for l in sql.splitlines() if "ADD COLUMN IF NOT EXISTS source" in l]
    assert add_lines, "migration 230 must add the source column"
    for line in add_lines:
        assert "DEFAULT" not in line.upper(), (
            "ADD COLUMN must NOT carry a DEFAULT -- it would backfill history. "
            f"Offending line: {line.strip()}"
        )
    assert "ALTER COLUMN source SET DEFAULT 'user'" in sql, (
        "the default must be set in a separate statement so it applies to new rows only"
    )


# Writers held outside git. `scripts/dormant_claim_provision.py` is gitignored
# (.gitignore:131) because it carries prospect data, so it is absent on a fresh
# clone and in CI. The test SKIPS it there rather than failing -- but skips
# explicitly, with the reason printed, so an absent writer can never read as a
# passing one. A silent pass on a missing file is the defect this whole change is
# about, in miniature.
GITIGNORED_WRITERS = {"scripts/dormant_claim_provision.py"}


@pytest.mark.parametrize("rel", PROVISIONING_WRITERS)
def test_provisioning_writers_stamp_provisioned(rel):
    """A writer that creates rows on the user's behalf must say so."""
    path = BACKEND / rel
    if not path.exists():
        if rel in GITIGNORED_WRITERS:
            pytest.skip(f"{rel} is gitignored and absent from this checkout")
        pytest.fail(f"{rel} is listed as a provisioning writer but does not exist")
    text = path.read_text(encoding="utf-8")
    assert "provisioned" in text, (
        f"{rel} writes tracking rows on the user's behalf but never stamps "
        "source='provisioned'; its rows would count as user engagement"
    )


def test_no_unaudited_write_paths():
    """Derive every write site from the tree and require each to be classified.

    An allowlist typed from memory is not a check (10 Sep 2026 lesson): the first
    pass at this change patched 2 of 11 provisioning writers. This test fails when
    a NEW file writes tracking rows without being placed in one of the two lists.
    """
    models_alt = "|".join(TRACK_MODELS)
    tables_alt = "|".join(
        __import__(m, fromlist=[c]).__dict__[c].__tablename__
        for c, m in TRACK_MODELS.items()
    )
    orm_re = re.compile(rf"\b({models_alt})\s*\(")
    sql_re = re.compile(rf"INSERT\s+INTO\s+(?:public\.)?({tables_alt})", re.I)
    skip_re = re.compile(r"^\s*class\s|\.query\(|isinstance\(|ForeignKey|relationship\(")

    known = set(PROVISIONING_WRITERS) | set(USER_ACTION_FILES) | {
        # Dead code: passes `tracked_at=`, which is not a column, so this restore
        # path raises TypeError before it can write. Pre-dates migration 230.
        # Listed so the audit stays green while the defect stays visible.
        "scripts/rescrape_carriages.py",
    }

    found = set()
    for path in BACKEND.rglob("*.py"):
        rel = path.relative_to(BACKEND).as_posix()
        if rel.startswith(("tests/", "migrations/")) or "node_modules" in rel:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for line in lines:
            if sql_re.search(line) or (orm_re.search(line) and not skip_re.search(line)):
                found.add(rel)
                break

    unaudited = sorted(found - known)
    assert not unaudited, (
        "these files write user_*_tracks rows and are in neither the provisioning "
        f"nor the user-action list: {unaudited}. Classify each one."
    )

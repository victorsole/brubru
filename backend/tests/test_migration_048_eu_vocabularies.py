"""
Migration round-trip test for 048_eu_vocabularies.sql.

Brubru migrations are raw SQL files (not Alembic), so we apply them in an
ephemeral PostgreSQL database. Test runs only when DATABASE_URL_TEST points
at a usable Postgres instance — otherwise SKIPPED so the suite stays green
on dev laptops without a local Postgres.

Real CI sets DATABASE_URL_TEST in `.env.test`; refer to docker-compose.yml
service `postgres-test` if you need to spin one up locally.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = ROOT / "backend" / "migrations"
UP_SQL_PATH = MIGRATIONS_DIR / "048_eu_vocabularies.sql"
DOWN_SQL_PATH = MIGRATIONS_DIR / "048_eu_vocabularies_down.sql"


# ----------------------------------------------------------------------
# Static checks (always run)
# ----------------------------------------------------------------------

def test_up_migration_exists():
    assert UP_SQL_PATH.exists(), f"missing {UP_SQL_PATH}"


def test_down_migration_exists():
    assert DOWN_SQL_PATH.exists(), f"missing {DOWN_SQL_PATH}"


def test_up_migration_creates_both_tables():
    sql = UP_SQL_PATH.read_text().lower()
    assert "create table if not exists eu_authority_labels" in sql
    assert "create table if not exists brubru_dataset_catalog" in sql


def test_up_migration_has_rls_policies():
    sql = UP_SQL_PATH.read_text()
    assert "ENABLE ROW LEVEL SECURITY" in sql
    # Policy names must mention service_role + authenticated readers.
    assert "service_role_all_eu_authority_labels" in sql
    assert "authenticated_read_eu_authority_labels" in sql
    assert "service_role_all_brubru_dataset_catalog" in sql
    assert "authenticated_read_brubru_dataset_catalog" in sql


def test_down_migration_drops_what_up_creates():
    sql = DOWN_SQL_PATH.read_text().lower()
    assert "drop table if exists brubru_dataset_catalog" in sql
    assert "drop table if exists eu_authority_labels" in sql
    assert "drop function if exists trg_brubru_dataset_catalog_updated_at" in sql


# ----------------------------------------------------------------------
# Live round-trip (skipped without DATABASE_URL_TEST)
# ----------------------------------------------------------------------

@pytest.fixture
def test_db_url():
    url = os.environ.get("DATABASE_URL_TEST")
    if not url:
        pytest.skip("DATABASE_URL_TEST not set — live round-trip skipped")
    return url


@pytest.mark.live
def test_migration_round_trip(test_db_url):
    """Apply up, assert tables exist, apply down, assert tables are gone.

    Uses Brubru's stock psycopg2 driver (the same one SQLAlchemy already
    pulls in). Note: this test will not destroy any non-empty schema —
    DATABASE_URL_TEST must point at an isolated DB.
    """
    import psycopg2  # type: ignore[import-not-found]

    up_sql = UP_SQL_PATH.read_text()
    down_sql = DOWN_SQL_PATH.read_text()

    # Make sure we're on an isolated DB before running anything.
    if "brubru_test" not in test_db_url and "_test" not in test_db_url:
        pytest.skip("DATABASE_URL_TEST does not look isolated — refusing to run round-trip")

    conn = psycopg2.connect(test_db_url)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            # Refuse to run on a populated cache — destructive otherwise.
            cur.execute(
                "SELECT to_regclass('public.eu_authority_labels')"
            )
            already_exists = cur.fetchone()[0] is not None
            if already_exists:
                cur.execute("SELECT COUNT(*) FROM eu_authority_labels")
                row_count = cur.fetchone()[0]
                if row_count > 0:
                    pytest.skip(
                        f"DATABASE_URL_TEST already has {row_count} rows in "
                        "eu_authority_labels — refusing to wipe. Point at "
                        "an empty DB to run the round-trip."
                    )

            # 1. Apply up
            cur.execute(up_sql)
            cur.execute(
                "SELECT to_regclass('public.eu_authority_labels'), "
                "to_regclass('public.brubru_dataset_catalog')"
            )
            row = cur.fetchone()
            assert row[0] is not None, "eu_authority_labels not created"
            assert row[1] is not None, "brubru_dataset_catalog not created"

            # 2. Smoke insert / select
            cur.execute(
                "INSERT INTO eu_authority_labels(uri, lang, pref_label, source_dataset_uri) "
                "VALUES (%s, %s, %s, %s) ON CONFLICT (uri, lang) DO NOTHING",
                ("http://test/migration-roundtrip", "en", "X", "http://test/dataset"),
            )
            cur.execute(
                "SELECT pref_label FROM eu_authority_labels WHERE uri=%s",
                ("http://test/migration-roundtrip",),
            )
            assert cur.fetchone()[0] == "X"

            # 3. Apply down
            cur.execute(down_sql)
            cur.execute(
                "SELECT to_regclass('public.eu_authority_labels'), "
                "to_regclass('public.brubru_dataset_catalog')"
            )
            row = cur.fetchone()
            assert row[0] is None, "eu_authority_labels survived down migration"
            assert row[1] is None, "brubru_dataset_catalog survived down migration"
    finally:
        conn.close()

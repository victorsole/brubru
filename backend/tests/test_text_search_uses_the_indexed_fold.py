"""The TED text search folds through brubru_fold(), the IMMUTABLE form of unaccent(lower(x)) its trigram
indexes are built on (migration 320, 30 Oct 2026: a count from 3.7 s to 0.11 s). Folded any other way,
the query's expression is not the index's and Postgres reads all 68,413 notices again."""
from sqlalchemy.dialects import postgresql

from api.v1._search import text_match
from models.tender import Tender


def _sql(q):
    return str(text_match(q, Tender.title, Tender.description, Tender.summary, Tender.official_name)
               .compile(dialect=postgresql.dialect()))


def test_each_column_is_folded_as_its_index_is():
    for q in ("hydrogen", "EU"):     # the long form (LIKE) and the short one (a word-bounded expression)
        sql = _sql(q)
        for col in ("tenders.title", "tenders.description", "tenders.summary", "tenders.official_name"):
            assert f"brubru_fold({col})" in sql, (q, col)
        assert "unaccent(lower(tenders." not in sql


def test_the_migration_builds_the_function_and_one_index_per_column():
    import pathlib
    m = (pathlib.Path(__file__).resolve().parents[1] / "migrations" / "320_tenders_text_search_index.sql").read_text()
    assert "public.unaccent('public.unaccent'::regdictionary, lower($1))" in m and "IMMUTABLE" in m
    for col in ("title", "description", "summary", "official_name::text"):
        assert f"USING gin (public.brubru_fold({col}) gin_trgm_ops)" in m, col

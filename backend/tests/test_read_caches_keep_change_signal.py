"""O230 (5 Nov 2026): a cache computed from a law's own text and stored on a READ moved the law's updated_date, so
updated_from handed it out again as changed. Each such writer now sets brubru.keep_change_signal to its own
transaction before the UPDATE (the trigger then keeps updated_at and logs nothing) and commits right after.
Checked against the live trigger function on a local Postgres on 6 Nov; this test holds the call order in CI."""
from types import SimpleNamespace

import pytest

from services.comparator import structure_extractor as se
from services.parsers import definition_store as ds
from services.parsers import recital_article_store as rs


class _Db:
    def __init__(self):
        self.log = []

    def execute(self, clause, params=None):
        sql = " ".join(str(clause).split())
        self.log.append("SET" if "brubru.keep_change_signal" in sql else ("UPDATE" if sql.startswith("UPDATE eu_laws") else sql[:30]))
        return SimpleNamespace(rowcount=1, first=lambda: None)

    def commit(self):
        self.log.append("COMMIT")

    def rollback(self):
        self.log.append("ROLLBACK")


@pytest.mark.parametrize("name, write", [
    ("definitions", lambda db: ds.write_map(db, "32006R1907", {"substance": {}})),
    ("consolidated definitions", lambda db: ds._write_consolidated(db, "32006R1907", "02006R1907-20260622", {"parser_version": 3})),
    ("recital map", lambda db: rs.write_map(db, "32016R0679", {"1": [2]})),
    ("structure counts", lambda db: se.cache_structure_counts(db, "32016R0679", (173, 99))),
])
def test_a_cache_written_on_a_read_keeps_the_laws_change_signal(name, write):
    db = _Db()
    write(db)
    assert db.log == ["SET", "UPDATE", "COMMIT"], (name, db.log)

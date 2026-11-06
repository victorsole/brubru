"""O213 (6 Nov 2026): /funding/awards?order=oldest sorted all 116,823 FTS lines (40.8 s on the database) because
their date index runs DESC NULLS LAST, and ASC NULLS LAST is not its reverse. The FTS side now reads the dated
rows ASC NULLS FIRST (the index backwards) and the undated rows apart; the merge keeps NULLS LAST. Read on
production 6 Nov: 1.4 s for the page, the FTS side 30 ms, and the same rows as before for four country filters."""
import pytest

from api.v2.funding import awards as a


def test_oldest_reads_the_fts_lines_backwards_on_their_index_and_keeps_undated_rows_last():
    sql = a._page_sql("oldest", "", False)
    assert "WHERE document_date IS NOT NULL ORDER BY document_date ASC NULLS FIRST, src ASC, rid ASC LIMIT :side_limit" in sql
    assert "WHERE document_date IS NULL ORDER BY src ASC, rid ASC LIMIT :side_limit" in sql
    assert sql.endswith("aw ORDER BY document_date ASC NULLS LAST, src ASC, rid ASC LIMIT :limit OFFSET :offset")
    assert sql.count("UNION ALL") == 3   # project, fts dated, fts undated, ted_award


def test_a_filter_is_kept_on_both_fts_branches():
    sql = a._page_sql("oldest", " WHERE country = :country", True)
    assert sql.count("WHERE country = :country AND document_date IS NOT NULL") == 1
    assert sql.count("WHERE country = :country AND document_date IS NULL") == 1
    assert sql.count("WHERE country = :country") == 4


@pytest.mark.parametrize("order", ["recent", "amount", "updated_asc", "updated_desc", "created_asc", "created_desc"])
def test_every_other_order_is_unchanged(order):
    sql = a._page_sql(order, "", False)
    assert "document_date IS NULL" not in sql and sql.count("UNION ALL") == 2
    o = a._order_sql(order)
    assert sql.count(f"ORDER BY {o} LIMIT :side_limit") == 3

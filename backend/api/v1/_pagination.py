"""Deterministic paging for LIMIT/OFFSET list endpoints.

GovClipping walked our list endpoints on 25 September 2026 and received the right NUMBER
of records with the wrong records in them: 4,835 consultations served but only 3,543
distinct ids, so 27% of the corpus never arrived, and 19,081 laws served for 17,882
distinct CELEX numbers. Nothing failed. `total`, `has_more` and `coverage_complete` were
all correct, and the duplicate rows simply took the places of the rows we never sent.

The cause is that LIMIT/OFFSET only returns each row exactly once when the ORDER BY is a
TOTAL order. Ours were not. SQL leaves the order of tied rows undefined, and PostgreSQL is
free to return them differently for each OFFSET, so a row can land on page 2 and again on
page 5 while another is skipped. Measured the same day, the ties are not marginal:

    public_consultations   4,835 rows over   471 distinct last_updated (biggest tie 500)
    eu_laws               30,474 rows over    91 distinct updated_at   (biggest tie 4,965)

91% of consultations and nearly all laws sit inside a tie group, which is why a quarter of
the corpus was unreachable rather than a handful of rows.

`stable()` appends the primary key, which is unique by definition, so the sort becomes a
total order and the page boundaries stop moving between requests. SQLAlchemy's `order_by`
APPENDS, so the caller's own ordering is untouched: this only decides ties.

Usage, wrapping the query AFTER its own order_by:

    rows = stable(q.order_by(Model.date.desc())).offset(off).limit(limit).all()

For raw SQL, end the ORDER BY with the primary key yourself, e.g.
`ORDER BY last_updated DESC NULLS LAST, id`.
"""
from __future__ import annotations

from sqlalchemy import inspect as sa_inspect


def stable(query, *tiebreak):
    """Append a unique tiebreaker so LIMIT/OFFSET paging is deterministic.

    `tiebreak` overrides the derived key, for queries whose first entity is not the row
    being paged (aliases, column queries, joins selecting a non-primary entity).

    Raises ValueError when no tiebreaker can be derived, rather than returning the query
    untouched: a silent no-op here reintroduces exactly the bug this exists to prevent,
    and it would be invisible in the response.
    """
    if tiebreak:
        return query.order_by(*tiebreak)

    descriptions = getattr(query, "column_descriptions", None) or []
    entity = descriptions[0].get("entity") if descriptions else None
    if entity is None:
        raise ValueError(
            "stable() could not derive a primary key from this query: pass an explicit "
            "tiebreaker, e.g. stable(q, Model.id)"
        )
    primary_key = sa_inspect(entity).primary_key
    if not primary_key:
        raise ValueError(f"{entity} has no primary key to break ties on")
    return query.order_by(*[column.asc() for column in primary_key])

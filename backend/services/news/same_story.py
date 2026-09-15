"""One story, one eu_news_items row, even when it is linked from two URLs.

Why this exists
---------------
`eu_news_items.entry_key` is the canonical URL, so identity is per URL. The
Commission publishes most releases twice: once on the presscorner
(ec.europa.eu/commission/presscorner/detail/en/ip_26_1835) and once on the DG's own
site (competition-policy.ec.europa.eu/about/news/...), and DG newsrooms link either
one. Both became rows. On 15 Sep 2026 `/api/v2/news/all` served "Commission approves
EUR 52 million Romanian State aid for cattle farmers..." twice, nine seconds apart,
both from the COMP sources; the store held 112 such groups (120 surplus rows), most
of them presscorner + DG-subdomain pairs (COMP, GROW, ENER, TRADE, ESTAT/ENER).

The rule
--------
Same institution + same `news_date` + same title once case, punctuation and
whitespace are removed. Titles shorter than MIN_TITLE_CHARS are never matched: a
short generic title ("EP TODAY", "Daily News") legitimately repeats on one day.
Undated items are never matched either, because without a date "same title" is not
evidence of the same story.
"""
from __future__ import annotations

import re
from typing import Optional

from sqlalchemy import text

MIN_TITLE_CHARS = 30

# The SQL twin of `normalise_title`. Postgres `\W` and Python `\W` agree on the
# characters that matter here (letters and digits kept, punctuation, symbols and
# spaces dropped), and comparing SQL-normalised to SQL-normalised avoids relying on
# that agreement at all.
_NORM_SQL = "lower(regexp_replace(title, '\\W+', '', 'g'))"


def normalise_title(title: Optional[str]) -> str:
    return re.sub(r"\W+", "", (title or "")).lower()


def is_matchable(title: Optional[str], news_date) -> bool:
    return bool(news_date) and len((title or "").strip()) >= MIN_TITLE_CHARS


def find_same_story(db, *, institution: str, title: str, news_date,
                    exclude_entry_key: Optional[str] = None) -> Optional[str]:
    """entry_key of an existing row carrying the same story, or None.

    Flushes first: a twin added earlier in the SAME run (two DG pages in one
    source batch) is still pending in the session, and a text() query does not
    autoflush.
    """
    if not institution or not is_matchable(title, news_date):
        return None
    db.flush()
    row = db.execute(text(
        "SELECT entry_key FROM eu_news_items "
        "WHERE institution = :inst AND news_date = :d "
        f"AND {_NORM_SQL} = lower(regexp_replace(:t, '\\W+', '', 'g')) "
        "AND (CAST(:x AS text) IS NULL OR entry_key <> :x) "
        "ORDER BY created_at ASC LIMIT 1"),
        {"inst": institution, "d": news_date, "t": title, "x": exclude_entry_key},
    ).fetchone()
    return row[0] if row else None


# Groups of rows that are one story. Used by scripts/dedupe_eu_news_same_story.py.
DUPLICATE_GROUPS_SQL = f"""
SELECT institution, news_date, {_NORM_SQL} AS norm,
       array_agg(id::text ORDER BY created_at ASC, id) AS ids,
       array_agg(entry_key ORDER BY created_at ASC, id) AS keys
  FROM eu_news_items
 WHERE news_date IS NOT NULL
   AND institution IS NOT NULL
   AND length(btrim(title)) >= {MIN_TITLE_CHARS}
 GROUP BY institution, news_date, {_NORM_SQL}
HAVING count(*) > 1
"""

"""Free-text `q` matching for v1/v2 list endpoints.

Two defects this exists to fix, both measured on the live `tenders` table on
9 September 2026.

**Unanchored substring matching makes short terms worthless.** `q=CAD` returned
**280** notices and not one of them was about CAD: every hit was `ACCORD-CADRE`
(the French term for a framework agreement) or `Fassade`. Word-bounded, the same
query returns **0**, which is the honest answer -- there are no CAD tenders in the
corpus. A confidently wrong answer is worse than an empty one, because the caller
acts on it. `search_guides()` already word-bounds short terms; this brings the
tender/funding surfaces into line.

**Matching was accent-sensitive, on a corpus that is 45% accented.** 4,158 of 9,146
notices carry diacritics in the buyer name. A caller typing `Fakultni nemocnice
Olomouc` -- the spelling anyone without a Czech keyboard produces -- got **0**, while
`Fakultní nemocnice Olomouc` got **16**. Same class of failure as
`feedback_triggers_no_accent_folding`: an unaccented key can never match an accented
value, and the caller cannot tell that from an absence of data.

Both sides are folded through `unaccent()` (extension present in this database), so
the accented and unaccented spellings of a query are equivalent.

The short-term threshold is 4 characters, matching `search_guides()`. Above it,
substring matching is kept deliberately: partial words are useful there (`comput`
finds "computing", 186 notices), and a long string is specific enough that noise is
not the problem.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from sqlalchemy import and_, func, literal, or_

# Matching search_guides(): at 4 characters and below, substring noise dominates
# (`rearm` inside "fiREARMs" is the documented case in the guide ranker).
SHORT_Q_MAX = 4

# Escaped before being spliced into a POSIX regex, or a caller's `q=C++` raises
# instead of returning a result set.
_RE_META = re.compile(r"([.^$*+?()\[\]{}|\\])")


def _folded(col: Any):
    """The column, lowercased and stripped of diacritics: brubru_fold(x) is unaccent(lower(x)) with its
    dictionary named, so IMMUTABLE and indexable (migration 320: trigram indexes on the TED notices'
    four columns took a count from 3.7 s to 0.11 s, 30 Oct 2026)."""
    return func.brubru_fold(col)


# Little words carry no meaning in a search and would only narrow it.
_LITTLE_WORDS = {"the", "of", "and", "in", "for", "on", "to", "a", "an", "by", "with", "about", "from", "at", "or"}
MAX_WORDS = 8


def search_words(q: Optional[str]) -> list[str]:
    """The words a person typed, without the little ones. A search of nothing but little words keeps them."""
    words = (q or "").split()
    kept = [w for w in words if w.casefold() not in _LITTLE_WORDS]
    return (kept or words)[:MAX_WORDS]


def like_all_words(q: Optional[str], cols: list[str], params: dict, prefix: str = "q") -> str:
    """SQL for hand-written queries: every word somewhere in these columns, in any order and any case.
    A person types "electric cars", and as one exact phrase that found nothing (4 Nov 2026)."""
    clauses = []
    for i, word in enumerate(search_words(q)):
        params[f"{prefix}{i}"] = f"%{word}%"
        clauses.append("(" + " OR ".join(f"{c} ILIKE :{prefix}{i}" for c in cols) + ")")
    return " AND ".join(clauses) or "TRUE"


def title_first(q: Optional[str], params: dict, title_col: str = "title", prefix: str = "tq") -> str:
    """An ORDER BY term: results with the words in their title before those that only mention them somewhere.
    Newest-first alone answered "AI Act" with "Elastic in cash, inelastic in repo" (4 Nov 2026)."""
    clauses = []
    for i, word in enumerate(search_words(q)):
        params[f"{prefix}{i}"] = f"%{word}%"
        clauses.append(f"{title_col} ILIKE :{prefix}{i}")
    return f"CASE WHEN {' AND '.join(clauses)} THEN 0 ELSE 1 END" if clauses else "0"


def in_title(q: Optional[str], title: Optional[str]) -> bool:
    """The same test, for a list already in memory."""
    words = search_words(q)
    folded = (title or "").casefold()
    return bool(words) and all(w.casefold() in folded for w in words)


def orm_all_words(q: Optional[str], *cols: Any):
    """like_all_words for ORM queries."""
    return and_(*[or_(*[c.ilike(f"%{w}%") for c in cols]) for w in search_words(q)])


def text_match(q: Optional[str], *cols: Any):
    """An accent-insensitive OR across `cols`, word-bounded for short `q`. Several words: all of them, in any order.

    Returns None when there is nothing to match on, so callers can write
    `cond = text_match(q, A, B); if cond is not None: filters.append(cond)` and a
    blank or whitespace-only `q` behaves as "no filter" rather than as
    "match everything", which `LIKE '%%'` would.
    """
    if q is None:
        return None
    term = q.strip()
    if not term or not cols:
        return None
    words = search_words(term)
    if len(words) > 1:
        return and_(*[_one_term(w, cols) for w in words])
    return _one_term(words[0], cols)


def _one_term(term: str, cols: tuple):
    if len(term) <= SHORT_Q_MAX:
        # \y is a POSIX word boundary in Postgres. Escaping happens BEFORE folding
        # so the backslashes we add are not themselves transformed.
        pattern = func.concat(
            literal(r"\y"),
            func.unaccent(func.lower(literal(_RE_META.sub(r"\\\1", term)))),
            literal(r"\y"),
        )
        return or_(*[_folded(c).op("~")(pattern) for c in cols])

    pattern = func.concat(literal("%"), func.unaccent(func.lower(literal(term))), literal("%"))
    return or_(*[_folded(c).like(pattern) for c in cols])

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

from sqlalchemy import and_, case, func, literal, or_

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


def _is_short(word: str) -> bool:
    return len(word) <= SHORT_Q_MAX


def _whole_word(word: str) -> str:
    """A POSIX pattern for a short word as a word: \\yai\\y, so that "AI" does not match "certain"."""
    return r"\y" + _RE_META.sub(r"\\\1", word) + r"\y"


def _sql_term(col: str, word: str, name: str, params: dict) -> str:
    """One word in one column, as text_match treats it: whole for a short word, anywhere for a long one."""
    if _is_short(word):
        params[name] = _whole_word(word)
        return f"{col} ~* :{name}"
    params[name] = f"%{word}%"
    return f"{col} ILIKE :{name}"


def like_all_words(q: Optional[str], cols: list[str], params: dict, prefix: str = "q") -> str:
    """SQL for hand-written queries: every word somewhere in these columns, in any order and any case.
    A person types "electric cars", and as one exact phrase that found nothing (4 Nov 2026)."""
    clauses = []
    for i, word in enumerate(search_words(q)):
        terms = [_sql_term(c, word, f"{prefix}{i}", params) for c in cols]
        clauses.append("(" + " OR ".join(terms) + ")")
    return " AND ".join(clauses) or "TRUE"


def title_first(q: Optional[str], params: dict, title_col: str = "title", prefix: str = "tq") -> str:
    """An ORDER BY term: the whole phrase in the title, then all its words in the title, then the rest.
    Newest-first alone answered "AI Act" with "Elastic in cash, inelastic in repo" (4 Nov 2026)."""
    words = search_words(q)
    if not words:
        return "0"
    all_words = " AND ".join(_sql_term(title_col, w, f"{prefix}{i}", params) for i, w in enumerate(words))
    if len(words) == 1:
        return f"CASE WHEN {all_words} THEN 0 ELSE 1 END"
    params[f"{prefix}phrase"] = "%" + " ".join(words) + "%"
    return f"CASE WHEN {title_col} ILIKE :{prefix}phrase THEN 0 WHEN {all_words} THEN 1 ELSE 2 END"


def in_title(q: Optional[str], title: Optional[str]) -> bool:
    """The same test, for a list already in memory."""
    words = search_words(q)
    folded = (title or "").casefold()
    if not words:
        return False
    return all(
        re.search(rf"\b{re.escape(w.casefold())}\b", folded) if _is_short(w) else w.casefold() in folded
        for w in words
    )


def _orm_term(col: Any, word: str):
    return col.op("~*")(_whole_word(word)) if _is_short(word) else col.ilike(f"%{word}%")


def orm_all_words(q: Optional[str], *cols: Any):
    """like_all_words for ORM queries."""
    return and_(*[or_(*[_orm_term(c, w) for c in cols]) for w in search_words(q)])


def orm_title_first(q: Optional[str], title_col: Any):
    """title_first for ORM queries: a sort term, 0 when the words are in the title."""
    return case((and_(*[_orm_term(title_col, w) for w in search_words(q)]), 0), else_=1)


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

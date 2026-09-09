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

from sqlalchemy import func, literal, or_

# Matching search_guides(): at 4 characters and below, substring noise dominates
# (`rearm` inside "fiREARMs" is the documented case in the guide ranker).
SHORT_Q_MAX = 4

# Escaped before being spliced into a POSIX regex, or a caller's `q=C++` raises
# instead of returning a result set.
_RE_META = re.compile(r"([.^$*+?()\[\]{}|\\])")


def _folded(col: Any):
    """The column, lowercased and stripped of diacritics."""
    return func.unaccent(func.lower(col))


def text_match(q: Optional[str], *cols: Any):
    """An accent-insensitive OR across `cols`, word-bounded for short `q`.

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

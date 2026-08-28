"""One declared place naming the column that holds each table's text.

The problem this replaces
-------------------------
`body_txt` / `body_html` is the API's contract -- every v2 item promises them.
The storage layer never adopted it. Measured 28 August 2026, one concept is
stored under eight different names:

    economy_items ............ body_txt / body_html      (the only standard one)
    legissum_summaries ....... summary_text / summary_html
    texts_adopted ............ full_text
    commission_documents ..... text_body / body_html
    institutional_publications html_content
    social_posts ............. content
    parliamentary_questions .. text_question / text_answer
    mep_amendments ........... original_text / proposed_text

So every handler wrote its own translation, and each one was an opportunity to
get it wrong quietly. That is not hypothetical: the LEGISSUM list endpoint never
selected `summary_text` at all and served a null body over 4,457 rows that were
100% populated, while its detail route returned the text but never the HTML.

Why a mapping layer before renaming the columns
-----------------------------------------------
Renaming is the destination, not the first step: the names are written by
scrapers, migrations, backfills and ad-hoc queries, and changing them under all
of that at once is how you get a silent outage. This layer inverts the problem.
Handlers stop knowing physical column names and ask here instead, so:

  * a new table cannot quietly invent a ninth convention -- it is not served
    until it is declared here;
  * the eventual rename is a ONE-LINE edit per table in this file, and every
    handler keeps working through it;
  * `tests/test_body_sources.py` asserts every column declared here really
    exists, so a rename that lands in the database and not here fails loudly
    instead of serving nulls.

Why this lives in `core/` and not `api/v2/`
------------------------------------------
It first went to `api/v2/_body_sources.py` and took the API down on import.
`api/v2/commission/commission_register.py` does `from api.v1.commission_register
import *` to reproduce v1's namespace, so a v1 handler importing anything under
`api.v2` re-enters a half-initialised module and dies on a NameError. The
registry describes the DATABASE, not an API version, and both v1 and v2 need it;
`core/` is a namespace package, so importing from it runs no package __init__ at
all and cannot cycle.

Coverage numbers below are measured, not assumed, and are what tells a null body
apart from a missing one. They are a snapshot: the test checks the columns exist,
never that a percentage held.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class BodySource:
    """Where a table keeps its text.

    `txt` and `html` are column names, or None when the table genuinely has no
    such form -- `texts_adopted` holds plain text extracted from a PDF and never
    saw HTML, and inventing it would misrepresent the source.
    """

    txt: Optional[str] = None
    html: Optional[str] = None
    note: str = ""

    def __post_init__(self):
        if not self.txt and not self.html:
            raise ValueError("a BodySource must name at least one column")


# fmt: off
BODY_SOURCES: dict[str, BodySource] = {
    # The standard, and the target shape for everything below.
    "economy_items": BodySource(
        "body_txt", "body_html",
        "553,364/555,354 txt (99.6%). 334 generated routes read this one table."),

    "legissum_summaries": BodySource(
        "summary_text", "summary_html",
        "4,457/4,457 both (100%). The list served neither until 28 Aug 2026."),

    "texts_adopted": BodySource(
        "full_text", None,
        "703/703. Extracted from doceo PDFs, so there is no HTML manifestation."),

    "commission_documents": BodySource(
        "text_body", "body_html",
        "471/1,184 txt, 244 html. The NEWEST rows are the empty ones, so the "
        "default recent-first sort shows nulls first: a corpus gap, not a bug."),

    "institutional_publications": BodySource(
        None, "html_content",
        "705/835 html. No plain-text column; strip the HTML for body_txt."),

    "social_posts": BodySource(
        "content", None,
        "30,690/30,690. body_html is composed from the post text plus its link."),

    "committee_minutes": BodySource(
        "full_text", None,
        "110/228. PDF-extracted, same reasoning as texts_adopted."),

    "law_requirements": BodySource(
        "requirement_text", None,
        "2,945/2,945."),

    "amendment_documents": BodySource(
        "text_body", "body_html",
        "0/1,330 -- the columns exist and were NEVER filled, though "
        "body_fetched_at is stamped on 14 rows. Declared so the endpoint serves "
        "the text the moment a fetcher fills it. This is the gap behind "
        "/parliament/reports and /parliament/ep-documents."),

    # --- one concept, two columns -----------------------------------------
    # These hold two genuinely DIFFERENT texts rather than two renderings of
    # one, so a single body column would lose half the record. The handler
    # composes them; the registry records the pieces rather than pretending
    # there is a single source column.
    "parliamentary_questions": BodySource(
        "text_question", None,
        "5,646 questions / 4,876 answers. text_answer is the SECOND text, not "
        "an HTML rendering -- composed by the handler, never silently dropped."),

    "mep_amendments": BodySource(
        "original_text", None,
        "58,399 both. proposed_text is the amended wording: the pair IS the "
        "amendment, so the handler composes original + proposed."),

    # --- prose that is not a document -------------------------------------
    "public_consultations": BodySource(
        "description", None,
        "4,264/4,803. NOTE: full_description and outcome_summary are empty in "
        "EVERY row (0/4,803) -- composing them, as the handler did, added "
        "nothing. Measured, not assumed."),

    "eu_calendar_events": BodySource(
        "description", None,
        "1,562/3,985. Agenda documents live in related_documents, not here."),

    "funding_opportunities": BodySource(
        "description", None,
        "1,972/1,972. short_summary is a lead, not the body."),
}
# fmt: on


class UnknownBodyTable(KeyError):
    """Raised when a handler asks for a table nobody declared.

    Loud on purpose. A silent default would let a new table ship serving nulls,
    which is the failure this module exists to end.
    """


def get_source(table: str) -> BodySource:
    try:
        return BODY_SOURCES[table]
    except KeyError:
        raise UnknownBodyTable(
            f"{table!r} has no declared body source. Add it to BODY_SOURCES in "
            f"core/body_sources.py, naming the column(s) that hold its text, "
            f"rather than aliasing the column inside the handler."
        ) from None


def body_select(table: str, include_body: bool, alias: str = "") -> str:
    """SQL that always yields `body_txt` and `body_html`, whatever they are called.

    The point of the alias is that a handler's SELECT, its row mapper and its
    response model all speak the contract's names, so renaming the physical
    column later changes this file and nothing else.

        body_select("legissum_summaries", True)
        -> 'summary_text AS body_txt, summary_html AS body_html'

    `include_body=False` still returns both names, as typed NULLs, so the shape
    of the row never changes with the flag -- a mapper cannot then trip over a
    column that is present in one branch and absent in the other.
    """
    src = get_source(table)
    p = f"{alias}." if alias else ""
    if not include_body:
        return "NULL::text AS body_txt, NULL::text AS body_html"
    txt = f"{p}{src.txt} AS body_txt" if src.txt else "NULL::text AS body_txt"
    html = f"{p}{src.html} AS body_html" if src.html else "NULL::text AS body_html"
    return f"{txt}, {html}"


def read_body(table: str, row, include_body: bool = True) -> tuple[Optional[str], Optional[str]]:
    """The same mapping for an ORM object or row, where SQL aliasing is not an option."""
    if not include_body:
        return None, None
    src = get_source(table)
    txt = getattr(row, src.txt, None) if src.txt else None
    html = getattr(row, src.html, None) if src.html else None
    return txt, html


def declared_tables() -> list[str]:
    return sorted(BODY_SOURCES)

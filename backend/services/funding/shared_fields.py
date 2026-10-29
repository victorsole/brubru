"""The funding standard's shared fields (Phase 2 step 3, 28 Oct 2026).

Every funding item carries item_type, title, summary, status, body_code, body_name and amount_eur,
null where the item has no such thing. Victor's choices of 28 Oct: the item_type values already in
use, and a summary cut from the item's own text where a list had none. Here, not in the v2 funding
package, so the v1 handlers behind the F&T and TED routes can use it without an import cycle.
"""
from __future__ import annotations

import html
import re
import time
from typing import Dict, Iterable, Optional

from sqlalchemy import text

SUMMARY_CHARS = 300
_TAG = re.compile(r"<[a-zA-Z/][^>]*>")


def cut_summary(source: Optional[str], limit: int = SUMMARY_CHARS) -> Optional[str]:
    """The item's own text as a summary: whitespace collapsed, cut at the last word end before `limit`
    characters and closed with an ellipsis when cut."""
    if not source:
        return None
    # Some buyers type HTML into a plain-text field (88 of 65,676 TED descriptions, 28 Oct 2026): the
    # summary is plain text, the body keeps what was published.
    s = " ".join(html.unescape(_TAG.sub(" ", str(source))).split())
    if len(s) <= limit:
        return s or None
    cut = s[:limit].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return (cut or s[:limit]) + "\u2026"


# The funds are not bodies in economy_bodies: their lists and /funding/all name them by lower(fund) of
# the finance tables (body=erdf), so the cohesion outcomes of ESF+ and Interreg use the same codes.
FUND_NAMES = {
    "erdf": "European Regional Development Fund",
    "esf": "European Social Fund Plus",
    "cf": "Cohesion Fund",
    "jtf": "Just Transition Fund",
    "interreg": "Interreg (European Territorial Cooperation)",
    "emfaf": "European Maritime, Fisheries and Aquaculture Fund",
    "amif": "Asylum, Migration and Integration Fund",
    "isf": "Internal Security Fund",
    "eagf": "European Agricultural Guarantee Fund",
    "eafrd": "European Agricultural Fund for Rural Development",
    "eusf": "European Union Solidarity Fund",
}

_BODY_NAMES: Dict[str, str] = {}
_BODY_NAMES_READ_AT: Optional[float] = None


def body_names(db, codes: Iterable[Optional[str]]) -> Dict[str, Optional[str]]:
    """code -> name: the funds from FUND_NAMES, every other body from economy_bodies (read once per
    process, and again when a code is missing, at most every 15 minutes)."""
    global _BODY_NAMES_READ_AT
    codes = {c for c in codes if c}
    missing = {c for c in codes if c not in FUND_NAMES and c not in _BODY_NAMES}
    if missing and (_BODY_NAMES_READ_AT is None or time.monotonic() - _BODY_NAMES_READ_AT > 900):
        _BODY_NAMES_READ_AT = time.monotonic()
        for r in db.execute(text("SELECT code, name FROM economy_bodies")).fetchall():
            code, name = getattr(r, "code", None), getattr(r, "name", None)
            if isinstance(code, str) and isinstance(name, str):
                _BODY_NAMES[code] = name
    return {c: FUND_NAMES.get(c) or _BODY_NAMES.get(c) for c in codes}


def with_body_names(db, items: list) -> list:
    """Fill body_name on every item (a model or a dict) from its body_code."""
    names = body_names(db, [(i.get("body_code") if isinstance(i, dict) else getattr(i, "body_code", None)) for i in items])
    for i in items:
        if isinstance(i, dict):
            i["body_name"] = names.get(i.get("body_code"))
        else:
            i.body_name = names.get(getattr(i, "body_code", None))
    return items


def eur(amount, currency: Optional[str]) -> Optional[float]:
    """The amount when it is already in euros, else null. A list whose items may be in another
    currency reads amount_eur from page_amounts_eur() instead (Phase 2 step 6)."""
    if amount is None or (currency or "").strip().upper() != "EUR":
        return None
    return float(amount)


# An amount in euros (Phase 2 step 6, 29 Oct 2026; standard §6, decision 4): the item's own figure at
# the ECB reference rate of the item's own day (ecb_reference_rates, migration 318), or of the last
# earlier day the ECB published one (weekends and TARGET holidays: Christmas leaves a 5-day gap),
# at most RATE_DAYS_BACK days before; a converted amount is rounded to the cent, one in euros is kept
# as stated. The lev at 1.95583 lev per euro, its
# conversion rate (Council Regulation (EU) 2025/1409; the ECB's BGN series ends 31 Dec 2025). A
# currency the ECB does not publish (MDL, MKD, UAH, RSD, TZS, PAB, AMD, BAM ... in our notices), an
# amount with no currency or no date: null, never a guess.
RATE_DAYS_BACK = 7
BGN_PER_EUR = "1.95583"
AMOUNT_EUR_RULE = (
    "as stated when the figure is in euros; otherwise converted at the ECB reference rate of the item's "
    "publication day (or of the last earlier day the ECB published one, at most 7 days before), to the "
    "cent; null when the ECB publishes no rate for the currency (MDL, MKD, UAH, RSD and a few others)")


# The rate is read in a subquery over ecb_reference_rates, where an unqualified name resolves to that
# table first: a caller's column called `currency` would compare the rates table with itself.
_RATE_COLUMNS = re.compile(r"(?<![.\w])(currency|rate_date|rate|series_key|source_url|first_seen|last_updated|scraped_at)(?!\w)")


def amount_eur_sql(amount: str, currency: str, day: str) -> str:
    """The amount in euros as an SQL expression, over the columns (or expressions) `amount`,
    `currency` and `day` (a date: the item's own day, in Brussels). The one rule for amount_eur,
    its filters and its order. A column named like one of the rates table's must be qualified."""
    for expr in (amount, currency, day):
        clash = _RATE_COLUMNS.search(re.sub(r"'[^']*'", "''", expr))
        if clash:
            raise ValueError(f"qualify {clash.group(1)!r} in {expr!r}: the rates table has a column of that name")
    cur = f"upper(btrim({currency}))"
    rate = (f"(SELECT r.rate FROM ecb_reference_rates r WHERE r.currency = {cur} "
            f"AND r.rate_date <= ({day}) AND r.rate_date >= ({day}) - {RATE_DAYS_BACK} "
            f"ORDER BY r.rate_date DESC LIMIT 1)")
    return (f"(CASE WHEN {amount} IS NULL THEN NULL "
            f"WHEN {cur} = 'EUR' THEN ({amount})::numeric "
            f"WHEN {cur} = 'BGN' THEN round(({amount})::numeric / {BGN_PER_EUR}, 2) "
            f"ELSE round(({amount})::numeric / {rate}, 2) END)")


def brussels_day(column: str, kind: str) -> str:
    """The Brussels calendar day of a date column: `date`, `timestamptz`, or `utc_timestamp` (a
    timestamp without time zone that holds UTC)."""
    if kind == "date":
        return column
    if kind == "timestamptz":
        return f"(({column}) AT TIME ZONE 'Europe/Brussels')::date"
    if kind == "utc_timestamp":
        return f"((({column}) AT TIME ZONE 'UTC') AT TIME ZONE 'Europe/Brussels')::date"
    raise ValueError(kind)


def page_amounts_eur(db, rows, *, table: str, key: str, amount: str, currency: str, day: str,
                     key_of=None, currency_of=None) -> Dict:
    """key -> amount_eur for the rows of one page whose currency is not the euro, converted in SQL by
    amount_eur_sql (so an item shows the figure its filters compare). A page in euros needs no query."""
    key_of = key_of or (lambda r: getattr(r, key))
    currency_of = currency_of or (lambda r: getattr(r, currency))
    keys = [key_of(r) for r in rows if (currency_of(r) or "").strip().upper() not in ("", "EUR")]
    if not keys:
        return {}
    got = db.execute(text(f"SELECT {key} AS k, {amount_eur_sql(amount, currency, day)} AS eur "
                          f"FROM {table} WHERE {key} = ANY(:keys)"), {"keys": keys}).fetchall()
    return {r.k: (float(r.eur) if r.eur is not None else None) for r in got}


def eur_sql(amount: str, currency: str) -> str:
    """eur() in SQL, for a list whose items show eur(): the amount when its currency is the euro, else
    null. Its amount filters then compare the figure the item shows."""
    return f"(CASE WHEN upper(btrim({currency})) = 'EUR' THEN ({amount})::numeric END)"


# The amount range every list with an amount takes (Phase 2 step 6b, standard §6), on the expression
# that gives the list's own amount_eur.
MIN_AMOUNT_DOC = "amount_eur at least (euros). An item with no euro figure is left out."
MAX_AMOUNT_DOC = "amount_eur at most (euros). An item with no euro figure is left out."
AMOUNT_RANGE_DOC = ("`min_amount_eur`, `max_amount_eur`: `amount_eur` at least / at most, in euros (an item with no "
                    "euro figure is left out); `order=amount` lists the largest first")


def amount_range_sql(where: list, params: dict, min_eur, max_eur, expr: str) -> None:
    """min_amount_eur / max_amount_eur on `expr` for a list written in SQL."""
    if min_eur is not None:
        where.append(f"{expr} >= :min_amount_eur"); params["min_amount_eur"] = min_eur
    if max_eur is not None:
        where.append(f"{expr} <= :max_amount_eur"); params["max_amount_eur"] = max_eur


def amount_range_orm(query, min_eur, max_eur, expr: str):
    """min_amount_eur / max_amount_eur on `expr` for an ORM query."""
    if min_eur is not None:
        query = query.filter(text(f"{expr} >= :min_amount_eur").bindparams(min_amount_eur=min_eur))
    if max_eur is not None:
        query = query.filter(text(f"{expr} <= :max_amount_eur").bindparams(max_amount_eur=max_eur))
    return query


def item_amount_eur(amount, currency: Optional[str], converted: Dict, item_key) -> Optional[float]:
    """An item's amount_eur: its amount when in euros, else what page_amounts_eur() read for it."""
    if amount is None:
        return None
    if (currency or "").strip().upper() == "EUR":
        return float(amount)
    return converted.get(item_key)


def legacy(*standard: str, note: str = "the same value") -> dict:
    """Field arguments for an older name kept beside the standard one (Phase 2 step 4, 28 Oct 2026:
    one name per concept; the old names stay until the date Victor sets). The schema marks the field
    deprecated; its description names the field (or fields) to read instead."""
    names = " or ".join(f"`{s}`" for s in standard)
    return {"description": f"Legacy name, kept for existing integrations: read {names} ({note}).",
            "json_schema_extra": {"deprecated": True}}


# A budget item's status, one vocabulary (Phase 2 step 5d, 29 Oct 2026; standard §6): adopted,
# proposed, accepted, rejected, withdrawn, under_assessment. The source's own word is served beside
# it as `source_status`, and stays in the body. Read at the sources that day:
#   Cohesion Open Data 9qee-iv7c, "Adoption status of programme": "Adopted by EC" (a Commission
#     decision), "Adopted by MS" (only on amended versions 2-7: a transfer the Member State makes
#     itself, which under Article 24(5) of Regulation (EU) 2021/1060 "shall not require a decision
#     of the Commission"), "Adopted by EC (TF Accepted)" / "(TF Proposed)" (AMIF and ISF only,
#     sub-versions such as 6.1: the funds' thematic facility; the programme version is adopted).
#     All four are `adopted`. The 96 Interreg rows carry none: null.
#   EU Solidarity Fund cases: Accepted, Rejected, Withdrawn, Under assessment.
BUDGET_STATUSES = ("adopted", "proposed", "accepted", "rejected", "withdrawn", "under_assessment")


def budget_status(word: Optional[str]) -> Optional[str]:
    """The standard status for a cohesion programme's or a Solidarity Fund case's own word, or None."""
    w = " ".join((word or "").lower().replace("_", " ").split())
    if not w:
        return None
    if w.startswith("adopted"):
        return "adopted"
    if w.startswith("proposed"):
        return "proposed"
    w = w.replace(" ", "_")
    return w if w in BUDGET_STATUSES else None


def budget_status_sql(column: str = "status") -> str:
    """budget_status() in SQL, for the lists' filters and /funding/all."""
    w = f"lower(btrim({column}))"
    return (f"CASE WHEN {w} LIKE 'adopted%' THEN 'adopted' WHEN {w} LIKE 'proposed%' THEN 'proposed' "
            f"WHEN {w} IN ('accepted', 'rejected', 'withdrawn') THEN {w} "
            f"WHEN {w} IN ('under assessment', 'under_assessment') THEN 'under_assessment' END")


def budget_status_filter(where: list, params: dict, value: str, column: str = "status") -> None:
    """`status=`: a standard word matches the standard status; any other text, as before 29 Oct 2026,
    is a substring of the source's own word."""
    v = value.strip()
    if v.lower() in BUDGET_STATUSES:
        where.append(f"({budget_status_sql(column)}) = :status_std"); params["status_std"] = v.lower()
    else:
        where.append(f"{column} ILIKE :status_src"); params["status_src"] = f"%{v}%"

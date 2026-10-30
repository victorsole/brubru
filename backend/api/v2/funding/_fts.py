"""The EU Financial Transparency System rows with the file's own columns (26 Oct 2026).

Shared by /funding/eu-funding-recipients and /funding/international-cooperation. Each row is an
economy_items row (body_code 'commission', item_type 'funding_recipient': the record as text,
its dates, its id) joined to fts_commitments (migration 313: the values the FTS file states,
re-read from the file by scripts/sync_fts_commitments.py). Until then both lists had the text
only, and international-cooperation parsed its fields back out of it.

`amount_eur` is the beneficiary's own contracted amount, the row's main figure;
`commitment_total_eur` is the whole commitment's, shared by its beneficiaries (international-
cooperation served that as `amount_eur` until 26 Oct 2026, so a consortium's members each showed
the full amount and a sum per organisation counted it once per member).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from api.v1._row_dates import row_updated
from services.funding.countries import eu_code, vat_key
from services.funding.shared_fields import legacy

FROM = ("FROM economy_items e LEFT JOIN fts_commitments c ON c.economy_item_id = e.id "
        "WHERE e.body_code = 'commission' AND e.item_type = 'funding_recipient'")
# A change to the file's values is a change to the item: updated_date is the later of the two.
UPDATED = "greatest(e.updated_at, c.last_updated)"
# No index serves UPDATED, so an updated_from window read every FTS line (34.4 s a count, O105). "The
# later of the two is on or after X" is "either is on or after X": the lines are found through the two
# stamps' own indexes (idx_economy_items_updated_at, migration 321's ix_fts_commitments_last_updated)
# and the exact rule stays beside it (0.29 s, 30 Oct 2026).
CHANGED_SINCE = ("e.id IN (SELECT id FROM economy_items WHERE updated_at >= :updated_from "
                 "UNION SELECT economy_item_id FROM fts_commitments WHERE last_updated >= :updated_from)")


# The indexed way pays for a narrow window only: since 26 Oct 16:20 (104,320 lines) it took 108 s where
# reading every line took 68 s, against 2.7 s instead of 128 s since the day before (30 Oct 2026).
NARROW_WINDOW = 20_000


def changed_is_narrow(db, since) -> bool:
    """Whether few enough rows changed since `since` for the indexed way: a count over the same two
    indexes (economy items of every kind, an upper bound)."""
    from sqlalchemy import text
    n = db.execute(text(
        "SELECT count(*) FROM (SELECT id FROM economy_items WHERE updated_at >= :s "
        "UNION SELECT economy_item_id FROM fts_commitments WHERE last_updated >= :s) x"), {"s": since}).scalar()
    return (n or 0) <= NARROW_WINDOW


def window_sql(where: list, params: dict, window: dict, db=None) -> None:
    """The change window on an FTS list: the shared rule, plus the indexed way to the lines of a narrow
    updated_from window."""
    from api.v1._change_window import sql_window
    sql_window(where, params, window, "e.creation_date", UPDATED)
    since = window.get("updated_from")
    if since is not None and (db is None or changed_is_narrow(db, since)):
        where.append(CHANGED_SINCE)
DATE_SORT = "coalesce(e.document_date, e.creation_date)"
_COLS = (
    "e.id, e.title, e.summary, e.source_kind, e.public_url, e.document_date, e.creation_date, "
    f"{UPDATED} AS updated_at, c.beneficiary, c.country, c.city, c.nuts2, "
    "c.beneficiary_amount_eur, c.commitment_total_eur, c.funding_type, c.programme, c.dg, "
    "c.lc_reference, c.year, c.subject, c.is_coordinator, c.beneficiary_type, c.is_nfpo, c.is_ngo, "
    "c.registration_number, c.vat_number, c.call_id, c.project_id, c.project_acronym, c.project_start, "
    "c.project_end, c.budget_line_name, c.management_type, c.economy_item_id IS NOT NULL AS has_columns"
)


# The file's columns an item reads (tests build stand-in rows from this list).
FILE_COLUMNS = (
    "beneficiary", "country", "city", "nuts2", "beneficiary_amount_eur", "commitment_total_eur", "funding_type",
    "programme", "dg", "lc_reference", "year", "subject", "is_coordinator", "beneficiary_type", "is_nfpo", "is_ngo",
    "registration_number", "vat_number", "call_id", "project_id", "project_acronym", "project_start", "project_end",
    "budget_line_name", "management_type",
)


def cols(with_body: bool) -> str:
    return _COLS + (", e.body_txt, e.body_html" if with_body else ", NULL::text AS body_txt, NULL::text AS body_html")


class FtsItem(BaseModel):
    id: int = Field(..., description="Stable Brubru item id (use it on the item route).")
    body_code: str = Field("commission", description="Always 'commission' (FTS is a Commission system).")
    body_name: Optional[str] = Field(None, description="The body's name, as Brubru's directory of EU bodies gives it for body_code.")
    status: Optional[str] = Field(None, description="Always null: a payment record has no status (the funding standard's shared field).")
    item_type: str = Field("funding_recipient", description="Always 'funding_recipient'.")
    title: str = Field(..., description="The beneficiary's name.")
    summary: Optional[str] = None
    source_kind: Optional[str] = Field(None, description="'fts'.")
    beneficiary: Optional[str] = Field(None, description="Who received the money, as the FTS file names it.")
    country: Optional[str] = Field(None, description="Beneficiary country, as the FTS file names it (e.g. Belgium).")
    city: Optional[str] = None
    nuts2: Optional[str] = Field(None, description="The beneficiary's NUTS 2 region, as the FTS file names it.")
    amount_eur: Optional[float] = Field(None, description="This beneficiary's contracted amount, EUR (the FTS file's own figure for it).")
    commitment_total_eur: Optional[float] = Field(None, description="The whole legal commitment's total (A+B), EUR, shared by all its beneficiaries.")
    funding_type: Optional[str] = Field(None, description="The FTS 'Type of contract': Action Grant, Contribution Agreements, or a procurement category (e.g. 'Advisory: non-IT').")
    programme: Optional[str] = Field(None, description="Full FTS programme name.")
    dg: Optional[str] = Field(None, description="Responsible department (the DG or agency that pays), e.g. 'CNECT - ...'.")
    contract_ref: Optional[str] = Field(None, description="Reference of the legal commitment.")
    year: Optional[int] = Field(None, description="The FTS file's year.")
    subject: Optional[str] = Field(None, description="What the money was for.")
    is_coordinator: Optional[bool] = Field(None, description="Whether the beneficiary coordinates the grant (FTS 'Coordinator').")
    beneficiary_type: Optional[str] = Field(None, description="FTS beneficiary type (e.g. Private Companies, Public bodies).")
    is_nfpo: Optional[bool] = Field(None, description="Not-for-profit organisation (FTS).")
    is_ngo: Optional[bool] = Field(None, description="Non-governmental organisation (FTS).")
    registration_number: Optional[str] = Field(None, description="The beneficiary's main registration number (FTS).")
    vat_number: Optional[str] = None
    call_id: Optional[str] = Field(None, description="The call the grant came from, when the FTS file names one.")
    project_id: Optional[str] = Field(None, description="Grant agreement number: the project at /api/v2/funding/ft-funded-projects/{project_id} when Brubru holds it.")
    project_acronym: Optional[str] = None
    project: Optional[str] = Field(None, description=(
        "The project this commitment funds, on /api/v2/funding/ft-funded-projects, when Brubru holds it "
        "(30 Oct 2026: 46,200 of 46,476 lines with a project_id). The project's eu_contribution and its "
        "beneficiaries' amounts are the same money: do not add them."))
    start_date: Optional[date] = Field(None, description="The project's start, where the FTS file gives one (the name on /ft-funded-projects).")
    end_date: Optional[date] = Field(None, description="The project's end, where the FTS file gives one.")
    project_start: Optional[date] = Field(None, **legacy("start_date"))
    project_end: Optional[date] = Field(None, **legacy("end_date"))
    budget_line: Optional[str] = Field(None, description="Budget line name.")
    management_type: Optional[str] = None
    public_url: Optional[str] = Field(None, description="The FTS record's address.")
    body_txt: Optional[str] = Field(None, description="The record as text (on the list unless include_body=false, and on the item route).")
    body_html: Optional[str] = None
    document_date: Optional[datetime] = Field(None, description="The project's start, when already passed; null otherwise.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first stored the row.")
    updated_date: Optional[datetime] = Field(None, description="When the row or its FTS values last changed, for incremental sync.")

    @model_validator(mode="after")
    def _standard_names(self):
        # One name per concept (Phase 2 step 4, 28 Oct 2026): the project's dates as on /ft-funded-projects.
        self.start_date = self.start_date or self.project_start
        self.end_date = self.end_date or self.project_end
        return self


def with_projects(db, items: list, base: str) -> list:
    """Each item's `project`: the funded project's item when Brubru holds its grant agreement (one query a page)."""
    ids = sorted({i.project_id for i in items if getattr(i, "project_id", None)})
    if ids:
        from urllib.parse import quote
        from sqlalchemy import text
        held = {r.project_id for r in db.execute(text(
            "SELECT project_id FROM ft_funded_projects WHERE NOT is_test AND project_id = ANY(:ids)"), {"ids": ids}).fetchall()}
        for i in items:
            if i.project_id in held:
                i.project = f"{base.rstrip('/')}/api/v2/funding/ft-funded-projects/{quote(str(i.project_id), safe='')}"
    return items


def to_item(r, *, with_body: bool, model=FtsItem, **extra):
    return model(
        id=r.id, title=r.title, summary=r.summary, source_kind=r.source_kind,
        beneficiary=r.beneficiary or r.title, country=r.country, city=r.city, nuts2=r.nuts2,
        amount_eur=float(r.beneficiary_amount_eur) if r.beneficiary_amount_eur is not None else None,
        commitment_total_eur=float(r.commitment_total_eur) if r.commitment_total_eur is not None else None,
        funding_type=r.funding_type, programme=r.programme, dg=r.dg, contract_ref=r.lc_reference,
        year=r.year, subject=r.subject, is_coordinator=r.is_coordinator, beneficiary_type=r.beneficiary_type,
        is_nfpo=r.is_nfpo, is_ngo=r.is_ngo, registration_number=r.registration_number,
        vat_number=r.vat_number, call_id=r.call_id, project_id=r.project_id,
        project_acronym=r.project_acronym, project_start=r.project_start, project_end=r.project_end,
        budget_line=r.budget_line_name, management_type=r.management_type, public_url=r.public_url,
        body_txt=(r.body_txt if with_body else None), body_html=(r.body_html if with_body else None),
        document_date=r.document_date, creation_date=r.creation_date, updated_date=row_updated(r),
        **extra,
    )


def filters(where: list, params: dict, *, dg=None, funding_type=None, programme=None, country=None,
            year=None, min_amount_eur=None, max_amount_eur=None, coordinator=None, project_id=None,
            call_id=None, vat=None) -> None:
    """The field filters, on the file's columns."""
    for col, val, key in (("c.dg", dg, "dg"), ("c.funding_type", funding_type, "ft"),
                          ("c.programme", programme, "prog")):
        if val:
            where.append(f"{col} ILIKE :{key}")
            params[key] = f"%{val}%"
    # A two-letter country is a code, matched on the code read from the file's English name (EL and
    # GR, UK and GB are one country); a substring of "BE" would also match Uzbekistan. Longer: the name.
    if country and len(country.strip()) == 2:
        where.append("c.country_code = :ctry"); params["ctry"] = eu_code(country)
    elif country:
        where.append("c.country ILIKE :ctry"); params["ctry"] = f"%{country}%"
    if year:
        where.append("c.year = :year"); params["year"] = year
    if min_amount_eur is not None:
        where.append("c.beneficiary_amount_eur >= :min_amt"); params["min_amt"] = min_amount_eur
    if max_amount_eur is not None:
        where.append("c.beneficiary_amount_eur <= :max_amt"); params["max_amt"] = max_amount_eur
    if coordinator is not None:
        where.append("c.is_coordinator = :coord"); params["coord"] = coordinator
    if project_id:
        where.append("c.project_id = :pid"); params["pid"] = project_id
    if call_id:
        where.append("c.call_id = :cid"); params["cid"] = call_id
    if vat:
        # The indexed key (letters and digits, upper case), not the file's spelling: an expression on
        # vat_number read every row and timed out on production (26 Oct 2026).
        where.append("c.vat_key = :vat"); params["vat"] = vat_key(vat)

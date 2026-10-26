"""
EU Financial Transparency System (FTS) — the database behind
/api/v2/commission/eu-funding-recipients.

Source: the FTS annual datasets on the EU Open Data Portal, published as one
Excel file per year at
  https://ec.europa.eu/budget/financial-transparency-system/download/<year>_FTS_dataset_en.xlsx
Each row is one beneficiary's share of a legal commitment (grant, procurement
contract, prize, etc.) under EU direct management. We ingest the most recent
complete year (auto-discovered). The row IS the content — no per-row fetch, no LLM.

The legal-commitment reference repeats across rows (one commitment can have many
beneficiaries), so the unique key is a hash of the salient fields.
"""
from __future__ import annotations

import hashlib
import io
from datetime import datetime, timezone

import requests
# openpyxl is imported lazily inside the one function that needs it (below), so a
# missing optional Excel dependency can never break importing this module -- which
# sync_economy.py imports at top level for EVERY body. A hard top-level import here
# froze ALL economy ingestion on prod ~25 Jun to 10 Jul 2026 (openpyxl not in
# requirements.txt at the time). Fixed 10 Jul: added to requirements + made lazy.

from services.scrapers.economy_common import Item, clean, _iso_dt

_BASE = "https://ec.europa.eu/budget/financial-transparency-system/download"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")


def _fetch_latest() -> tuple[int, bytes] | None:
    """The most recent year whose Excel file actually exists. The server returns
    a 200 HTML page for not-yet-published years, so we validate the XLSX (zip)
    magic bytes rather than trusting the status code."""
    now = datetime.now(timezone.utc).year
    for y in range(now, 2006, -1):
        try:
            r = requests.get(f"{_BASE}/{y}_FTS_dataset_en.xlsx",
                             headers={"User-Agent": _UA}, timeout=240)
            if r.status_code == 200 and r.content[:2] == b"PK":
                return y, r.content
        except requests.RequestException:
            continue
    return None


def _col(idx: dict, *subs: str):
    for sub in subs:
        for h, i in idx.items():
            if h and sub.lower() in h.lower():
                return i
    return None


def read_fts_file(year: int | None = None) -> tuple[int, bytes] | None:
    """(year, the year's Excel bytes): the year asked for, else the most recent published."""
    if year:
        try:
            r = requests.get(f"{_BASE}/{year}_FTS_dataset_en.xlsx", headers={"User-Agent": _UA}, timeout=240)
        except requests.RequestException:
            return None
        return (year, r.content) if r.status_code == 200 and r.content[:2] == b"PK" else None
    return _fetch_latest()


def _norm_header(h) -> str:
    return " ".join(str(h or "").replace("\u2019", "'").lower().split())


def _exact(idx: dict, *names: str):
    """The column whose header is one of `names` (case, spacing and apostrophes ignored).
    `_col`'s substring match cannot tell "Beneficiary's contracted amount (EUR)" from
    "Beneficiary's estimated contracted amount (EUR)" or "Commitment contracted amount (EUR) (A)"."""
    wanted = {_norm_header(n) for n in names}
    for h, i in idx.items():
        if _norm_header(h) in wanted:
            return i
    return None


_NOT_GIVEN = {None, "", "-", "*****", "N/A - Not applicable", "N/A"}


def _yes(v):
    s = str(v).strip().lower() if v is not None else ""
    return True if s == "yes" else False if s == "no" else None


def _num(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _day(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    d = _iso_dt(str(v)[:10])
    return d.date() if d else None


def fts_records(raw: bytes, year: int):
    """One dict per beneficiary row of the year's FTS file, with every column the file states
    (26 Oct 2026: until then only text lines were kept, so the fields could only be parsed back
    from our own body). `key` and `public_url` are the economy_items row's, computed as before."""
    from openpyxl import load_workbook  # lazy import (see module-top note)
    ws = load_workbook(io.BytesIO(raw), read_only=True).active
    rows = ws.iter_rows(values_only=True)
    header = list(next(rows))
    idx = {h: i for i, h in enumerate(header)}
    c_name = _col(idx, "Name of benefic")
    c_lc = _col(idx, "Reference of the Leg")
    c_bref = _col(idx, "Reference (Budget)")
    c_amt = _col(idx, "Commitment  total", "Commitment total")
    if c_name is None:
        return
    # "Funding type" became "Type of contract*" (Action Grant, Contribution Agreements, the
    # procurement categories) in the files the Commission re-saved on 29 Sep / 1 Oct 2026: no
    # 2025 row had a funding type, so /international-cooperation served funding_type null.
    cols = {
        "budget": _exact(idx, "Budget"),
        "registration_number": _exact(idx, "Main registration number of beneficiary"),
        "vat_number": _exact(idx, "VAT number of beneficiary"),
        "is_nfpo": _exact(idx, "Not-for-profit organisation (NFPO)"),
        "is_ngo": _exact(idx, "Non-governmental organisation (NGO)"),
        "is_coordinator": _exact(idx, "Coordinator"),
        "city": _exact(idx, "City"),
        "country": _col(idx, "Beneficiary country"),
        "nuts2": _exact(idx, "NUTS2"),
        "beneficiary_amount_eur": _exact(idx, "Beneficiary's contracted amount (EUR)"),
        "beneficiary_estimated_amount_eur": _exact(idx, "Beneficiary's estimated contracted amount (EUR)"),
        "beneficiary_estimated_consumed_eur": _exact(idx, "Beneficiary's estimated consumed amount (EUR)"),
        "commitment_contracted_eur": _exact(idx, "Commitment contracted amount (EUR) (A)"),
        "commitment_adjustment_eur": _exact(idx, "Additional/Reduced amount (EUR) (B)"),
        "commitment_total_eur": c_amt,
        "commitment_consumed_eur": _exact(idx, "Commitment consumed amount (EUR)"),
        "amount_source": _exact(idx, "Source of (estimated) detailed amount"),
        "expense_type": _exact(idx, "Expense type"),
        "call_id": _exact(idx, "Call ID"),
        "project_id": _exact(idx, "Project ID"),
        "project_acronym": _exact(idx, "Project Acronym"),
        "subject": _col(idx, "Subject of grant"),
        "dg": _col(idx, "Responsible depart"),
        "budget_line_number": _exact(idx, "Budget line number"),
        "budget_line_name": _col(idx, "Budget line name"),
        "programme": _col(idx, "Programme name"),
        "beneficiary_type": _exact(idx, "Beneficiary type"),
        "project_start": _col(idx, "Project start"),
        "project_end": _exact(idx, "Project end date"),
        "funding_type": _col(idx, "Funding type", "Type of contract"),
        "management_type": _col(idx, "Management type"),
        "benefiting_country": _exact(idx, "Benefiting country"),
    }
    numeric = {k for k in cols if k.endswith("_eur")}
    flags = {"is_nfpo", "is_ngo", "is_coordinator"}
    dates = {"project_start", "project_end"}

    def g(row, i):
        if i is None or i >= len(row):
            return None
        v = row[i]
        return None if (v in _NOT_GIVEN or (isinstance(v, str) and v.strip() in _NOT_GIVEN)) else v

    def g_key(row, i):  # the loader's own notion of an empty cell: keys and URLs stay those stored
        if i is None or i >= len(row):
            return None
        v = row[i]
        return v if v not in (None, "", "-", "*****") else None

    seen: set[str] = set()
    for row in rows:
        name = clean(g_key(row, c_name))
        if not name:
            continue
        lc = g_key(row, c_lc) or ""
        bref = g_key(row, c_bref) or ""
        amount = g_key(row, c_amt)
        key = hashlib.md5(f"{lc}|{bref}|{name}|{amount}".encode("utf-8")).hexdigest()[:12]
        if key in seen:
            continue
        seen.add(key)
        rec = {"key": key, "year": year, "beneficiary": name,
               "lc_reference": lc if lc not in _NOT_GIVEN else None,
               "budget_reference": bref if bref not in _NOT_GIVEN else None,
               "public_url": f"https://ec.europa.eu/budget/financial-transparency-system/index.html#{year}-{key}"}
        for field, i in cols.items():
            v = g(row, i)
            if field in numeric:
                rec[field] = _num(v)
            elif field in flags:
                rec[field] = _yes(v)
            elif field in dates:
                rec[field] = _day(v)
            else:
                rec[field] = clean(str(v)) if v is not None else None
        yield rec


def ingest_eu_funding_recipients(*, fetch_bodies: bool = True, year: int | None = None,
                                 **_) -> list[Item]:
    if year:
        try:
            raw = requests.get(f"{_BASE}/{year}_FTS_dataset_en.xlsx",
                               headers={"User-Agent": _UA}, timeout=240).content
        except requests.RequestException:
            return []
    else:
        found = _fetch_latest()
        if not found:
            return []
        year, raw = found
    try:
        from openpyxl import load_workbook  # lazy import (see module-top note)
        ws = load_workbook(io.BytesIO(raw), read_only=True).active
    except (ValueError, OSError, ImportError):
        return []
    rows = ws.iter_rows(values_only=True)
    header = list(next(rows))
    idx = {h: i for i, h in enumerate(header)}
    c_name = _col(idx, "Name of benefic")
    c_lc = _col(idx, "Reference of the Leg")
    c_bref = _col(idx, "Reference (Budget)")
    c_amt = _col(idx, "Commitment  total", "Commitment total")
    c_prog = _col(idx, "Programme name")
    c_subj = _col(idx, "Subject of grant")
    c_cty = _col(idx, "Beneficiary country")
    # "Funding type" became "Type of contract*" (Action Grant, Contribution Agreements, the
    # procurement categories) in the files the Commission re-saved on 29 Sep / 1 Oct 2026: no
    # 2025 row had a funding type, so /international-cooperation served funding_type null.
    c_fund = _col(idx, "Funding type", "Type of contract")
    c_mgmt = _col(idx, "Management type")
    c_dept = _col(idx, "Responsible depart")
    c_bln = _col(idx, "Budget line name")
    c_start = _col(idx, "Project start")
    if c_name is None:
        return []

    def g(row, i):
        if i is None or i >= len(row):
            return None
        v = row[i]
        return v if v not in (None, "", "-", "*****") else None

    now = datetime.now(timezone.utc)
    items: list[Item] = []
    seen: set[str] = set()
    for row in rows:
        name = clean(g(row, c_name))
        if not name:
            continue
        lc = g(row, c_lc) or ""
        bref = g(row, c_bref) or ""
        amount = g(row, c_amt)
        key = hashlib.md5(f"{lc}|{bref}|{name}|{amount}".encode("utf-8")).hexdigest()[:12]
        if key in seen:
            continue
        seen.add(key)
        url_row = f"https://ec.europa.eu/budget/financial-transparency-system/index.html#{year}-{key}"
        prog = clean(g(row, c_prog))
        country = clean(g(row, c_cty))
        fund = clean(g(row, c_fund))
        subj = clean(g(row, c_subj))
        start = g(row, c_start)
        start_dt = _iso_dt(str(start)[:10]) if start else None
        if start_dt is not None and start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        # The row's date is its project start; a start still to come is not a date the record
        # carries yet, and it sorted commitments for 2027-2028 to the top of the feed (20 Oct
        # 2026: 33 rows). It stays in the body. No start at all: NULL, never 1 January of the
        # year (a year read as 1 January is how 57 FRA rows were misdated).
        doc_dt = start_dt if start_dt and start_dt <= now else None
        amt_str = None
        if amount is not None:
            try:
                amt_str = f"EUR {float(amount):,.0f}"
            except (TypeError, ValueError):
                amt_str = str(amount)
        lines = [
            f"Beneficiary: {name}",
            f"EU commitment (total): {amt_str}" if amt_str else "",
            f"Funding type: {fund}" if fund else "",
            f"Programme: {prog}" if prog else "",
            f"Subject: {subj}" if subj else "",
            f"Responsible department: {clean(g(row, c_dept))}" if g(row, c_dept) else "",
            f"Budget line: {clean(g(row, c_bln))}" if g(row, c_bln) else "",
            f"Management type: {clean(g(row, c_mgmt))}" if g(row, c_mgmt) else "",
            f"Beneficiary country: {country}" if country else "",
            f"Legal commitment ref: {lc}" if lc else "",
            f"Project start: {start_dt.date().isoformat()}" if start_dt else "",
            f"Year: {year}",
        ]
        lines = [l for l in lines if l]
        items.append(Item(
            body_code="commission", item_type="funding_recipient", title=name,
            public_url=url_row,
            summary=clean(" | ".join(x for x in [name, amt_str or "", prog or "", country or ""] if x)),
            body_txt=clean("\n".join(lines)),
            body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
            document_date=doc_dt, creation_date=now, source_kind="fts", guid=key))
    return items

"""Decentralised EU agency procurement / grants / calls.

Each EU body publishes its own tenders, grants and calls for expression of
interest on its own site, in its own markup, so this module collects per-agency
parsers feeding a shared schema (economy_items, item_type tender|grant|eoi_call).
Common helpers live here; agency-specific extraction lives in small functions.

Schema packed into the 5 datapoints:
  title           = tender/call title
  summary         = "reference · status · deadline"
  body_txt        = title + reference + status + deadline (+ procedure type)
  document_date   = deadline (closing date) where present, else publication
  public_url      = the tender/call page;  guid = reference (fallback URL)
  body_code       = the agency;  item_type = tender | grant | eoi_call

Cedefop (30 Sep 2026) is the first body on the corrected shape: document_date =
publication date, and tender_reference / status / deadline as their own columns
(migration 256), carried in Item.extras. The other agencies still use the packing
above until each is walked in the API audit.
"""
from __future__ import annotations

import html as _html
import json
import re
from datetime import datetime, timezone
from urllib.parse import quote, unquote

import requests

from services.scrapers.economy_common import Item, clean

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")
_HEADERS = {"User-Agent": _UA}
_DATE = re.compile(r'(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Z][a-z]{2,8}\s+\d{4})')


def _txt(x: str) -> str:
    return _html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x or ""))).strip()


def _row_url(base: str, href: str, reference: str, title: str) -> str:
    """A per-row URL. Use the row's own link if present; otherwise make the listing
    URL unique with a #fragment so rows don't collide on the UNIQUE(public_url)."""
    if href:
        return href if href.startswith("http") else base + href
    frag = reference or title[:60]
    return f"{base}#{quote(frag, safe='')}"


def _parse_date(s: str) -> datetime | None:
    s = (s or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d %B %Y", "%d %b %Y",
                "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _build(*, body_code: str, item_type: str, title: str, url: str, reference: str = "",
           status: str = "", deadline: datetime | None, now: datetime,
           source_kind: str) -> Item:
    bits = [b for b in [reference, status, deadline.date().isoformat() if deadline else ""] if b]
    lines = [title,
             f"Reference: {reference}" if reference else "",
             f"Status: {status}" if status else "",
             f"Deadline: {deadline.date()}" if deadline else ""]
    lines = [l for l in lines if l]
    return Item(
        body_code=body_code, item_type=item_type, title=clean(title)[:120], public_url=url,
        summary=clean(" · ".join(bits)) or clean(title)[:120],
        body_txt=clean("\n".join(lines)),
        body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
        document_date=deadline, creation_date=now, source_kind=source_kind,
        guid=reference or url)


# --------------------------------------------------------------------------- #
# Drupal "Views table" agencies (one <tr> per item, cells tagged
# views-field-<field>). Confirmed for EFCA; reusable for any EU-theme Views
# table by passing the field-class names.
# --------------------------------------------------------------------------- #
def parse_views_table(html: str, base: str, *, body_code: str, item_type: str,
                      source_kind: str, ref_field: str, title_field: str = "title",
                      deadline_field: str | None = None, status: str = "") -> list[Item]:
    now = datetime.now(timezone.utc)
    out: list[Item] = []
    body = re.search(r"<tbody>(.*?)</tbody>", html, re.S)
    if not body:
        return out
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", body.group(1), re.S):
        def cell(field: str) -> str:
            m = re.search(rf'views-field-{re.escape(field)}[^>]*>(.*?)</td>', row, re.S)
            return m.group(1) if m else ""
        title_cell = cell(title_field)
        am = re.search(r'href="([^"]+)"', title_cell)
        title = _txt(title_cell)
        if not title:
            continue
        href = am.group(1) if am else ""
        reference = _txt(cell(ref_field))
        url = _row_url(base, href, reference, title)
        dl = _parse_date(_DATE.search(_txt(cell(deadline_field))).group(1)) if (
            deadline_field and _DATE.search(_txt(cell(deadline_field)))) else None
        st = status or _txt(cell("field-opencall-status"))
        out.append(_build(body_code=body_code, item_type=item_type, title=title, url=url,
                          reference=reference, status=st, deadline=dl, now=now,
                          source_kind=source_kind))
    return out


def parse_positional_table(html: str, base: str, *, body_code: str, item_type: str,
                           source_kind: str, title_col: int, deadline_col: int,
                           ref_col: int | None = None, status: str = "") -> list[Item]:
    """For Views tables with un-named columns (e.g. EMA value-1..value-4):
    parse <td> cells by position (0-indexed)."""
    now = datetime.now(timezone.utc)
    out: list[Item] = []
    body = re.search(r"<tbody>(.*?)</tbody>", html, re.S)
    if not body:
        return out
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", body.group(1), re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) <= max(title_col, ref_col or 0, deadline_col):
            continue
        title = _txt(cells[title_col])
        if not title:
            continue
        am = re.search(r'href="([^"]+)"', cells[title_col])
        href = am.group(1) if am else ""
        reference = _txt(cells[ref_col]) if ref_col is not None else ""
        url = _row_url(base, href, reference, title)
        dm = _DATE.search(_txt(cells[deadline_col]))
        dl = _parse_date(dm.group(1)) if dm else None
        out.append(_build(body_code=body_code, item_type=item_type, title=title, url=url,
                          reference=reference, status=status, deadline=dl, now=now,
                          source_kind=source_kind))
    return out


def _fetch(url: str) -> str:
    return requests.get(url, headers=_HEADERS, timeout=40).text


def _split_calls(items: list[Item]) -> tuple[list[Item], list[Item]]:
    """Split a procurement listing into (tenders, eoi_calls) by reference / title."""
    tenders, calls = [], []
    for it in items:
        ref = (it.guid or "").upper()
        is_eoi = "/CEI" in ref or "EOI" in ref or "expression of interest" in it.title.lower()
        (calls if is_eoi else tenders).append(it)
    return tenders, calls


# --------------------------------------------------------------------------- #
# Cedefop — the WHOLE archive (every listing page) plus each procedure's own page.
#
# Audit 30 Sep 2026 (API Audit doc, "Walk · cedefop"): the old reader took page 0
# only (27 of 464 procedures), dropped the listing's status column, stored the
# closing date as document_date and never saw an EXTENDED closing date, so an open
# tender (CEDEFOP/2026/OP/0012) read as closed. The detail page states everything:
#   Procurement type | Status | Official Publication Date | Closing date |
#   Extended closing date (when extended) | Reference | Downloads
# Field names reuse the funding folder's (Victor, 30 Sep): tender_reference,
# status (open | forthcoming | closed) and deadline travel in Item.extras; the
# Official Publication Date is document_date.
# --------------------------------------------------------------------------- #
_CEDEFOP = "https://www.cedefop.europa.eu"
_CEDEFOP_LISTING = _CEDEFOP + "/en/about-cedefop/public-procurement"
_CEDEFOP_MAX_PAGES = 60      # 20 pages on 30 Sep 2026; a stop, not an expectation
# Rows on the first listing pages, and every open or in-progress procedure, get a
# fresh detail read on every run (that is where deadlines move). Older, finished
# procedures are read once, by a run with CEDEFOP_FULL_DETAILS=1; later runs send
# no date and no body for them, and the upsert keeps what is stored.
_CEDEFOP_FRESH_PAGES = 2
_CEDEFOP_LIVE = {"open", "in progress"}
_CEDEFOP_CACHE: dict = {}    # one crawl serves both ingest functions in a run
_CEDEFOP_CACHE_TTL = 1800


def _get_ok(url: str) -> str:
    """GET that fails loudly: an error page must not parse to zero rows."""
    r = requests.get(url, headers=_HEADERS, timeout=40)
    r.raise_for_status()
    return r.text


def _cedefop_listing_rows(html: str) -> list[dict]:
    body = re.search(r"<tbody>(.*?)</tbody>", html, re.S)
    if not body:
        return []
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body.group(1), re.S):
        def cell(field: str) -> str:
            m = re.search(rf'views-field-{field}[^>]*>(.*?)</td>', tr, re.S)
            return m.group(1) if m else ""
        title_cell = cell("title")
        title = _txt(title_cell)
        if not title:
            continue
        am = re.search(r'href="([^"]+)"', title_cell)
        href = _html.unescape(am.group(1)) if am else ""
        reference = _txt(cell("field-ced-procurement-reference"))
        dm = _DATE.search(_txt(cell("field-ced-closing-date-time")))
        rows.append({
            "title": title,
            "url": _row_url(_CEDEFOP, href, reference, title),
            "reference": reference,
            "closing": _parse_date(dm.group(1)) if dm else None,
            "status_raw": _txt(cell("field-ced-procurement-status")),
        })
    return rows


_CEDEFOP_LABELS = ("Procurement type", "Status", "Official Publication Date", "Closing date",
                   "Extended closing date", "Reference", "Related Country", "Downloads")


def _cedefop_detail(url: str) -> dict:
    """Read one procedure page: description, the Call details block, downloads."""
    page = _get_ok(url.split("#")[0])
    main = re.search(r"<h1.*?</h1>(.*?)(?:<footer|region-footer)", page, re.S)
    main = main.group(1) if main else page
    parts = re.split(r"Call details", main, maxsplit=1)
    desc_html = parts[0]
    details = _txt(parts[1]) if len(parts) > 1 else ""
    out: dict = {}
    # "Label value Label value ..." -> dict, by the known labels in page order.
    pat = "|".join(re.escape(l) for l in sorted(_CEDEFOP_LABELS, key=len, reverse=True))
    marks = [(m.start(), m.end(), m.group(0)) for m in re.finditer(pat, details)]
    for i, (_s, e, label) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(details)
        out.setdefault(label, details[e:end].strip())
    paras = [p for p in (_txt(x) for x in re.findall(r"<p[^>]*>(.*?)</p>", desc_html, re.S)) if p]
    # The first paragraph repeats the reference; keep the rest.
    ref = out.get("Reference", "")
    out["description"] = [p for p in paras if p != ref]
    out["links"] = sorted(set(re.findall(
        r'href="(https?://(?:ted\.europa\.eu|ec\.europa\.eu/info/funding-tenders)[^"]+)"', desc_html)))
    out["documents"] = _cedefop_documents(page)
    return out


def _documents_txt(docs: list[dict]) -> list[str]:
    """The procedure body's list of its files (procurement_documents holds their text)."""
    return [f"Document: {d['title']} ("
            + ", ".join(x for x in [(d.get("file_format") or "").upper(),
                                    d["document_date"].isoformat() if d.get("document_date") else ""] if x)
            + f") {d['file_url']}" for d in docs]


def _documents_html(docs: list[dict]) -> str:
    if not docs:
        return ""
    return "<h2>Documents</h2><ul>" + "".join(
        f'<li><a href="{_html.escape(d["file_url"])}">{_html.escape(d["title"])}</a>'
        + "".join(f" · {_html.escape(x)}" for x in [(d.get("file_format") or "").upper(),
                  d["document_date"].isoformat() if d.get("document_date") else ""] if x)
        + "</li>" for d in docs) + "</ul>"


# 27 Nov 2009 is Cedefop's site-migration stamp, not a file's date: measured 30 Sep 2026
# over all 464 procedure pages it sits on 720 of 1,500 dated files, across 110 procedures
# published 2004-2009, and no other date appears on more than 5 procedures (the ECDC
# 27 Jul 2017 pattern). Those files get no date rather than a wrong one.
_CEDEFOP_MIGRATION_STAMP = datetime(2009, 11, 27, tzinfo=timezone.utc)


def _cedefop_documents(page: str) -> list[dict]:
    """The Downloads block: one entry per file (a document in two languages is two files).
      <div class="dfu-file file-pdf"> <p class="dfu-file-title">Title</p>
        <div class="dfu-metadata"><span>27/11/2009</span></div>
        <span class="file-lang"><a href=".." type="application/pdf; length=65714" lang="en">
    The date is the one Cedefop shows next to the file; absent, or the site-migration
    stamp, it stays None."""
    group = re.search(r'id="group-downloads"(.*?)(?:id="group-(?!downloads)|<footer|$)', page, re.S)
    if not group:
        return []
    docs = []
    for block in re.split(r'<div\s+class="dfu-file[\s"]', group.group(1))[1:]:
        tm = re.search(r'class="dfu-file-title"[^>]*>(.*?)</p>', block, re.S)
        dm = re.search(r'class="dfu-metadata"[^>]*>\s*<span[^>]*>([^<]+)</span>', block, re.S)
        title = _txt(tm.group(1)) if tm else ""
        date = _parse_date(dm.group(1).strip()) if dm else None
        if date == _CEDEFOP_MIGRATION_STAMP:
            date = None
        for a in re.findall(r'<span class="file-lang">\s*(<a\b[^>]*>)', block, re.S):
            hm = re.search(r'href="([^"]+)"', a)
            if not hm:
                continue
            url = _html.unescape(hm.group(1))
            if url.startswith("/"):
                url = _CEDEFOP + url
            lm = re.search(r'\blang="([^"]+)"', a)
            sm = re.search(r'length=(\d+)', a)
            name = unquote(url.rsplit("/", 1)[-1])
            fm = re.search(r"\.([A-Za-z0-9]{2,5})$", name)
            docs.append({"title": title or name, "file_url": url, "file_name": name,
                         "file_format": fm.group(1).lower() if fm else None,
                         "file_size": int(sm.group(1)) if sm else None,
                         "language": lm.group(1).lower() if lm else None,
                         "document_date": date.date() if date else None})
    return docs


def _cedefop_status(raw: str, deadline: datetime | None, now: datetime) -> str:
    """Normalise to the Funding & Tenders vocabulary. "Open" is a claim that needs a
    deadline still ahead (the consultations `_status` rule); "In progress" means
    evaluation, closed to bidders."""
    if raw.strip().lower() == "open" and deadline is not None and deadline >= now:
        return "open"
    return "closed"


def _cedefop_item(row: dict, detail: dict | None, now: datetime) -> Item:
    ptype = (detail or {}).get("Procurement type", "")
    is_call = ("expression of interest" in ptype.lower()) if ptype else (
        "/CEI" in row["reference"].upper() or "EOI" in row["reference"].upper()
        or "expression of interest" in row["title"].lower())
    extended = _parse_date((detail or {}).get("Extended closing date", ""))
    closing = _parse_date((detail or {}).get("Closing date", "")) or row["closing"]
    deadline = extended or closing
    published = _parse_date((detail or {}).get("Official Publication Date", ""))
    status = _cedefop_status(row["status_raw"], deadline, now)
    item = Item(
        body_code="cedefop", item_type="eoi_call" if is_call else "tender",
        title=clean(row["title"])[:120], public_url=row["url"],
        summary=clean(" · ".join(b for b in [row["reference"], row["status_raw"],
                                               deadline.date().isoformat() if deadline else ""] if b)),
        creation_date=now, source_kind="cedefop_procurement", guid=row["reference"] or row["url"],
        extras={"tender_reference": row["reference"] or None, "status": status,
                # item_type came from the page's Procurement type only when the page
                # was read; otherwise it is a guess from the reference, and the writer
                # keeps the stored type (sync_economy._keep_stored_type).
                "type_from_page": detail is not None},
    )
    if detail is None:
        # Not re-read this run: send no date, deadline or body, so the stored values stand.
        return item
    facts = [("Reference", row["reference"]), ("Procurement type", ptype),
             ("Status", row["status_raw"] or detail.get("Status", "")),
             ("Official publication date", published.date().isoformat() if published else ""),
             ("Closing date", closing.date().isoformat() if closing else ""),
             ("Extended closing date", extended.date().isoformat() if extended else "")]
    facts = [(k, v) for k, v in facts if v]
    desc = detail.get("description") or []
    links = detail.get("links") or []
    docs = detail.get("documents") or []
    item.body_txt = clean("\n".join([row["title"], *desc, *(f"{k}: {v}" for k, v in facts), *links,
                                     *_documents_txt(docs)]))
    item.body_html = clean(
        f"<h1>{_html.escape(row['title'])}</h1>"
        + "".join(f"<p>{_html.escape(p)}</p>" for p in desc)
        + "<dl>" + "".join(f"<dt>{_html.escape(k)}</dt><dd>{_html.escape(v)}</dd>" for k, v in facts)
        + "</dl>"
        + ("<ul>" + "".join(f'<li><a href="{_html.escape(u)}">{_html.escape(u)}</a></li>' for u in links)
           + "</ul>" if links else "")
        + _documents_html(docs))
    item.document_date = published
    item.extras["deadline"] = deadline
    return item


def _cedefop_all(*, fetch_bodies: bool = True) -> list[Item]:
    import os
    import time
    full = os.environ.get("CEDEFOP_FULL_DETAILS") == "1"
    key = (fetch_bodies, full)
    hit = _CEDEFOP_CACHE.get(key)
    if hit and time.time() - hit[0] < _CEDEFOP_CACHE_TTL:
        return hit[1]
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    seen: set = set()
    for page in range(_CEDEFOP_MAX_PAGES):
        rows = _cedefop_listing_rows(_get_ok(f"{_CEDEFOP_LISTING}?page={page}"))
        if not rows:
            break
        for row in rows:
            ident = row["reference"] or row["url"]
            if ident in seen:
                continue
            seen.add(ident)
            want = fetch_bodies and (full or page < _CEDEFOP_FRESH_PAGES
                                     or row["status_raw"].lower() in _CEDEFOP_LIVE)
            detail = None
            if want:
                try:
                    detail = _cedefop_detail(row["url"])
                except requests.RequestException as exc:
                    print(f"    [WARN] cedefop detail {row['reference']}: {exc}", flush=True)
            items.append(_cedefop_item(row, detail, now))
    if not items:
        raise RuntimeError("Cedefop procurement listing parsed to zero rows")
    _CEDEFOP_CACHE[key] = (time.time(), items)
    return items


def ingest_cedefop_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return [it for it in _cedefop_all(fetch_bodies=fetch_bodies) if it.item_type == "tender"]


def ingest_cedefop_calls(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return [it for it in _cedefop_all(fetch_bodies=fetch_bodies) if it.item_type == "eoi_call"]


# --------------------------------------------------------------------------- #
# EMA — positional Views table (value-1=published, value-2=title, value-3=ref,
# value-4=deadline).
# --------------------------------------------------------------------------- #
_EMA = "https://www.ema.europa.eu"


def ingest_ema_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return parse_positional_table(
        _fetch(_EMA + "/en/about-us/procurement-grants"), _EMA, body_code="ema",
        item_type="tender", source_kind="ema_procurement",
        title_col=1, ref_col=2, deadline_col=3, status="Open")


# --------------------------------------------------------------------------- #
# EFCA — European Fisheries Control Agency (Drupal Views tables).
#
# API audit, 30 Sep 2026 ("Walk · EFCA"): /en/content/open-calls-tender now lists JOB
# VACANCIES (2 were served as tenders); 26 procedures were stored twice (EFCA moved
# from /en/node/NNN to slug addresses and identity was the address); EFCA's own
# Open/Closed column was overwritten by fixed labels; the deadline was document_date.
# Victor's decisions, 30 Sep: stop reading the vacancies page; identity by EFCA
# reference; status from EFCA's column (open only while Open and the deadline is
# ahead); document_date = the linked Funding & Tenders notice's publication date.
# About 40 pages in all, so every procedure page is read each run.
# --------------------------------------------------------------------------- #
_EFCA = "https://www.efca.europa.eu"
_EFCA_PROCEDURES = _EFCA + "/en/content/negotiated-procedures"   # same table as the procurement plan
_EFCA_CALLS = _EFCA + "/en/content/calls-expression-interest"


def _efca_rows(html: str, *, ref_field: str, deadline_field: str, status_field: str | None) -> list[dict]:
    body = re.search(r"<tbody>(.*?)</tbody>", html, re.S)
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body.group(1) if body else "", re.S):
        def cell(field: str) -> str:
            m = re.search(rf'views-field-{field}[^>]*>(.*?)</td>', tr, re.S)
            return m.group(1) if m else ""
        am = re.search(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', cell("title"), re.S)
        if not am or not _txt(am.group(2)):
            continue
        dm = re.search(r'datetime="([^"]+)"', cell(deadline_field))
        href = _html.unescape(am.group(1))
        rows.append({
            "title": _txt(am.group(2)),
            "url": href if href.startswith("http") else _EFCA + href,
            "reference": _txt(cell(ref_field)),
            "deadline": _iso(dm.group(1)) if dm else None,
            "status_raw": _txt(cell(status_field)) if status_field else "",
        })
    return rows


def _efca_detail(url: str) -> dict:
    page = _get_ok(url)
    m = re.search(r"<h1.*?</h1>(.*?)(?:<footer|ecl-site-footer)", page, re.S)
    block = m.group(1) if m else ""
    text = _txt(block)
    # The procedure's content starts at its "Type" label; before it sit the breadcrumb
    # trail and the title repeated (on calls-for-interest pages).
    start = re.search(r"\bType\s", text)
    text = text[start.start():] if start else text
    notices = list(dict.fromkeys(_FT_NOTICE.findall(page)))
    kind = re.search(r"\bType\s+(.+?)\s+(?:Number|Deadline)\b", text)
    oj = re.search(r"published in the Official Journal[^.]*?on (\d{1,2}/\d{1,2}/\d{4})", text)
    return {"text": text[:4000], "notices": notices,
            "kind": kind.group(1).strip() if kind else "",
            "oj_note": oj.group(0) if oj else ""}


def _efca_item(row: dict, detail: dict | None, *, item_type: str, now: datetime) -> Item:
    deadline = row["deadline"]
    said_open = row["status_raw"].lower() == "open" if row["status_raw"] else True
    status = "open" if said_open and deadline is not None and deadline >= now else "closed"
    ref = row["reference"]
    item = Item(
        body_code="efca", item_type=item_type, title=clean(row["title"])[:120], public_url=row["url"],
        summary=clean(" · ".join(b for b in [ref, row["status_raw"],
                                               deadline.date().isoformat() if deadline else ""] if b)),
        creation_date=now, source_kind="efca_procurement", guid=ref or row["url"],
        extras={"tender_reference": ref or None, "status": status, "deadline": deadline},
    )
    if detail is None:
        return item
    notice = next((n for n in detail["notices"] if n.endswith("-CN")), None) or next(iter(detail["notices"]), None)
    published = _ft_notice_date(notice) if notice else None
    facts = [("Reference", ref), ("Procedure type", detail["kind"]),
             ("Status on EFCA's site", row["status_raw"]),
             ("Funding & Tenders notice", notice or ""),
             ("Notice published", published.date().isoformat() if published else ""),
             ("Deadline", deadline.strftime("%Y-%m-%d %H:%M UTC") if deadline else "")]
    facts = [(k, v) for k, v in facts if v]
    lines = [row["title"], detail["text"], *(f"{k}: {v}" for k, v in facts)]
    item.body_txt = clean("\n".join(l for l in lines if l))
    item.body_html = clean(
        f"<h1>{_html.escape(row['title'])}</h1><p>{_html.escape(detail['text'])}</p>"
        + "<dl>" + "".join(f"<dt>{_html.escape(k)}</dt><dd>{_html.escape(v)}</dd>" for k, v in facts)
        + "</dl>")
    item.document_date = published if published and (deadline is None or published <= deadline) else None
    return item


def _efca_read(listing: str, *, item_type: str, ref_field: str, deadline_field: str,
               status_field: str | None, fetch_bodies: bool) -> list[Item]:
    now = datetime.now(timezone.utc)
    rows = _efca_rows(_get_ok(listing), ref_field=ref_field, deadline_field=deadline_field,
                      status_field=status_field)
    if not rows:
        raise RuntimeError(f"EFCA listing parsed to zero rows: {listing}")
    items, seen = [], set()
    for row in rows:
        ident = row["reference"] or row["url"]
        if ident in seen:
            continue
        seen.add(ident)
        detail = None
        if fetch_bodies:
            try:
                detail = _efca_detail(row["url"])
            except requests.RequestException as exc:
                print(f"    [WARN] efca detail {row['url'][-60:]}: {exc}", flush=True)
        items.append(_efca_item(row, detail, item_type=item_type, now=now))
    return items


def ingest_efca_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _efca_read(_EFCA_PROCEDURES, item_type="tender", ref_field="field-number",
                      deadline_field="field-deadline", status_field="field-opencall-status",
                      fetch_bodies=fetch_bodies)


def ingest_efca_calls(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _efca_read(_EFCA_CALLS, item_type="eoi_call", ref_field="field-expression-interest-number",
                      deadline_field="field-deadline-for-applications", status_field=None,
                      fetch_bodies=fetch_bodies)


# --- EFSA ----------------------------------------------------------------- #
# API audit, 30 Sep 2026 ("Walk · EFSA"): the reader took the FIRST table of
# /en/calls/procurement only (live calls; closed calls drop off the page), stored the
# deadline as document_date, hard-coded "Open" and kept no reference: 10 rows.
# Victor's decisions, 30 Sep: EFSA's notices from SEDIA by its buyer id (314 notices,
# planned calls included, the page's items among them), through the shared reader;
# plus the closed procedures below EUR 140k that only EFSA's own site keeps.
_EFSA = "https://www.efsa.europa.eu"
_EFSA_FT_BUYER_ID = "47352394"
_EFSA_NEGOTIATED = _EFSA + "/en/procurement/closed-negotiated-procedures"
_EFSA_NP_REF = re.compile(r"(NP[/-]EFSA[/-][A-Z]+[/-]\d{4}[/-]\d{2})")


def _efsa_negotiated_cards(html: str) -> list[dict]:
    rows = []
    for art in re.findall(r'<article class="node call[^"]*negotiated-procedures[^"]*">(.*?)</article>', html, re.S):
        am = re.search(r'<a href="([^"]+)"[^>]*>(.*?)</a>', art, re.S)
        if not am:
            continue
        title = _txt(am.group(2))
        rm = _EFSA_NP_REF.search(title)
        bm = re.search(r'field-budget.*?content="([^"]+)"', art, re.S)
        lm = re.search(r'field-start-date.*?field__item">([^<]+)<', art, re.S)
        dm = re.search(r'field-end-date.*?datetime="([^"]+)"', art, re.S)
        href = _html.unescape(am.group(1))
        rows.append({"title": title, "url": href if href.startswith("http") else _EFSA + href,
                     "reference": rm.group(1) if rm else "",
                     "budget": bm.group(1) if bm else "", "launch": _txt(lm.group(1)) if lm else "",
                     "deadline": _iso(dm.group(1)) if dm else None})
    return rows


def _efsa_negotiated(now: datetime) -> list[Item]:
    """EFSA's closed procedures below EUR 140k (its own archive page; no publication date there)."""
    rows, page = [], 0
    while page < 20:
        batch = _efsa_negotiated_cards(_get_ok(f"{_EFSA_NEGOTIATED}?page={page}"))
        if not batch:
            break
        rows += batch
        page += 1
    items = []
    for r in rows:
        deadline = r["deadline"]
        facts = [("Reference", r["reference"]), ("Procedure type", "negotiated procedure below EUR 140,000"),
                 ("Estimated budget", f"EUR {r['budget']}" if r["budget"] else ""),
                 ("Approximate launch", r["launch"]),
                 ("Deadline", deadline.strftime("%Y-%m-%d %H:%M UTC") if deadline else ""),
                 ("Status on EFSA's site", "deadline closed")]
        facts = [(k, v) for k, v in facts if v]
        items.append(Item(
            body_code="efsa", item_type="tender", title=clean(r["title"])[:120], public_url=r["url"],
            summary=clean(" · ".join(b for b in [r["reference"], "negotiated procedure",
                                                   deadline.date().isoformat() if deadline else ""] if b)),
            body_txt=clean("\n".join([r["title"], *(f"{k}: {v}" for k, v in facts), r["url"]])),
            body_html=clean(f"<h1>{_html.escape(r['title'])}</h1><dl>"
                            + "".join(f"<dt>{_html.escape(k)}</dt><dd>{_html.escape(v)}</dd>" for k, v in facts)
                            + "</dl>"),
            document_date=None, creation_date=now, source_kind="efsa_negotiated",
            guid=r["reference"] or r["url"],
            extras={"tender_reference": r["reference"] or None,
                    "status": "open" if deadline is not None and deadline >= now else "closed",
                    "deadline": deadline},
        ))
    return items


def _title_key(title: str) -> str:
    """A title without its procedure reference, lower-case, words only."""
    return re.sub(r"\W+", " ", _EFSA_NP_REF.sub("", title).lower()).strip()


def _efsa_drop_portal_duplicates(portal: list[Item], archive: list[Item]) -> list[Item]:
    """An archive procedure that is also on the portal (as an ex-ante notice) is ONE
    procedure: keep the portal notice, which has a publication date (Victor, 30 Sep
    2026; 4 of 27)."""
    portal_text = [f"{it.title} {it.body_txt or ''}" for it in portal]
    portal_keys = [_title_key(it.title) for it in portal]
    kept = []
    for it in archive:
        ref = it.extras.get("tender_reference")
        key = _title_key(it.title)
        on_portal = (ref and any(ref in t for t in portal_text)) or \
            (len(key) >= 20 and any(key in k or (len(k) >= 20 and k in key) for k in portal_keys))
        if not on_portal:
            kept.append(it)
    return kept


def ingest_efsa_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    now = datetime.now(timezone.utc)
    portal = _ft_buyer_notices(body_code="efsa", buyer_id=_EFSA_FT_BUYER_ID,
                               source_kind="efsa_ft_notice", now=now)
    return portal + _efsa_drop_portal_duplicates(portal, _efsa_negotiated(now))


def parse_field_cards(html: str, base: str, *, body_code: str, item_type: str, source_kind: str,
                      title_substr: str, ref_field: str, deadline_field: str,
                      status: str = "") -> list[Item]:
    """Drupal field-card listings (e.g. Eurojust): one card per item, each with a
    title link plus field--name-field-<X> divs for reference and closing date."""
    now = datetime.now(timezone.utc)
    out: list[Item] = []
    title_re = re.compile(r'<a href="([^"]*' + re.escape(title_substr) + r'[^"#?]*)"[^>]*>(.*?)</a>', re.S)
    matches = list(title_re.finditer(html))
    seen = set()
    for i, m in enumerate(matches):
        href, raw = m.group(1), m.group(2)
        title = _txt(raw)
        if not title or len(title) < 8:
            continue
        url = href if href.startswith("http") else base + href
        if url in seen:
            continue
        seen.add(url)
        win = html[m.end(): matches[i + 1].start() if i + 1 < len(matches) else m.end() + 1800]
        rm = re.search(rf'field--name-field-{re.escape(ref_field)}.*?field__item"[^>]*>([^<]+)', win, re.S)
        reference = _txt(rm.group(1)) if rm else ""
        dm = re.search(
            rf'field--name-field-{re.escape(deadline_field)}.*?(\d{{4}}-\d{{2}}-\d{{2}}|\d{{1,2}}[/.]\d{{1,2}}[/.]\d{{4}}|\d{{1,2}}\s+[A-Z][a-z]+\s+\d{{4}})',
            win, re.S)
        dl = _parse_date(dm.group(1)) if dm else None
        out.append(_build(body_code=body_code, item_type=item_type, title=title, url=url,
                          reference=reference, status=status, deadline=dl, now=now,
                          source_kind=source_kind))
    return out


# --- Eurojust — Drupal field-cards --------------------------------------- #
_EUROJUST = "https://www.eurojust.europa.eu"


def ingest_eurojust_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    items = parse_field_cards(_fetch(_EUROJUST + "/about-us/procurement/ongoing-calls-for-tender"),
                              _EUROJUST, body_code="eurojust", item_type="tender",
                              source_kind="eurojust_procurement", title_substr="/procurement/",
                              ref_field="tender-reference", deadline_field="end-date", status="Open")
    low = parse_field_cards(_fetch(_EUROJUST + "/about-us/procurement/low-value-contracts"),
                            _EUROJUST, body_code="eurojust", item_type="tender",
                            source_kind="eurojust_procurement", title_substr="/procurement/",
                            ref_field="tender-reference", deadline_field="end-date",
                            status="Low-value contract")
    seen = {i.public_url for i in items}
    merged = items + [i for i in low if i.public_url not in seen]
    # keep only real tenders (those carrying a tender reference, not nav links)
    return [i for i in merged if i.guid and not i.guid.startswith("http")]

# --- ETF — field-cards with linked short-title + deadline in body --------- #
_ETF = "https://www.etf.europa.eu"


def ingest_etf_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    # deadline_field="deadline" finds the field; the closing date also appears in
    # the card body ("Deadline ... DD/MM/YYYY"), which the window date-search picks up.
    return parse_field_cards(
        _fetch(_ETF + "/en/about/procurement"), _ETF, body_code="etf", item_type="tender",
        source_kind="etf_procurement", title_substr="/en/about/procurement/",
        ref_field="deadline", deadline_field="deadline", status="Open")


# --- EUAA — Drupal Views positional table -------------------------------- #
_EUAA = "https://euaa.europa.eu"


def ingest_euaa_calls(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return parse_positional_table(
        _fetch(_EUAA + "/about-us/procurement"), _EUAA,
        body_code="euaa", item_type="eoi_call",
        source_kind="euaa_procurement",
        title_col=1, ref_col=0, deadline_col=2, status="Open",
    )


# --- EUDA — plain HTML table (no Drupal markers) -------------------------- #
_EUDA = "https://www.euda.europa.eu"


def ingest_euda_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return parse_positional_table(
        _fetch(_EUDA + "/about/procurement_en"), _EUDA,
        body_code="euda", item_type="tender", source_kind="euda_procurement",
        title_col=1, ref_col=0, deadline_col=3, status="Open",
    )


# --- ENISA — Drupal Views with positional headers + <time datetime> ------- #
_ENISA = "https://www.enisa.europa.eu"


def _parse_enisa_table(html: str, base: str) -> list[Item]:
    """ENISA tbody rows: 5 cells per row. Title cell 0 (with anchor),
    reference cell 1, call-type cell 2, deadline cell 3 (<time datetime>),
    status cell 4."""
    now = datetime.now(timezone.utc)
    out: list[Item] = []
    body = re.search(r"<tbody.*?</tbody>", html, re.S)
    if not body:
        return out
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", body.group(0), re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) < 5:
            continue
        title_html, ref_html, type_html, deadline_html, status_html = cells[:5]
        am = re.search(r'href="([^"]+)"', title_html)
        if not am:
            continue
        title = _txt(title_html)
        if not title:
            continue
        url = am.group(1) if am.group(1).startswith("http") else base + am.group(1)
        reference = _txt(ref_html)
        call_type = _txt(type_html)
        dl = None
        dt_m = re.search(r'datetime="([^"]+)"', deadline_html)
        if dt_m:
            try:
                dl = datetime.fromisoformat(dt_m.group(1).replace("Z", "+00:00"))
            except ValueError:
                dl = None
        if dl is None:
            dm = _DATE.search(_txt(deadline_html))
            dl = _parse_date(dm.group(1)) if dm else None
        status_text = _txt(status_html).upper() or "OPEN"
        is_eoi = ("EXPRESSIONS OF INTEREST" in call_type.upper()
                  or "CEI" in (reference or "").upper())
        out.append(_build(
            body_code="enisa", item_type=("eoi_call" if is_eoi else "tender"),
            title=title, url=url, reference=reference, status=status_text,
            deadline=dl, now=now, source_kind="enisa_procurement",
        ))
    return out


def ingest_enisa_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    items = _parse_enisa_table(_fetch(_ENISA + "/working-with-us/procurement"), _ENISA)
    return [i for i in items if i.item_type == "tender"]


def ingest_enisa_calls(*, fetch_bodies: bool = True, **_) -> list[Item]:
    items = _parse_enisa_table(_fetch(_ENISA + "/working-with-us/procurement"), _ENISA)
    return [i for i in items if i.item_type == "eoi_call"]


# --- ERA — bespoke listing-item cards ------------------------------------- #
_ERA = "https://www.era.europa.eu"


def _parse_era_articles(html: str, base: str) -> list[Item]:
    """ERA <article class="listing-item ..."> cards. Title in a
    <span class="title"> inside <a class="standalone">. Opening/closing date
    is the first <time datetime>. Status badge text-bg-success ("Open").
    The card does not expose a procurement reference, so the URL slug becomes
    the guid (same pattern as the existing ETF parser for low-value cards)."""
    now = datetime.now(timezone.utc)
    out: list[Item] = []
    article_re = re.compile(
        r'<article[^>]*class="[^"]*listing-item[^"]*"[^>]*>(.*?)</article>', re.S)
    for body in article_re.findall(html):
        am = re.search(
            r'<a[^>]+href="(/procurement/[^"]+)"[^>]*>\s*<span class="title">(.*?)</span>',
            body, re.S)
        if not am:
            am = re.search(r'<a[^>]+href="(/procurement/[^"]+)"[^>]*>(.*?)</a>',
                           body, re.S)
        if not am:
            continue
        title = _txt(am.group(2))
        if not title:
            continue
        url = base + am.group(1)
        st_m = re.search(r'badge[^"]*text-bg-success[^"]*"[^>]*>\s*(\w[\w\s-]+?)\s*<',
                         body)
        status = _txt(st_m.group(1)) if st_m else "Open"
        dt_m = re.search(r'<time[^>]+datetime="([^"]+)"', body)
        dl = None
        if dt_m:
            try:
                dl = datetime.fromisoformat(dt_m.group(1).replace("Z", "+00:00"))
            except ValueError:
                dl = None
        reference = am.group(1).rsplit("/", 1)[-1]
        out.append(_build(
            body_code="era", item_type="tender", title=title, url=url,
            reference=reference, status=status, deadline=dl, now=now,
            source_kind="era_procurement",
        ))
    return out


def ingest_era_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _parse_era_articles(
        _fetch(_ERA + "/agency/procurement_en?f%5B0%5D=era_procurement_status%3Aopen"),
        _ERA,
    )


# --- ECDC — ct-procurement article cards, paginated ?page=N --------------- #
# API audit, 30 Sep 2026 ("Walk · ECDC"): the reader took pages 0-3 only (29 of 174
# procedures), looked for a status ECDC never prints (0 rows had one), stored the
# deadline as document_date and composed a 3-line body. ECDC prints no status and no
# visible publication date, but every page carries <meta property="article:published_time">.
# Victor's decisions, 30 Sep: read every page; status derived from the deadline (open
# while ahead); document_date = article:published_time, fallback "Page last updated",
# else NULL; all three kinds (ex-ante publicity, call for tender, call for proposal)
# stay under tender, with the kind in the body. Same fields as Cedefop (Item.extras).
#
# ECDC sits behind CloudFront, which answers 429 after about 60 quick requests with
# Retry-After: 0 (30 Sep 2026). Every ECDC request goes through _ecdc_get: a pause
# between requests and a growing back-off on 429.
_ECDC = "https://www.ecdc.europa.eu"
_ECDC_LISTING = _ECDC + "/en/about-ecdc/procurement-and-grants"
_ECDC_MAX_PAGES = 80         # 35 pages on 30 Sep 2026; a stop, not an expectation
_ECDC_FRESH_PAGES = 2        # re-read these pages' detail pages every run
_ECDC_CACHE: dict = {}
_ECDC_CACHE_TTL = 1800
_ECDC_PAUSE = 2.0                        # seconds between ECDC requests
_ECDC_BACKOFF = (15, 45, 90, 180, 300)   # seconds to wait after each successive 429
_ecdc_last = [0.0]


def _ecdc_get(url: str) -> str:
    """ECDC GET: paced, retrying 429 with a growing back-off, failing loudly otherwise."""
    import time
    for wait in (*_ECDC_BACKOFF, None):
        gap = _ECDC_PAUSE - (time.monotonic() - _ecdc_last[0])
        if gap > 0:
            time.sleep(gap)
        r = requests.get(url, headers=_HEADERS, timeout=40)
        _ecdc_last[0] = time.monotonic()
        if r.status_code != 429:
            r.raise_for_status()
            return r.text
        if wait is None:
            r.raise_for_status()
        print(f"    [INFO] ecdc 429, waiting {wait}s: {url[-60:]}", flush=True)
        time.sleep(wait)
    raise RuntimeError("unreachable")


def _ecdc_meta(block: str, label: str) -> str:
    m = re.search(rf'>{label}\s*:?\s*</span>(.*?)</div>', block, re.S)
    return _txt(m.group(1)) if m else ""


def _ecdc_deadline(block: str) -> datetime | None:
    m = re.search(r'>Deadline[^<]*</span>.*?datetime="([^"]+)"', block, re.S)
    if not m:
        return None
    try:
        return datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
    except ValueError:
        return None


def _ecdc_cards(html: str) -> list[dict]:
    """One dict per <article class="ct-procurement"> card on a listing page."""
    rows = []
    for body in re.findall(
            r'<article[^>]*class="[^"]*ct-procurement[^"]*"[^>]*>(.*?)</article>', html, re.S):
        am = re.search(r'<a[^>]+href="([^"]+)"[^>]*hreflang="en"[^>]*>(.*?)</a>', body, re.S)
        if not am or not _txt(am.group(2)):
            continue
        href = _html.unescape(am.group(1))
        rows.append({
            "title": _txt(am.group(2)),
            "url": href if href.startswith("http") else _ECDC + href,
            "reference": _ecdc_meta(body, r"Ref\."),
            "kind": _ecdc_meta(body, "Media type"),
            "deadline": _ecdc_deadline(body),
        })
    return rows


def _iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _ecdc_detail(url: str) -> dict:
    """Read one procedure page: publication date (metadata), description, links.

    The procedure's own content runs from its <h1> to the end of its <article>;
    "Page last updated" appears on some older pages only, so it cannot bound it."""
    page = _ecdc_get(url.split("#")[0])
    pub = re.search(r'property="article:published_time"\s+content="([^"]+)"', page)
    upd = re.search(r'Page last updated.*?datetime="([^"]+)"', page, re.S)
    m = re.search(r"<h1.*?</h1>(.*?)(?:Page last updated|</article>)", page, re.S)
    region = m.group(1) if m else ""
    # Description: the paragraphs after the meta list (the meta items are <div>s).
    after_meta = region.split("</ul>", 1)[-1]
    paras = [p for p in (_txt(x) for x in re.findall(r"<p[^>]*>(.*?)</p>", after_meta, re.S)) if p]
    links = sorted(set(u for u in re.findall(r'href="(https?://[^"]+)"', after_meta)
                       if "ecdc.europa.eu" not in u))
    return {"description": paras, "links": links,
            "published": _iso(pub.group(1) if pub else None),
            "updated": _iso(upd.group(1) if upd else None)}


def _ecdc_item(row: dict, detail: dict | None, now: datetime) -> Item:
    deadline = row["deadline"]
    status = "open" if deadline is not None and deadline >= now else "closed"
    item = Item(
        body_code="ecdc", item_type="tender", title=clean(row["title"])[:120],
        public_url=row["url"],
        summary=clean(" · ".join(b for b in [row["reference"], row["kind"],
                                               deadline.date().isoformat() if deadline else ""] if b)),
        creation_date=now, source_kind="ecdc_procurement",
        guid=row["reference"] or row["url"],
        extras={"tender_reference": row["reference"] or None, "status": status,
                "deadline": deadline},
    )
    if detail is None:
        # Not re-read this run: no date and no body, so the stored values stand.
        return item
    facts = [("Reference", row["reference"]), ("Procurement type", row["kind"]),
             ("Published", detail["published"].date().isoformat() if detail["published"] else ""),
             ("Deadline", deadline.strftime("%Y-%m-%d %H:%M UTC") if deadline else ""),
             ("Page last updated", detail["updated"].date().isoformat() if detail["updated"] else "")]
    facts = [(k, v) for k, v in facts if v]
    desc, links = detail["description"], detail["links"]
    item.body_txt = clean("\n".join([row["title"], *desc, *(f"{k}: {v}" for k, v in facts), *links]))
    item.body_html = clean(
        f"<h1>{_html.escape(row['title'])}</h1>"
        + "".join(f"<p>{_html.escape(p)}</p>" for p in desc)
        + "<dl>" + "".join(f"<dt>{_html.escape(k)}</dt><dd>{_html.escape(v)}</dd>" for k, v in facts)
        + "</dl>"
        + ("<ul>" + "".join(f'<li><a href="{_html.escape(u)}">{_html.escape(u)}</a></li>' for u in links)
           + "</ul>" if links else ""))
    # A notice cannot be published after its own deadline. 27 ECDC pages carry
    # article:published_time 2017-07-27, the day ECDC's site was migrated, on
    # procedures that closed in 2016-2017 (dry run 30 Sep 2026). Such a date is the
    # page's re-creation, not the notice's publication: try the fallback, else NULL.
    def _plausible(d: datetime | None) -> datetime | None:
        return d if d is not None and (deadline is None or d <= deadline) else None
    item.document_date = _plausible(detail["published"]) or _plausible(detail["updated"])
    return item


def ingest_ecdc_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    """Every listing page (stop at the first empty one), plus detail pages for the
    first pages and every procedure whose deadline is still ahead. The whole archive
    is read once with ECDC_FULL_DETAILS=1."""
    import os
    import time
    full = os.environ.get("ECDC_FULL_DETAILS") == "1"
    key = (fetch_bodies, full)
    hit = _ECDC_CACHE.get(key)
    if hit and time.time() - hit[0] < _ECDC_CACHE_TTL:
        return hit[1]
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    seen: set = set()
    for page in range(_ECDC_MAX_PAGES):
        url = _ECDC_LISTING + (f"?page={page}" if page else "")
        rows = _ecdc_cards(_ecdc_get(url))
        if not rows:
            break
        for row in rows:
            ident = row["reference"] or row["url"]
            if ident in seen:
                continue
            seen.add(ident)
            want = fetch_bodies and (full or page < _ECDC_FRESH_PAGES
                                     or (row["deadline"] is not None and row["deadline"] >= now))
            detail = None
            if want:
                try:
                    detail = _ecdc_detail(row["url"])
                except requests.RequestException as exc:
                    print(f"    [WARN] ecdc detail {row['reference']}: {exc}", flush=True)
            items.append(_ecdc_item(row, detail, now))
    if not items:
        raise RuntimeError("ECDC procurement listing parsed to zero rows")
    _ECDC_CACHE[key] = (time.time(), items)
    return items


# --- ECHA — current and closed calls, each procedure's own page ------------ #
# API audit, 30 Sep 2026 ("Walk · ECHA"): the reader took the current page only (4 of
# 113 procedures), pointed every row at the listing page (#reference), wrote "Open" on
# every body, stored the deadline as document_date, dropped rows without a reference
# and launched the browser twice. ECHA publishes no publication date. Victor's
# decisions, 30 Sep: read the closed-calls page too; status open only for the current
# page with the deadline ahead, closed otherwise; document_date = the publication date
# of the linked Funding & Tenders notice (SEDIA startDate), else NULL; calls for
# interest are eoi_call, everything else tender, with the procedure type in the body.
# ECHA answers plain HTTP with 403 everywhere; one browser session serves the run.
_ECHA = "https://echa.europa.eu"
_ECHA_PROCUREMENT_URL = _ECHA + "/about-us/business-opportunities"
_ECHA_CLOSED_URL = _ECHA_PROCUREMENT_URL + "/closed-calls"
_ECHA_CACHE: dict = {}
_ECHA_CACHE_TTL = 1800
_FT_NOTICE = re.compile(
    r"funding-tenders/opportunities/portal/screen/opportunities/tender-details/"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}-(?:CN|PIN|CAN))")


def _echa_rows(html: str, *, current: bool) -> list[dict]:
    """Rows of the business-opportunities table: title+link, (reference), Type, Deadline."""
    m = re.search(r"<table.*?</table>", html, re.S)
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(0) if m else "", re.S):
        am = re.search(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', tr, re.S)
        if not am:
            continue
        cells = [_txt(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        first = cells[0] if cells else ""
        rm = re.search(r"\(([^()]+)\)\s*$", first)
        dm = _DATE.search(cells[2]) if len(cells) > 2 else None
        href = _html.unescape(am.group(1))
        rows.append({
            "title": _txt(am.group(2)),
            "url": href if href.startswith("http") else _ECHA + href,
            "reference": rm.group(1).strip() if rm else "",
            "kind": cells[1] if len(cells) > 1 else "",
            "deadline": _parse_date(dm.group(1)) if dm else None,
            "current": current,
        })
    return rows


def _echa_detail(html: str) -> dict:
    m = re.search(r'<div class="single-procurement">(.*?)(?:<form |<footer)', html, re.S)
    block = m.group(1) if m else ""
    paras = [p for p in (_txt(x) for x in re.findall(r"<p[^>]*>(.*?)</p>", block, re.S)) if p]
    links = sorted(set(u for u in (_html.unescape(x) for x in re.findall(r'href="(https?://[^"]+)"', block))
                       if "echa.europa.eu" not in u))
    notices = list(dict.fromkeys(_FT_NOTICE.findall(block)))
    return {"description": paras, "links": links, "notices": notices,
            "documents": _echa_documents(block)}


_GENERIC_LINK_TEXT = {"here", "click here", "link", "this link", "download", "pdf", "[pdf]"}


def _echa_documents(block: str) -> list[dict]:
    """Files linked from a procedure's text (Liferay document library):
      /documents/10162/<folder>/<file name>/<uuid>?t=<cache-buster>
      /documents/d/guest/<name>                       (no extension: the bytes decide)
    The link text is the title. ECHA shows no date next to a file, so none is stored.
    The ?t= cache-buster is dropped: the same file must keep one address."""
    docs, seen = [], set()
    for href, inner in re.findall(r'<a\b[^>]*href="([^"]*?/documents/[^"]+)"[^>]*>(.*?)</a>', block, re.S):
        url = _html.unescape(href).split("?", 1)[0].split("#", 1)[0]
        if url.startswith("/"):
            url = _ECHA + url
        if not url.startswith(_ECHA + "/documents/") or url in seen:
            continue
        seen.add(url)
        parts = [p for p in url.split("/") if p]
        # /documents/10162/<folder>/<name>/<uuid>: the name is the segment before the uuid
        name = unquote(parts[-2] if re.fullmatch(r"[0-9a-f-]{36}", parts[-1]) else parts[-1])
        fm = re.search(r"\.([A-Za-z0-9]{2,5})$", name)
        title = _txt(inner)
        if title.lower().strip(" .:") in _GENERIC_LINK_TEXT:
            title = name                      # "click here" says nothing about the file
        docs.append({"title": title or name, "file_url": url, "file_name": name,
                     "file_format": fm.group(1).lower() if fm else None,
                     "file_size": None, "language": None, "document_date": None})
    return docs


_SEDIA_SEARCH = "https://api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey=SEDIA&text={text}&pageNumber=1&pageSize=5"


def _ft_notice_date(identifier: str) -> datetime | None:
    """Publication date (SEDIA startDate) of one Funding & Tenders notice, by its exact id."""
    from urllib.parse import quote as _q
    try:
        r = requests.post(_SEDIA_SEARCH.format(text=_q(f'"{identifier}"')),
                          files={"languages": (None, '["en"]', "application/json")},
                          headers=_HEADERS, timeout=40)
        r.raise_for_status()
        results = r.json().get("results") or []
    except (requests.RequestException, ValueError) as exc:
        print(f"    [WARN] F&T notice {identifier}: {exc}", flush=True)
        return None
    for res in results:
        md = res.get("metadata") or {}
        if (md.get("identifier") or [None])[0] == identifier:
            start = (md.get("startDate") or [None])[0]
            return _parse_iso_sedia(start)
    return None


def _parse_iso_sedia(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _echa_item(row: dict, detail: dict | None, now: datetime) -> Item:
    deadline = row["deadline"]
    status = "open" if row["current"] and (deadline is None or deadline >= now) else "closed"
    ref = row["reference"]
    is_call = "interest" in row["kind"].lower() or "/CEI/" in ref.upper()
    # A market consultation prepares a procedure and is published under THAT procedure's
    # reference (7 pairs in ECHA's archive, 30 Sep 2026). The reference identifies the
    # procedure, so only the procedure carries it; the consultation names it in its body.
    # Victor, 30 Sep: identity by procedure page, the unique reference rule stays.
    consultation = _echa_is_consultation(row)
    item = Item(
        body_code="echa", item_type="eoi_call" if is_call else "tender",
        title=clean(row["title"])[:120], public_url=row["url"],
        summary=clean(" · ".join(b for b in [ref, row["kind"],
                                               deadline.date().isoformat() if deadline else ""] if b)),
        creation_date=now, source_kind="echa_procurement",
        guid=row["url"] if consultation else (ref or row["url"]),
        extras={"tender_reference": None if consultation else (ref or None),
                "status": status, "deadline": deadline},
    )
    if detail is None:
        return item
    notice = next((n for n in detail["notices"] if n.endswith("-CN")), None) or \
        next(iter(detail["notices"]), None)
    published = _ft_notice_date(notice) if notice else None
    facts = [("Prepares procedure" if consultation else "Reference", ref),
             ("Procedure type", row["kind"]),
             ("Status on ECHA's site", "current call" if row["current"] else "closed call"),
             ("Funding & Tenders notice", notice or ""),
             ("Notice published", published.date().isoformat() if published else ""),
             ("Deadline", deadline.date().isoformat() if deadline else "")]
    facts = [(k, v) for k, v in facts if v]
    desc, links = detail["description"], detail["links"]
    docs = detail.get("documents") or []
    item.body_txt = clean("\n".join([row["title"], *desc, *(f"{k}: {v}" for k, v in facts), *links,
                                     *_documents_txt(docs)]))
    item.body_html = clean(
        f"<h1>{_html.escape(row['title'])}</h1>"
        + "".join(f"<p>{_html.escape(p)}</p>" for p in desc)
        + "<dl>" + "".join(f"<dt>{_html.escape(k)}</dt><dd>{_html.escape(v)}</dd>" for k, v in facts)
        + "</dl>"
        + ("<ul>" + "".join(f'<li><a href="{_html.escape(u)}">{_html.escape(u)}</a></li>' for u in links)
           + "</ul>" if links else "")
        + _documents_html(docs))
    # A notice cannot be published after its own deadline (see the ECDC note).
    item.document_date = published if published and (deadline is None or published <= deadline) else None
    return item


def _echa_is_consultation(row: dict) -> bool:
    return "consultation" in row["kind"].lower()


def _echa_same_procedure_key(row: dict):
    """ECHA sometimes lists ONE procedure on two pages (same reference, title and
    deadline; ECHA/2021/46 and ECHA/2018/398 on 30 Sep 2026)."""
    if not row["reference"] or _echa_is_consultation(row):
        return None
    return (row["reference"], re.sub(r"\W+", " ", row["title"].lower()).strip(), row["deadline"])


def _echa_merge_double_listings(items: list[Item], rows: list[dict]) -> list[Item]:
    """Keep one row per procedure listed twice: the page with the longer text; the
    other page's address goes in its body."""
    groups: dict = {}
    for it, row in zip(items, rows):
        k = _echa_same_procedure_key(row)
        if k:
            groups.setdefault(k, []).append(it)
    drop: set = set()
    for members in groups.values():
        if len(members) < 2:
            continue
        keep = max(members, key=lambda it: (len(it.body_txt or ""), it.public_url))
        others = [m.public_url for m in members if m is not keep]
        drop.update(others)
        if keep.body_txt:
            keep.body_txt = clean(keep.body_txt + "\n" + "\n".join(f"Also listed at: {u}" for u in others))
            keep.body_html = clean((keep.body_html or "") + "<ul>" + "".join(
                f'<li>Also listed at: <a href="{_html.escape(u)}">{_html.escape(u)}</a></li>' for u in others)
                + "</ul>")
    return [it for it in items if it.public_url not in drop]


def _echa_all(*, fetch_bodies: bool = True) -> list[Item]:
    """Current and closed calls in ONE browser session; detail pages for every current
    call each run, and for the closed archive once, with ECHA_FULL_DETAILS=1."""
    import os
    import time
    from services.scrapers.waf_browser_fetcher import WafBrowserFetcher
    full = os.environ.get("ECHA_FULL_DETAILS") == "1"
    key = (fetch_bodies, full)
    hit = _ECHA_CACHE.get(key)
    if hit and time.time() - hit[0] < _ECHA_CACHE_TTL:
        return hit[1]
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    seen: set = set()
    with WafBrowserFetcher() as f:
        rows = (_echa_rows(f.fetch(_ECHA_PROCUREMENT_URL, strip_chrome=False).html, current=True)
                + _echa_rows(f.fetch(_ECHA_CLOSED_URL, strip_chrome=False).html, current=False))
        if not rows:
            raise RuntimeError("ECHA business-opportunities pages parsed to zero rows")
        unique_rows = []
        for r in rows:                  # a call moving to the closed page mid-run
            if r["url"] not in seen:
                seen.add(r["url"])
                unique_rows.append(r)
        rows = unique_rows
        proc_keys = [_echa_same_procedure_key(r) for r in rows]
        doubled = {k for k in proc_keys if k and proc_keys.count(k) > 1}
        for row, proc_key in zip(rows, proc_keys):
            detail = None
            # Pages of a procedure listed twice are read every run, so the choice of
            # which page to keep (the longer text) is the same every day.
            if fetch_bodies and (row["current"] or full or proc_key in doubled):
                try:
                    detail = _echa_detail(f.fetch(row["url"], strip_chrome=False).html)
                except Exception as exc:  # noqa: BLE001 - one page must not stop the run
                    print(f"    [WARN] echa detail {row['url'][-60:]}: {type(exc).__name__}", flush=True)
            items.append(_echa_item(row, detail, now))
    items = _echa_merge_double_listings(items, rows)
    _ECHA_CACHE[key] = (time.time(), items)
    return items


def ingest_echa_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return [i for i in _echa_all(fetch_bodies=fetch_bodies) if i.item_type == "tender"]


def ingest_echa_calls(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return [i for i in _echa_all(fetch_bodies=fetch_bodies) if i.item_type == "eoi_call"]


# --- EIGE — defensive empty-listing handler ------------------------------- #
_EIGE = "https://eige.europa.eu"


def ingest_eige_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    """EIGE shows 'There are currently no ongoing procedures' when empty.
    When EIGE publishes calls they appear as a Drupal Views table on this
    page; parse_views_table returns [] cleanly when no <tbody> is present."""
    html = _fetch(_EIGE + "/about/procurement")
    return parse_views_table(
        html, _EIGE, body_code="eige", item_type="tender",
        source_kind="eige_procurement",
        ref_field="reference", deadline_field="deadline", status="Open",
    )


# --- FRA — Playwright (Anubis WAF) + defensive empty handling ------------- #
_FRA = "https://fra.europa.eu"


def _fetch_fra_playwright(path: str) -> str:
    from services.scrapers.waf_browser_fetcher import WafBrowserFetcher
    with WafBrowserFetcher() as f:
        return f.fetch(_FRA + path, strip_chrome=False).html


def ingest_fra_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    """FRA is behind Anubis bot-challenge; Playwright clears it. The Ongoing
    Procedures page returns 'There are no open procedures at the present
    time.' when empty; we return []. When listings are present, parse via
    parse_views_table with FRA's Drupal field names."""
    html = _fetch_fra_playwright("/en/about-fra/procurement/ongoing-procedures")
    if "no open procedures" in html.lower():
        return []
    return parse_views_table(
        html, _FRA, body_code="fra", item_type="tender",
        source_kind="fra_procurement",
        ref_field="reference", deadline_field="closing-date", status="Open",
    )


# --- EEA — F&T-only for open calls; stub returning [] --------------------- #
_EEA = "https://www.eea.europa.eu"


# EEA. API audit, 30 Sep 2026 ("Walk · EEA"): this was a stub returning [], so
# /eea-tenders had never held a row, while the Funding & Tenders portal holds 212 EEA
# notices (2015-2026) under EEA's buyer id, the id EEA's own procurement page links.
# Victor's decisions, 30 Sep: read EEA's notices from SEDIA by that buyer id, in the
# shared procurement shape; add EEA's own calls for interest (published on its Plone
# site, whose pages have a JSON form at /++api++/), the kind in the body.
_EEA_FT_BUYER_ID = "47352390"
_EEA_CALLS = ("remunerated-scientific-experts", "topic-centres-call-for-interest")
_SEDIA_STATUS = {"forthcoming": "forthcoming", "open": "open", "closed": "closed"}


def _sedia_helpers():
    """The Funding & Tenders reader lives in scripts/ingest_funding_sedia.py; reuse its
    request and normaliser rather than a second copy of either."""
    try:
        from scripts import ingest_funding_sedia as sedia
    except ImportError:  # run from backend/scripts (sync_economy's own directory)
        import ingest_funding_sedia as sedia
    return sedia


_FT_KIND_BY_SUFFIX = {"CN": "call for tender", "EXA": "ex-ante publicity",
                      "PIN": "prior information notice", "CAN": "contract award notice"}


def _ft_buyer_results(body_code: str, buyer_id: str) -> list[dict]:
    """Every raw SEDIA result of one EU buyer (cftPartyLegalEntityId), all pages."""
    sedia = _sedia_helpers()
    query = {"bool": {"must": [{"terms": {"type": ["0"]}},
                               {"terms": {"cftPartyLegalEntityId": [buyer_id]}}]}}
    results, page = [], 1
    while True:
        # A TOTAL order, or paging repeats some notices and skips others: unsorted,
        # SEDIA returned 212 results holding 210 distinct notices (30 Sep 2026).
        batch = sedia.fetch_sedia_page(page, page_size=100, query=query,
                                       sort={"field": "identifier", "order": "ASC"}).get("results") or []
        results += batch
        if len(batch) < 100:
            break
        page += 1
    if not results:
        raise RuntimeError(f"SEDIA returned no {body_code} notices for buyer id {buyer_id}")
    return results


# Each document has its own address on the portal (the Documents tab links it; plain
# HTTP, 30 Sep 2026). Notices migrated from the old eTendering site keep their files
# under docs/etender/{cftId}/ (file names "{cftId}_{docId}_..."); newer ones under
# docs/{notice id}/. The "download all" archive exists for new notices only (404 on
# etender ones), so files are read one by one.
_FT_DOCS = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/tender-details/docs"


# New notices label a file "EN", etender ones "ENG": one language, one spelling (ISO 639-1).
_LANG3 = {"bul": "bg", "ces": "cs", "cze": "cs", "dan": "da", "deu": "de", "ger": "de", "ell": "el",
          "gre": "el", "eng": "en", "spa": "es", "est": "et", "fin": "fi", "fra": "fr", "fre": "fr",
          "gle": "ga", "hrv": "hr", "hun": "hu", "ita": "it", "lit": "lt", "lav": "lv", "mlt": "mt",
          "nld": "nl", "dut": "nl", "pol": "pl", "por": "pt", "ron": "ro", "rum": "ro", "slk": "sk",
          "slo": "sk", "slv": "sl", "swe": "sv"}


def _lang2(code: str) -> str:
    return _LANG3.get(code, code)


def _ft_notice_documents(result: dict) -> list[dict]:
    """The notice's documents from SEDIA's cftDocuments: title, type, language and
    publication date of each current, non-obsolete file (the ZIP holds the files)."""
    md = result.get("metadata") or {}
    ident = (md.get("identifier") or [None])[0]
    raw = (md.get("cftDocuments") or [None])[0]
    if not ident or not raw:
        return []
    try:
        entries = json.loads(raw).get("cftDocuments") or []
    except (ValueError, AttributeError):
        return []
    cft_id = (md.get("cftId") or [None])[0]
    docs, seen = [], set()
    for e in sorted(entries, key=lambda e: e.get("sortKey") or ""):
        if e.get("obsolete"):
            continue
        refs = e.get("hermesDocumentReferences") or []
        ref = next((r for r in refs if r.get("isCurrentVersion") == "Y"), refs[-1] if refs else None)
        name = (ref or {}).get("documentFileName")
        if not name or name in seen:
            continue
        seen.add(name)
        fm = re.search(r"\.([A-Za-z0-9]{2,5})$", name)
        pub = _parse_iso_sedia((ref or {}).get("publicationDate"))
        folder = (f"etender/{cft_id}" if cft_id and name.startswith(f"{cft_id}_")
                  else quote(ident, safe=""))
        docs.append({"title": clean(e.get("documentTitle") or e.get("documentType") or name),
                     "document_type": e.get("documentType"),
                     "file_url": f"{_FT_DOCS}/{folder}/{quote(name, safe='')}", "file_name": name,
                     "file_format": fm.group(1).lower() if fm else None, "file_size": None,
                     "language": _lang2((e.get("languageCode") or "").lower()) or None,
                     "document_date": pub.date() if pub else None})
    return docs


def _ft_buyer_notices(*, body_code: str, buyer_id: str, source_kind: str, now: datetime) -> list[Item]:
    """Every Funding & Tenders notice of one EU buyer (SEDIA cftPartyLegalEntityId), in the
    shared procurement shape. One reader for every agency that publishes on the portal
    (Victor, 30 Sep 2026: EEA and EFSA first)."""
    sedia = _sedia_helpers()
    results = _ft_buyer_results(body_code, buyer_id)
    items, seen = [], set()
    for res in results:
        row = sedia.normalise_row(res)
        if not row or not row.get("topic_id") or row["topic_id"] in seen:
            continue
        seen.add(row["topic_id"])
        deadline = _iso(str(row["deadline"])) if row.get("deadline") else None
        published = _iso(str(row["published_at"])) if row.get("published_at") else None
        status = _SEDIA_STATUS.get((row.get("status") or "").lower(), "closed")
        if status == "open" and deadline is not None and deadline < now:
            status = "closed"
        kind = _FT_KIND_BY_SUFFIX.get(row["topic_id"].rsplit("-", 1)[-1], "call for tender")
        facts = [("Notice", row["topic_id"]), ("Procedure type", kind),
                 ("Contract type", row.get("contract_type") or ""),
                 ("Published", published.date().isoformat() if published else ""),
                 ("Deadline", deadline.strftime("%Y-%m-%d %H:%M UTC") if deadline else ""),
                 ("Status on the portal", status)]
        facts = [(k, v) for k, v in facts if v]
        desc = [p for p in re.split(r"\n{2,}", row.get("description") or "") if p.strip()]
        url = row.get("source_url") or ""
        docs = _ft_notice_documents(res)
        items.append(Item(
            body_code=body_code, item_type="tender", title=clean(row["title"])[:120], public_url=url,
            summary=clean(" · ".join(b for b in [row["topic_id"], kind,
                                                   deadline.date().isoformat() if deadline else ""] if b)),
            body_txt=clean("\n".join([row["title"], *desc, *(f"{k}: {v}" for k, v in facts), url,
                                      *_documents_txt(docs)])),
            body_html=clean(f"<h1>{_html.escape(row['title'])}</h1>"
                            + "".join(f"<p>{_html.escape(p)}</p>" for p in desc)
                            + "<dl>" + "".join(f"<dt>{_html.escape(k)}</dt><dd>{_html.escape(v)}</dd>"
                                               for k, v in facts) + "</dl>"
                            + f'<p><a href="{_html.escape(url)}">{_html.escape(url)}</a></p>'
                            + _documents_html(docs)),
            document_date=published if published and (deadline is None or published <= deadline) else None,
            creation_date=now, source_kind=source_kind, guid=row["topic_id"],
            extras={"tender_reference": row["topic_id"], "status": status, "deadline": deadline},
        ))
    # A prior information notice announces a call; once the call's contract notice (same
    # id root, -CN) exists, the PIN is superseded and reads closed, whatever SEDIA's own
    # label (Victor, 30 Sep 2026; 37 EFSA procedures have both).
    roots_with_cn = {it.extras["tender_reference"][:-3] for it in items
                     if it.extras["tender_reference"].endswith("-CN")}
    for it in items:
        ref = it.extras["tender_reference"]
        if ref.endswith("-PIN") and ref[:-4] in roots_with_cn:
            it.extras["status"] = "closed"
    return items


def _eea_own_calls(now: datetime) -> list[Item]:
    """EEA's own calls for interest, read from its Plone JSON API."""
    items = []
    for sub in _EEA_CALLS:
        page = f"{_EEA}/en/about/procurement-and-grants/{sub}"
        r = requests.get(f"{_EEA}/++api++/en/about/procurement-and-grants/{sub}",
                         headers={**_HEADERS, "Accept": "application/json"}, timeout=40)
        r.raise_for_status()
        d = r.json()
        import json as _json
        text = _html.unescape(re.sub(r"\s+", " ", " ".join(
            re.findall(r'"text": "([^"]{3,})"', _json.dumps(d.get("blocks", {}), ensure_ascii=False)))))
        text = text.replace("\u00a0", " ").replace("\xa0", " ")
        dm = re.search(r"Deadline for [^:]{0,80}?:?\s*(\d{1,2}\s+[A-Z][a-z]+\s+\d{4})", text)
        deadline = _parse_date(dm.group(1)) if dm else None
        published = _iso(d.get("effective"))
        status = "open" if deadline is not None and deadline >= now else "closed"
        title = clean(d.get("title") or sub)
        desc = [x for x in [d.get("description") or "", text[:4000]] if x]
        facts = [("Procedure type", "call for expression of interest"),
                 ("Published", published.date().isoformat() if published else ""),
                 ("Deadline", deadline.date().isoformat() if deadline else "")]
        facts = [(k, v) for k, v in facts if v]
        items.append(Item(
            body_code="eea", item_type="tender", title=title[:120], public_url=page,
            summary=clean(" · ".join(b for b in ["call for expression of interest",
                                                   deadline.date().isoformat() if deadline else ""] if b)),
            body_txt=clean("\n".join([title, *desc, *(f"{k}: {v}" for k, v in facts)])),
            body_html=clean(f"<h1>{_html.escape(title)}</h1>"
                            + "".join(f"<p>{_html.escape(p)}</p>" for p in desc)
                            + "<dl>" + "".join(f"<dt>{_html.escape(k)}</dt><dd>{_html.escape(v)}</dd>"
                                               for k, v in facts) + "</dl>"),
            document_date=published, creation_date=now, source_kind="eea_interest_call",
            guid=page, extras={"tender_reference": None, "status": status, "deadline": deadline},
        ))
    return items


def ingest_eea_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    now = datetime.now(timezone.utc)
    return (_ft_buyer_notices(body_code="eea", buyer_id=_EEA_FT_BUYER_ID,
                              source_kind="eea_ft_notice", now=now)
            + _eea_own_calls(now))


# --- EU-OSHA — Drupal Views views-row + per-year archive ------------------ #
_EU_OSHA = "https://osha.europa.eu"


def _parse_eu_osha_views(html: str, base: str, body_code: str, item_type: str,
                        source_kind: str) -> list[Item]:
    """EU-OSHA procurement listing (revamp-row grid, JS-rendered). Each entry has
    an optional publication-date <time datetime> then views-field-title > h2 > a
    linking to a /procurement/call-tender/<slug> (or /call-expression-.../) detail
    page. Match the detail links directly (robust to the grid wrapper) and pair
    each with the nearest preceding <time> as its document date."""
    now = datetime.now(timezone.utc)
    out: list[Item] = []
    seen: set[str] = set()
    pat = re.compile(
        r'views-field-title[^>]*>\s*<h2[^>]*>\s*<a[^>]+href="'
        r'(/en/about-eu-osha/procurement/call[^"]+)"[^>]*>(.*?)</a>', re.S)
    for m in pat.finditer(html):
        href, title = m.group(1), _txt(m.group(2))
        if not title or href in seen:
            continue
        seen.add(href)
        pre = html[max(0, m.start() - 500):m.start()]
        times = re.findall(r'<time[^>]*datetime="([^"]+)"', pre)
        doc_dt = _parse_date(times[-1][:10]) if times else None
        out.append(_build(
            body_code=body_code, item_type=item_type, title=title, url=base + href,
            reference="", status="Open", deadline=doc_dt, now=now,
            source_kind=source_kind,
        ))
    return out


def ingest_eu_osha_tenders(*, fetch_bodies: bool = True, max_pages: int = 4, **_) -> list[Item]:
    """EU-OSHA procurement. The site's WAF fingerprints TLS and drops raw HTTP
    clients (requests/urllib -> RemoteDisconnected), while a real browser and
    curl pass, so fetch via the headless-browser WafBrowserFetcher (same tool
    used for FRA). Two current listings: open calls for tender and calls for
    expression of interest. (The old /calls_archive/<year> tree is gone.)"""
    from services.scrapers.waf_browser_fetcher import WafBrowserFetcher
    items: list[Item] = []
    seen: set[str] = set()
    pages = [
        "/en/about-eu-osha/procurement/calls-tender",
        "/en/about-eu-osha/procurement/calls-expression-interest",
    ]
    with WafBrowserFetcher() as f:
        for path in pages:
            res = f.fetch(_EU_OSHA + path, strip_chrome=False)
            if getattr(res, "error", None) or not getattr(res, "html", None):
                continue
            for it in _parse_eu_osha_views(res.html, _EU_OSHA,
                                           body_code="eu_osha", item_type="tender",
                                           source_kind="eu_osha_procurement"):
                if it.guid in seen:
                    continue
                seen.add(it.guid)
                items.append(it)
    return items


def ingest_eu_osha_calls(*, fetch_bodies: bool = True, **_) -> list[Item]:
    """Calls for expression of interest at /calls-expression-interest; layout
    matches _parse_eu_osha_views. EU-OSHA's WAF drops raw HTTP (_fetch ->
    RemoteDisconnected), so render via WafBrowserFetcher like ingest_eu_osha_tenders.
    Returns [] cleanly when there are no open EOI calls."""
    from services.scrapers.waf_browser_fetcher import WafBrowserFetcher
    with WafBrowserFetcher() as f:
        res = f.fetch(_EU_OSHA + "/en/about-eu-osha/procurement/calls-expression-interest",
                      strip_chrome=False)
    return _parse_eu_osha_views(
        getattr(res, "html", "") or "", _EU_OSHA,
        body_code="eu_osha", item_type="eoi_call",
        source_kind="eu_osha_procurement",
    )


# --- Eurofound — Playwright sub-page crawl -------------------------------- #
_EUROFOUND = "https://www.eurofound.europa.eu"


def _fetch_eurofound_playwright(path: str) -> str:
    from services.scrapers.waf_browser_fetcher import WafBrowserFetcher
    with WafBrowserFetcher() as f:
        return f.fetch(_EUROFOUND + path, strip_chrome=False).html


def ingest_eurofound_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    """Eurofound rate-limits raw HTTP (429); Playwright gets through. The
    parser mirrors the EU-OSHA views-row pattern; if Eurofound's per-tab
    listing markup diverges, this returns [] cleanly and a follow-up pass
    can refine the regex once row examples are captured."""
    # Eurofound consolidated its procurement onto a single /en/about/procurement
    # page (Aug 2026); the old /calls-tenders-140k + /calls-tenders-below-140k
    # sub-pages 404. Returns [] cleanly when the page shows no open procedures.
    items: list[Item] = []
    try:
        html = _fetch_eurofound_playwright("/en/about/procurement")
    except Exception:
        return []
    items += _parse_eu_osha_views(
        html, _EUROFOUND, body_code="eurofound", item_type="tender",
        source_kind="eurofound_procurement",
    )
    return items


def ingest_eurofound_calls(*, fetch_bodies: bool = True, **_) -> list[Item]:
    # Same consolidated /en/about/procurement page as tenders (old
    # /calls-expression-interest sub-page 404s).
    try:
        html = _fetch_eurofound_playwright("/en/about/procurement")
    except Exception:
        return []
    return _parse_eu_osha_views(
        html, _EUROFOUND, body_code="eurofound", item_type="eoi_call",
        source_kind="eurofound_procurement",
    )


# --- EIB — procurement via TED API v3 ------------------------------------ #
# EIB does not publish its corporate procurement on its own site; everything
# goes through TED. Brubru's TED scraper currently ingests only member-state
# notices, so this scraper hits TED's public POST API directly and pulls EIB
# notices into economy_items(body_code='eib', item_type='tender').
_TED_API = "https://api.ted.europa.eu/v3/notices/search"


def _ted_text(field_value):
    """Multilingual TED field → English (or first available) string."""
    if not field_value:
        return ""
    if isinstance(field_value, str):
        return field_value
    if isinstance(field_value, dict):
        for lang in ("eng", "fre", "deu", "spa"):
            v = field_value.get(lang)
            if v:
                return v[0] if isinstance(v, list) else v
        for v in field_value.values():
            if v:
                return v[0] if isinstance(v, list) else v
    if isinstance(field_value, list) and field_value:
        return _ted_text(field_value[0])
    return ""


def _ted_search_eib(limit: int = 200, only_open: bool = True) -> list[dict]:
    """Hit the TED public API v3 for EIB-buyer notices. Open-only by default
    (deadline-receipt-request >= today). Returns the raw JSON notices list."""
    import json as _json
    import urllib.request as _urllib_request
    from urllib.error import HTTPError
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    q_parts = ['buyer-name="European Investment Bank"']
    if only_open:
        q_parts.append(f"deadline-receipt-request>={today}")
    payload = _json.dumps({
        "query": " AND ".join(q_parts),
        "fields": [
            "publication-number", "buyer-name", "notice-title",
            "publication-date", "deadline-receipt-request",
            "procedure-type", "links",
        ],
        "limit": limit,
        "page": 1,
    }).encode("utf-8")
    req = _urllib_request.Request(
        _TED_API, data=payload, method="POST",
        headers={"User-Agent": _UA, "Content-Type": "application/json",
                 "Accept": "application/json"},
    )
    try:
        body = _urllib_request.urlopen(req, timeout=30).read()
        return _json.loads(body).get("notices", [])
    except HTTPError as e:
        return []
    except Exception:
        return []


def _ted_search(query: str, limit: int = 200) -> list[dict]:
    """Generic TED API v3 search. Public POST endpoint, no auth."""
    import json as _json
    import urllib.request as _urllib_request
    from urllib.error import HTTPError
    payload = _json.dumps({
        "query": query,
        "fields": [
            "publication-number", "buyer-name", "notice-title",
            "publication-date", "deadline-receipt-request",
            "procedure-type", "links",
        ],
        "limit": limit,
        "page": 1,
    }).encode("utf-8")
    req = _urllib_request.Request(
        _TED_API, data=payload, method="POST",
        headers={"User-Agent": _UA, "Content-Type": "application/json",
                 "Accept": "application/json"},
    )
    try:
        body = _urllib_request.urlopen(req, timeout=30).read()
        return _json.loads(body).get("notices", [])
    except HTTPError:
        return []
    except Exception:
        return []


def _ted_to_item(n: dict, *, body_code: str, item_type: str, source_kind: str) -> Item | None:
    """Common TED notice → Item conversion. Returns None when essential
    fields are missing."""
    now = datetime.now(timezone.utc)
    pub_num = n.get("publication-number") or ""
    title = _ted_text(n.get("notice-title"))
    if not pub_num or not title:
        return None
    procedure = _ted_text(n.get("procedure-type"))
    dl_raw = n.get("deadline-receipt-request")
    dl_str = ""
    if isinstance(dl_raw, str):
        dl_str = dl_raw
    elif isinstance(dl_raw, dict):
        for v in dl_raw.values():
            if v:
                dl_str = v[0] if isinstance(v, list) else v
                break
    elif isinstance(dl_raw, list) and dl_raw:
        dl_str = dl_raw[0]
    deadline = None
    if dl_str:
        try:
            deadline = datetime.fromisoformat(dl_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            deadline = None
    ted_url = f"https://ted.europa.eu/en/notice/-/detail/{pub_num}"
    return _build(
        body_code=body_code, item_type=item_type, title=title, url=ted_url,
        reference=pub_num, status=procedure or "Open",
        deadline=deadline, now=now, source_kind=source_kind,
    )


def ingest_eib_procurement(*, fetch_bodies: bool = True, **_) -> list[Item]:
    """EIB procurement opportunities pulled from TED. body_code='eib',
    item_type='tender'. We try open-only first; if TED returns 0 (rare),
    fall back to a recent-publications window so the feed is not empty."""
    now = datetime.now(timezone.utc)
    out: list[Item] = []
    notices = _ted_search_eib(limit=200, only_open=True)
    if not notices:
        notices = _ted_search_eib(limit=50, only_open=False)
    for n in notices:
        pub_num = n.get("publication-number") or ""
        title = _ted_text(n.get("notice-title"))
        if not pub_num or not title:
            continue
        buyer = _ted_text(n.get("buyer-name")) or "European Investment Bank"
        procedure = _ted_text(n.get("procedure-type"))
        # Deadline can come back as ISO date or epoch-ish string; try ISO first.
        dl_raw = n.get("deadline-receipt-request")
        dl_str = ""
        if isinstance(dl_raw, str):
            dl_str = dl_raw
        elif isinstance(dl_raw, dict):
            for v in dl_raw.values():
                if v: dl_str = v[0] if isinstance(v, list) else v; break
        elif isinstance(dl_raw, list) and dl_raw:
            dl_str = dl_raw[0]
        deadline = None
        if dl_str:
            try:
                deadline = datetime.fromisoformat(dl_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                deadline = None
        pub_str = ""
        pub_raw = n.get("publication-date")
        if isinstance(pub_raw, str):
            pub_str = pub_raw
        # TED's canonical notice URL
        ted_url = f"https://ted.europa.eu/en/notice/-/detail/{pub_num}"
        reference = pub_num
        out.append(_build(
            body_code="eib", item_type="tender", title=title, url=ted_url,
            reference=reference,
            status=procedure or "Open",
            deadline=deadline, now=now, source_kind="eib_procurement",
        ))
    return out


# --- Move 5 (15 Jun 2026): EU-institution framework contracts via TED ----- #
# Pulls open Framework Contract (FWC) notices from TED API v3 for the major
# EU institutions. FWCs are the parent contracts under which specific re-
# openings are later published (TAS's Lot 1 OCA / Lot 5 / Lot 8 lives here).
# Each notice → economy_items(body_code='<inst>', item_type='framework').

_EU_INSTITUTION_BUYERS = (
    ("commission", "European Commission"),
    ("eib", "European Investment Bank"),
    ("eeas", "European External Action Service"),
    ("parliament", "European Parliament"),
    ("council", "Council of the European Union"),
    ("ecb", "European Central Bank"),
)


def ingest_eu_institution_frameworks(*, fetch_bodies: bool = True, **_) -> list[Item]:
    """One pass per institution. The TED API does not expose an
    is-framework-agreement filter we can rely on, so we use the practical
    heuristic 'notice-title contains framework' + open deadline. This
    matches the Commission's Lot N OCA / EISMEA / DG-INTPA FWCs that
    actually carry 'framework' in the published title."""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    out: list[Item] = []
    for body_code, buyer in _EU_INSTITUTION_BUYERS:
        q = (
            f'buyer-name="{buyer}" '
            f'AND notice-title="framework" '
            f'AND deadline-receipt-request>={today}'
        )
        notices = _ted_search(q, limit=200)
        for n in notices:
            item = _ted_to_item(
                n, body_code=body_code, item_type="framework",
                source_kind="eu_inst_framework",
            )
            if item:
                out.append(item)
    return out

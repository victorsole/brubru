"""
Ingest delegated + implementing acts from the Commission Register of
Delegated Acts (RegDel) Excel export.

Source URLs (no auth, no CSRF):
  https://webgate.ec.europa.eu/regdel/web/delegatedActs/excel?lang=en&filter=...
  https://webgate.ec.europa.eu/regdel/web/implementingActs/excel?lang=en&filter=...

Each row carries: Complete title, CCode (e.g. C(2026)876), Celex number,
Policy area, Leading Service Commission (DG), status, phase, planned
adoption date, basic legislative act (parent law title), empowerment
article.

This wipes the 7 fictitious seed rows that were sitting in secondary_acts
and replaces them with real data.

Run:
    python3.12 backend/scripts/ingest_regdel_acts.py            # dry-run, fetch only
    python3.12 backend/scripts/ingest_regdel_acts.py --apply
    python3.12 backend/scripts/ingest_regdel_acts.py --apply --type delegated
    python3.12 backend/scripts/ingest_regdel_acts.py --apply --type implementing
"""

from __future__ import annotations

import argparse
import hashlib
import io
import re
import sys
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# xlrd, not pandas: the export is a legacy .xls and xlrd reads it in ~100 KB, where
# pandas (plus numpy) is ~50 MB in the container for one monthly job. The container had
# neither, so every scheduled run died with ModuleNotFoundError: No module named 'pandas'
# while the script worked on a laptop (28-29 Sep 2026).
import xlrd
import psycopg2

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
USER_AGENT = "Mozilla/5.0 (compatible; BrubruIngest/1.0) Chrome/151.0.0.0"

REGDEL_BASE = "https://webgate.ec.europa.eu/regdel/web"
EXPORT_FILTER = urllib.parse.quote('{"rowsPerPage":6,"firstRowOffset":0,"language":"en"}')


def get_env(k: str) -> str:
    """The value from the process environment, else from the repo-root .env.

    The environment comes FIRST because it is the only one that exists where this runs:
    the Railway container ships no .env, so a .env-only reader returns "" and the job
    dies on its first line. Three sibling jobs were fixed for this on 29 Sep 2026 and
    this one was missed, because its visible failure was a missing `pandas` and the
    DATABASE_URL fault was hidden behind it. Fixing the import revealed the second fault
    on the very next run. tests/test_scheduled_scripts_read_the_environment.py now
    asserts this for every scheduled script, so the class cannot come back one file at a
    time.
    """
    import os
    value = os.environ.get(k)
    if value:
        return value
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


def fetch_excel(act_type: str) -> bytes:
    """Download the Excel export. act_type ∈ {'delegated', 'implementing'}."""
    path = "delegatedActs" if act_type == "delegated" else "implementingActs"
    url = f"{REGDEL_BASE}/{path}/excel?lang=en&filter={EXPORT_FILTER}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


# ---------------------------------------------------------------------------
# The register's own API: what the Excel export leaves out (14 Oct 2026)
# ---------------------------------------------------------------------------
# The export has ten columns and no scrutiny: objection_deadline, ep_scrutiny,
# council_scrutiny and parent_procedure_ref were empty on all 2,162 delegated acts, 43 of
# the 49 adopted acts had no adoption date, and parent_celex came from a regex over the
# basic act's title, which took an act NAMED in that title (Directive 2009/39 for
# Regulation 609/2013) on 47 acts and found nothing on 142. The register's web page reads
# a JSON API that carries the basic act's CELEX, procedure and scrutiny period, and per
# act the adoption, extension, objection and early non-objection events. It is the page's
# own API: a session cookie and the XSRF token the page sets, nothing else.
#
# What it does NOT publish is the day the scrutiny period starts (the notification to
# Parliament and Council). The document register's "date of transmission" is not it:
# tested on 58 published acts, 30 would have been published before their deadline, and
# acts from 2012-2017 carry 2021 dates. So no deadline is computed. What is certain is a
# floor: notification never precedes adoption, so the period cannot end before adoption +
# period + extension. On 150 published acts, 143 of the 146 without an early
# non-objection appeared in the Official Journal on or after that floor; the other 3 the
# day after adoption, the urgency procedure. Served as objection_deadline_earliest.

REGDEL_HOME = "https://webgate.ec.europa.eu/regdel/"


class Register:
    """A session on the RegDel API: the cookie and XSRF token its own page sets."""

    def __init__(self, pace: float = 0.15):
        import http.cookiejar
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        self.opener.addheaders = [("User-Agent", USER_AGENT)]
        self.opener.open(REGDEL_HOME, timeout=60).read()
        self.token = next((c.value for c in jar if "xsrf" in c.name.lower()), None)
        if not self.token:
            raise RuntimeError("the register set no XSRF-TOKEN cookie")
        self.pace = pace

    def _call(self, path: str, body: Optional[dict] = None, timeout: int = 60):
        import json
        headers = {"Accept": "application/json", "X-XSRF-TOKEN": self.token}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode()
        req = urllib.request.Request(f"{REGDEL_BASE}/{path}", data=data, headers=headers,
                                     method="POST" if body is not None else "GET")
        with self.opener.open(req, timeout=timeout) as r:
            return json.loads(r.read())

    def records(self, act_type: str) -> List[dict]:
        path = "delegatedActs" if act_type == "delegated" else "implementingActs"
        # 120 s: these run before the upsert, and a slow register must not cost the rows.
        return self._call(path, {"language": "en"}, timeout=120).get("list") or []

    def events(self, regdel_id: int) -> List[dict]:
        import time
        time.sleep(self.pace)
        return self._call(f"delegatedActs/{int(regdel_id)}/events") or []


_PROCEDURE_RE = re.compile(r"\s*(\d{4})/(\d{4})/([A-Z]{3})\s*")
_PERIOD_RE = re.compile(r"\d{1,2}(?:/\d{1,2})?")


def register_fields(item: dict, act_type: str) -> Dict[str, Any]:
    """The columns one register record fills, None where it says nothing."""
    from datetime import datetime, timezone
    basic = item.get("basicAct") or {}
    parent = str(basic.get("celexNumber") or "").strip().upper()
    proc = _PROCEDURE_RE.fullmatch(str(basic.get("procedureCode") or ""))
    period = str(basic.get("deadlineRaw") or "").strip()
    status = str(item.get("delegatedActStatus") or "")
    updated = item.get("updateDate")
    return {
        "regdel_id": item.get("id"),
        "register_parent_celex": parent if re.fullmatch(r"3\d{4}[A-Z]\d{4}", parent) else None,
        # The register writes 2011/0296/COD; OEIL and every other Brubru field 2011/0296(COD).
        "parent_procedure_ref": f"{proc.group(1)}/{proc.group(2)}({proc.group(3)})" if proc else None,
        "description": (str(item.get("summary") or "").strip() or None),
        # Delegated acts only: an implementing act has no Article 290 scrutiny period.
        "scrutiny_period": period if act_type == "delegated" and _PERIOD_RE.fullmatch(period) else None,
        # Carried to the events phase, the urgency column's one writer: a status alone
        # misses acts whose events say urgent while their status says PUBLISHED.
        "status_urgent": act_type == "delegated" and "URGENCY" in status,
        "regdel_updated_at": datetime.fromtimestamp(updated / 1000, tz=timezone.utc) if updated else None,
    }


def shortest_period(period: Optional[str]) -> Optional[int]:
    """'1/3' -> 1 (one month when the Commission adopts an authority's draft unchanged)."""
    if not period or not _PERIOD_RE.fullmatch(period):
        return None
    return min(int(p) for p in period.split("/"))


def add_months(d, months: int):
    import calendar
    from datetime import date
    y, m = divmod(d.month - 1 + months, 12)
    y, m = d.year + y, m + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def event_day(ms):
    """A register event time is midnight in Brussels: 22:00 or 23:00 UTC the day before."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return datetime.fromtimestamp(ms / 1000, tz=ZoneInfo("Europe/Brussels")).date() if ms else None


SCRUTINY_EVENTS = {
    "DA_EXTENSION": "extension_requested",
    "DA_OBJECTION": "objection",
    "DA_OBJECTION_NOT_APPROVED": "objection_rejected",
    "DA_EARLY_NON_OBJECTION": "early_non_objection",
    "DA_EARLY_NON_OBJECTION_NOT_APPROVED": "early_non_objection_rejected",
}
INSTITUTIONS = {"INSTITUTION_PARLIAMENT": "ep", "INSTITUTION_COUNCIL": "council"}


def scrutiny_from_events(events: List[dict], period: Optional[str], status: str) -> Dict[str, Any]:
    """What one act's register events say: its dates, each institution's scrutiny, and the floor.

    Each institution gets every key, null where nothing happened, so a read act ({...})
    can be told from an unread one ({}). Dates are the latest event of each kind.
    """
    blank = dict.fromkeys(SCRUTINY_EVENTS.values()) | {"extension_months": None}
    scrutiny = {"ep": dict(blank), "council": dict(blank)}
    adoption = publication = None
    urgent = False
    for e in sorted(events, key=lambda e: e.get("eventDate") or 0):
        kind, day = e.get("eventType"), event_day(e.get("eventDate"))
        if not day:
            continue
        if kind in ("DA_ADOPTION", "DA_URGENT_ADOPTION"):
            adoption = day
        if kind in ("DA_PUBLICATION", "DA_URGENT_PUB") and publication is None:
            publication = day
        if kind in ("DA_URGENT_ADOPTION", "DA_URGENT_PUB"):
            urgent = True
        who = INSTITUTIONS.get(e.get("eventInstitution"))
        if who and kind in SCRUTINY_EVENTS:
            scrutiny[who][SCRUTINY_EVENTS[kind]] = day.isoformat()
            if kind == "DA_EXTENSION":
                raw = (e.get("deadline") or {}).get("deadlineRaw")
                try:
                    scrutiny[who]["extension_months"] = int(float(raw)) if raw not in (None, "") else None
                except (TypeError, ValueError):
                    scrutiny[who]["extension_months"] = None
    months = shortest_period(period)
    # An extension of unknown length counts as none: the floor stays a floor.
    extension = max((s["extension_months"] or 0) for s in scrutiny.values())
    closed_early = all(s["early_non_objection"] for s in scrutiny.values())
    earliest = None
    if adoption and months and not closed_early and status not in ("withdrawn", "cancelled"):
        earliest = add_months(adoption, months + extension)
    return {"adoption_date": adoption, "publication_date": publication, "urgent": urgent,
            "ep_scrutiny": scrutiny["ep"], "council_scrutiny": scrutiny["council"],
            "objection_deadline_earliest": earliest}


# Regex helpers for parsing the "Basic legislative act" free-text column
# into a CELEX number.
_BASIC_REGULATION_RE = re.compile(r"Regulation\s*\(EU\)\s*(\d{4})/(\d{1,4})", re.IGNORECASE)
_BASIC_REGULATION_LEGACY_RE = re.compile(r"Regulation\s*\(EU\)(?:\s*No)?\s*(\d{1,4})/(\d{4})", re.IGNORECASE)
_BASIC_DIRECTIVE_RE = re.compile(r"Directive\s*\(EU\)\s*(\d{4})/(\d{1,4})", re.IGNORECASE)
_BASIC_DIRECTIVE_OLD_RE = re.compile(r"Directive\s*(\d{4})/(\d{1,3})/(?:EU|EC|EEC)", re.IGNORECASE)
_BASIC_DECISION_RE = re.compile(r"Decision\s*\(EU\)\s*(\d{4})/(\d{1,4})", re.IGNORECASE)


def derive_parent_celex(basic_text: Any) -> Optional[str]:
    """Extract a CELEX from the free-text 'Basic legislative act' column."""
    if not isinstance(basic_text, str) or not basic_text.strip():
        return None
    m = _BASIC_REGULATION_RE.search(basic_text)
    if m and 2000 <= int(m.group(1)) <= 2099:
        return f"3{m.group(1)}R{int(m.group(2)):04d}"
    m = _BASIC_DIRECTIVE_RE.search(basic_text)
    if m and 2000 <= int(m.group(1)) <= 2099:
        return f"3{m.group(1)}L{int(m.group(2)):04d}"
    m = _BASIC_DIRECTIVE_OLD_RE.search(basic_text)
    if m and 1950 <= int(m.group(1)) <= 2099:
        return f"3{m.group(1)}L{int(m.group(2)):04d}"
    m = _BASIC_DECISION_RE.search(basic_text)
    if m and 2000 <= int(m.group(1)) <= 2099:
        return f"3{m.group(1)}D{int(m.group(2)):04d}"
    m = _BASIC_REGULATION_LEGACY_RE.search(basic_text)
    if m and 1950 <= int(m.group(2)) <= 2099 and "Regulation (EU)" in basic_text:
        # legacy "(EU) No N/YYYY" form
        return f"3{m.group(2)}R{int(m.group(1)):04d}"
    return None


# Every status value the RegDel exports actually use, counted from the live sheets on
# 30 Sep 2026 (delegated: 10 distinct values, implementing: 5). The old map covered six
# keys and everything else fell through a `.get(..., "draft")` default, so 356 acts wore
# a status that was not theirs -- most seriously the 24 delegated acts Parliament or
# Council had OBJECTED to, which were served as 'draft'.
#
# 'Published' -> 'published', corrected 30 Sep 2026 (Victor's call). It had mapped to
# 'adopted', which collapsed the two stages RegDel actually distinguishes:
#
#   Planned -> Adopted -> Published
#
# 'Adopted' means the College has taken the decision; 'Published' means the act is in
# the Official Journal. The gap between them is the window in which the scrutiny clock
# runs and Parliament or Council can still object, and we hold 699 acts sitting in it
# right now (adopted, no CELEX yet, 569 of them with 2026 C-numbers). Mapping both to
# 'adopted' made that word mean nothing and left the enum's 'published' unused since
# migration 038. The correction moves 6,737 rows, so GovClipping is told before it lands.
_STATUS_MAP = {
    "Published": "published",
    "Adoption": "adopted",
    "Adopted": "adopted",
    "Adopted (urgency procedure)": "adopted",
    "Draft": "draft",
    "Empowerment": "draft",
    "Planned": "planned",
    "Objected": "objected",
    "Cancelled": "cancelled",
    "Withdrawn": "withdrawn",
    "On hold": "on_hold",
    "Notified": "notified",
    "Scrutiny finished": "scrutiny_finished",
}

# Statuses seen in an export that this map does not know. Collected rather than
# swallowed: the register can add a value at any time and the old default turned that
# into a silent 'draft'. Reported at the end of the run.
_UNMAPPED_STATUSES: dict[str, int] = {}


def _normalised_title(title: str) -> str:
    """A title stripped of its numbering preamble, for matching one act to itself.

    A planned act reads 'COMMISSION DELEGATED REGULATION (EU) .../... amending X' and the
    same act once published reads 'Commission Delegated Regulation (EU) 2024/3199 of 15
    October 2024 amending X'. Only the tail is stable, so the key is built from that.

    Measured on the live export (30 Sep 2026): 48/48 delegated and 272/274 implementing
    pipeline titles are distinct after this, and 7 collide with an act already held under
    a real C-number -- which is the point, those are skipped.
    """
    t = re.sub(r"\s+", " ", title).strip().lower()
    t = re.sub(r"^commission\s+(delegated|implementing)\s+"
               r"(regulation|decision|directive)\s*", "", t)
    t = re.sub(r"^\(eu\)\s*(no\s*)?[….\d/]*\s*", "", t)
    t = re.sub(r"^of\s+\d{1,2}\s+\w+\s+\d{4}\s*", "", t)
    t = re.sub(r"^(of\s+xxx|…/\.\.\.)\s*", "", t)
    return t.strip()


# Titles too thin to key on, and pipeline rows whose act we already hold under a real
# C-number. Collected and reported rather than silently dropped.
_WEAK_TITLES: List[str] = []
_SHADOWED: List[str] = []


def _blank(value) -> bool:
    """True for an empty cell, whichever reader produced it."""
    if value is None:
        return True
    if isinstance(value, float) and value != value:   # NaN
        return True
    return str(value).strip() == ""


def _read_xls(payload: bytes) -> List[Dict[str, Any]]:
    """Rows of the RegDel .xls export as dicts, keyed by the header row."""
    book = xlrd.open_workbook(file_contents=payload)
    sheet = book.sheet_by_index(0)
    if sheet.nrows == 0:
        return []
    headers = [str(sheet.cell_value(0, c)).strip() for c in range(sheet.ncols)]
    out: List[Dict[str, Any]] = []
    for r in range(1, sheet.nrows):
        out.append({headers[c]: sheet.cell_value(r, c) for c in range(sheet.ncols)})
    return out


def normalise_row(row: Dict[str, Any], act_type: str) -> Optional[Dict[str, Any]]:
    """Convert one Excel row into a secondary_acts record."""
    status_col = "Delegated act status" if act_type == "delegated" else "Implementing act status"
    title = row.get("Complete title")
    ccode = row.get("CCode")
    # xlrd gives '' for an empty cell; a float NaN can still arrive from older exports.
    if _blank(title):
        title = None
    if _blank(ccode):
        ccode = None
    title = title.strip() if isinstance(title, str) else None
    ccode = ccode.strip() if isinstance(ccode, str) else None
    if not title:
        return None
    if not ccode or ccode.lower() == "nan":
        # An act the Commission has ANNOUNCED but not adopted. Until 30 Sep 2026 this
        # returned None and 322 rows -- 207 Planned, 109 Cancelled, 6 On hold -- were
        # discarded, so the register's whole forward pipeline was invisible to us.
        #
        # There is no identifier to key on: a C-number is issued at adoption, the CELEX
        # at publication, and the register's JSON API is CSRF-protected so the Excel
        # export is the only open source. The key is therefore SYNTHETIC, and marked as
        # such so nothing downstream can read it as a Commission code.
        norm = _normalised_title(title)
        if len(norm) < 25:
            # 'Commission Implementing Regulation (*)' carries nothing to key on. A hash
            # of almost-nothing collides with the next almost-nothing.
            _WEAK_TITLES.append(title[:80])
            return None
        digest = hashlib.sha1(f"{act_type}|{norm}".encode("utf-8")).hexdigest()[:16]
        ccode = f"PLANNED:{digest}"
        is_pipeline = True
    else:
        is_pipeline = False

    celex = row.get("Celex number")
    celex = celex.strip() if isinstance(celex, str) else None
    if _blank(celex):
        celex = None

    policy = row.get("Policy area")
    policy_areas = []
    if isinstance(policy, str) and policy.strip():
        policy_areas = [p.strip() for p in policy.split(",") if p.strip()]

    dg = row.get("Leading Service Commission")
    dg = dg.strip() if isinstance(dg, str) and dg.strip() else None

    raw_status = row.get(status_col)
    # 'unknown', never 'draft'. A status we do not recognise is a gap in our mapping,
    # and calling it a draft asserts something about the act that we have not been told.
    # The enum carries 'unknown' precisely so an honest answer is available.
    if raw_status and str(raw_status).strip():
        key = str(raw_status).strip()
        status = _STATUS_MAP.get(key)
        if status is None:
            _UNMAPPED_STATUSES[key] = _UNMAPPED_STATUSES.get(key, 0) + 1
            status = "unknown"
    else:
        status = "unknown"

    parent_celex = derive_parent_celex(row.get("Basic legislative act"))

    # source_url is NOT NULL on the table. Prefer the EUR-Lex CELEX URL when
    # we have a CELEX. Otherwise fall back to the RegDel deep-link by CCode
    # (the public register is the authoritative source for draft / pending
    # acts that haven't yet received a CELEX).
    if celex:
        source_url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"
    else:
        # RegDel uses the CCode without parens in its deep links.
        # Example: C(2026)876 → https://webgate.ec.europa.eu/regdel/#/{type}/{CCODE}
        slug_path = "delegatedActs" if act_type == "delegated" else "implementingActs"
        source_url = f"https://webgate.ec.europa.eu/regdel/#/{slug_path}?lang=en&search={urllib.parse.quote(str(ccode))}"

    planned_period = row.get("Planned adoption date")
    planned_period = planned_period.strip()[:16] if isinstance(planned_period, str) and planned_period.strip() else None

    return {
        "id": str(uuid.uuid4()),
        "act_type": act_type,
        "reference": str(ccode).strip(),
        "title": str(title).strip()[:1000],
        "parent_celex": parent_celex,
        "celex": celex,
        "status": status,
        "proposing_dg": dg,
        "source_url": source_url,
        "policy_areas": policy_areas,
        # The Commission's indicative timing ("Q3 2026"). A PERIOD, never a date: it
        # must not reach adoption_date, which means the day the College adopted the act.
        "planned_adoption_period": planned_period,
        "is_pipeline": is_pipeline,
        "norm_title": _normalised_title(title),
        # Filled from the register's API by enrich(); None keeps what the row holds.
        "regdel_id": None, "parent_procedure_ref": None, "description": None,
        "scrutiny_period": None, "regdel_updated_at": None, "status_urgent": False,
        # True only when the parent CELEX came from the register; a regex parent may fill
        # an empty cell but never replace one (an unreachable register must not flip it).
        "parent_from_register": False,
    }


def enrich(records: List[Dict[str, Any]], register_items: Dict[str, List[dict]]) -> int:
    """Fill each record from its register record, matched by C-number, else by title.

    An announced act has no C-number, so it is matched on the same normalised title its
    synthetic key is built from. The register's parent CELEX replaces the regex's.
    """
    by_code, by_title = {}, {}
    for act_type, items in register_items.items():
        for it in items:
            code = str(it.get("cCode") or "").strip()
            if code:
                by_code[(act_type, code)] = it
            elif it.get("completeTitle"):
                by_title.setdefault((act_type, _normalised_title(it["completeTitle"])), it)
    matched = 0
    for r in records:
        it = (by_title.get((r["act_type"], r["norm_title"])) if r["is_pipeline"]
              else by_code.get((r["act_type"], r["reference"])))
        if not it:
            continue
        matched += 1
        f = register_fields(it, r["act_type"])
        parent = f.pop("register_parent_celex")
        if parent:
            r["parent_celex"], r["parent_from_register"] = parent, True
        r.update(f)
    return matched


def _held_first(r: Dict[str, Any], held: Dict[str, str]):
    """Sort key: the record matching what the row already holds, then the lowest register id."""
    return (r["reference"] != held.get(r.get("celex") or ""), r.get("regdel_id") is None,
            r.get("regdel_id") or 0, r["reference"])


def dedupe(records: List[Dict[str, Any]], held: Dict[str, str]):
    """One record per CELEX and per C-number, chosen the same way every run.

    The register lists some acts twice: 32017R0867 under both C(2016)1372 and C(2017)597,
    and 12 implementing C-numbers twice. Both records were upserted into the one row,
    the second overwriting the first, so the row's fields alternated and its change date
    moved every run for nothing. `held` maps a CELEX to the reference the row holds.
    """
    dropped: List[Dict[str, Any]] = []
    for key in ("celex", "reference"):
        groups: Dict[Any, List[Dict[str, Any]]] = {}
        for r in records:
            # By C-number only among acts without a CELEX: two CELEX holders sharing a
            # C-number are two rows, upserted on their own CELEX, and do not collide.
            # Keyed on the value alone: the table's unique indexes are on celex and on
            # reference, whatever the act type.
            k = r[key] if r.get(key) and (key == "celex" or not r.get("celex")) else None
            groups.setdefault(k, []).append(r)
        records = []
        for k, group in groups.items():
            if k is None or len(group) == 1:
                records.extend(group)
                continue
            group = sorted(group, key=lambda r: _held_first(r, held))
            records.append(group[0])
            dropped.extend(group[1:])
    return records, dropped


# Acts whose events are read on every run whatever the register's change time says:
# the ones whose objection period may still be running.
# coalesce: a NULL here would sort AHEAD of true in the DESC order below.
_OPEN_WINDOW = """coalesce(status = 'adopted'
                           OR objection_deadline_earliest >= current_date - 31, false)"""


_TITLE_DATE = re.compile(r"\bof (\d{1,2})\s+(January|February|March|April|May|June|July|August|"
                         r"September|October|November|December)\s+(\d{4})\b")
_MONTHS = {m: i for i, m in enumerate(("January February March April May June July August "
                                       "September October November December").split(), 1)}


def title_date(title: Optional[str]):
    """The date an adopted act's own title states ('... of 13 July 2026 amending ...')."""
    from datetime import date
    m = _TITLE_DATE.search(title or "")
    if not m:
        return None
    try:
        return date(int(m.group(3)), _MONTHS[m.group(2)], int(m.group(1)))
    except ValueError:
        return None


def adoption_to_store(held, register_day, title):
    """The adoption date to keep: the register's where the row has none, or where the
    act's own title agrees with the register against the held date. Otherwise the held
    date stays (and the run lists it)."""
    if not register_day:
        return held
    if not held:
        return register_day
    if held != register_day and title_date(title) == register_day:
        return register_day
    return held


def read_scrutiny(conn, register: "Register", max_seconds: float,
                  urgent_by_status: set = frozenset()) -> Dict[str, Any]:
    """Read the events of each delegated act the register changed since we last read it.

    Fills a publication date only where the row has none. Corrects an adoption date only
    where the act's own title agrees with the register (12 rows held a date neither
    states); any other disagreement is listed, not written. Writes the scrutiny columns
    and urgency_procedure outright: this job is their only writer.
    """
    import json
    import time
    cur = conn.cursor()
    cur.execute(f"""
        SELECT id, regdel_id, status::text, scrutiny_period, adoption_date, regdel_updated_at,
               title, reference
          FROM secondary_acts
         WHERE act_type = 'delegated' AND regdel_id IS NOT NULL
           AND (regdel_events_read_for IS DISTINCT FROM regdel_updated_at OR {_OPEN_WINDOW})
         ORDER BY ({_OPEN_WINDOW}) DESC, regdel_updated_at DESC NULLS LAST""")
    todo = cur.fetchall()
    out = {"due": len(todo), "read": 0, "failed": 0, "adoption_filled": 0,
           "adoption_corrected": 0, "adoption_differs": []}
    start = time.monotonic()
    for row_id, regdel_id, status, period, held_adoption, version, title, reference in todo:
        if time.monotonic() - start > max_seconds:
            break
        try:
            events = register.events(regdel_id)
        except Exception as exc:  # one act's events: counted, the run goes on
            out["failed"] += 1
            print(f"  [ERR] events of register record {regdel_id}: {exc}")
            continue
        s = scrutiny_from_events(events, period, status)
        adoption = adoption_to_store(held_adoption, s["adoption_date"], title)
        if held_adoption and adoption != held_adoption:
            out["adoption_corrected"] += 1
        elif s["adoption_date"] and held_adoption and s["adoption_date"] != held_adoption:
            out["adoption_differs"].append(f"{reference} (held {held_adoption}, register {s['adoption_date']})")
        cur.execute("""
            UPDATE secondary_acts
               SET adoption_date = %(adopt)s,
                   publication_date = coalesce(publication_date, %(pub)s),
                   ep_scrutiny = %(ep)s::jsonb, council_scrutiny = %(council)s::jsonb,
                   objection_deadline_earliest = %(earliest)s,
                   urgency_procedure = %(urgent)s,
                   regdel_events_read_for = %(version)s
             WHERE id = %(id)s""", {
            "adopt": adoption, "pub": s["publication_date"],
            "urgent": s["urgent"] or regdel_id in urgent_by_status,
            "ep": json.dumps(s["ep_scrutiny"]), "council": json.dumps(s["council_scrutiny"]),
            "earliest": s["objection_deadline_earliest"],
            "version": version, "id": row_id})
        out["read"] += 1
        out["adoption_filled"] += int(bool(s["adoption_date"] and not held_adoption))
        if out["read"] % 100 == 0:
            conn.commit()
    conn.commit()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument(
        "--type",
        choices=("delegated", "implementing", "both"),
        default="both",
    )
    ap.add_argument("--limit", type=int, default=None, help="Truncate after N rows (debug)")
    ap.add_argument("--events-seconds", type=float, default=120,
                    help="Time for reading delegated acts' scrutiny events; the rest waits for the next run")
    args = ap.parse_args()

    db_url = get_env("DATABASE_URL")
    if not db_url:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)

    targets = ("delegated", "implementing") if args.type == "both" else (args.type,)
    all_rows: List[Dict[str, Any]] = []

    for act_type in targets:
        print(f"[INFO] fetching RegDel {act_type} export...")
        bytes_ = fetch_excel(act_type)
        rows = _read_xls(bytes_)
        print(f"  {len(rows)} rows in Excel")
        for row in rows:
            rec = normalise_row(row, act_type)
            if rec:
                all_rows.append(rec)
        if args.limit:
            all_rows = all_rows[: args.limit]
            break

    # A pipeline row whose act we already hold under a real C-number is the SAME act
    # listed twice by the register, once as planned and once as published. 7 of the 322
    # were like that on 30 Sep 2026. The real act wins; keeping both would hand a
    # subscriber one act twice, under two different statuses.
    real_titles = {(r["act_type"], r["norm_title"]) for r in all_rows if not r["is_pipeline"]}
    kept = []
    for r in all_rows:
        if r["is_pipeline"] and (r["act_type"], r["norm_title"]) in real_titles:
            _SHADOWED.append(r["title"][:80])
            continue
        kept.append(r)
    all_rows = kept

    pipeline_n = sum(1 for r in all_rows if r["is_pipeline"])
    print(f"[INFO] {len(all_rows)} records normalised (apply={args.apply}); "
          f"{pipeline_n} announced-but-not-adopted")
    if _SHADOWED:
        print(f"[INFO] {len(_SHADOWED)} announced act(s) skipped: already held under a "
              f"real C-number")
    if _WEAK_TITLES:
        print(f"[INFO] {len(_WEAK_TITLES)} announced act(s) skipped: title too thin to "
              f"identify, e.g. {_WEAK_TITLES[0]!r}")

    # The register's API. If it cannot be read, the export's rows are still stored and
    # the run says it is degraded: losing the scrutiny fields for one run must not cost
    # the acts themselves.
    degraded: List[str] = []
    register = None
    try:
        register = Register()
        items = {t: register.records(t) for t in targets}
        matched = enrich(all_rows, items)
        print(f"[INFO] register API: {sum(map(len, items.values()))} record(s), "
              f"{matched} of {len(all_rows)} export rows matched")
        if matched < 0.9 * len(all_rows):
            degraded.append(f"register API matched only {matched} of {len(all_rows)} rows")
    except Exception as exc:
        register = None
        degraded.append(f"register API unreadable ({exc.__class__.__name__}: {exc})")
        print(f"[WARN] {degraded[-1]}")

    if not args.apply:
        for r in all_rows[:5]:
            print(f"  {r['act_type']:13s} {r['reference']:14s} celex={(r['celex'] or '-'):12s} dg={(r['proposing_dg'] or '-'):8s} parent={(r['parent_celex'] or '-'):12s} status={r['status']:10s} policy={r['policy_areas'][:1]}")
        print("[NOTE] dry-run — pass --apply to write to DB")
        return

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    # The hand-curated seed rows this script once wiped are long gone: the first run
    # removed them. The wipe itself was REMOVED on 30 Sep 2026 because it had started
    # destroying real acts.
    #
    # It matched on a hard-coded list of ten C-numbers, on the assumption that those
    # codes were invented. They were not invented for long: the Commission has since
    # issued C(2026)1234 and C(2026)2345 to real implementing regulations (amendments to
    # Annexes V and XIV), and the register now exports them. Every run therefore DELETED
    # those two acts and the loop below re-inserted them seconds later with a fresh
    # uuid4 -- so their `id`, the identifier GovClipping uses for incremental sync,
    # changed every single day while the row looked untouched.
    #
    # A cleanup keyed on values someone else allocates is a cleanup with an expiry date.
    # If fixture rows ever need removing again, match them on what makes them fixtures
    # (their fabricated titles), never on an identifier the source controls.

    # Two upsert paths, chosen by whether the act has a CELEX.
    #
    # CELEX is the identity. `reference` (the C(YYYY)NNNN code) is a LABEL the Commission
    # can re-issue for the same act, so conflicting on it lets a second row in for a CELEX
    # we already hold. That produced 783 duplicate pairs once, was cleaned up without
    # changing this line, and produced 80 more by 30 Sep 2026. Migration 258 adds the
    # partial unique index that backs the ON CONFLICT (celex) target.
    #
    # 731 acts have no CELEX yet (adopted but not published, or draft). For those the
    # C-number is the only stable handle we have, so they keep the reference path.
    #
    # Every updated column is wrapped in COALESCE(EXCLUDED.x, secondary_acts.x): a later
    # export with an empty cell must not blank a value we already hold. The old statement
    # assigned EXCLUDED.celex directly, so one empty cell would have erased a good CELEX.
    SET_CLAUSE = r"""
                  -- The export serves one record's title as the draft ("(EU) …/...") on
                  -- one day and the final one the next. A draft never replaces a final
                  -- title: the swap moved 185-973 rows' change date per run (14 Oct 2026).
                  title        = CASE WHEN EXCLUDED.title ~ '(…|\.\.\.)\s*/\s*(…|\.\.\.)'
                                       AND secondary_acts.title !~ '(…|\.\.\.)\s*/\s*(…|\.\.\.)'
                                      THEN secondary_acts.title
                                      ELSE COALESCE(EXCLUDED.title, secondary_acts.title) END,
                  parent_celex = CASE WHEN %(parent_from_register)s
                                      THEN COALESCE(EXCLUDED.parent_celex, secondary_acts.parent_celex)
                                      ELSE COALESCE(secondary_acts.parent_celex, EXCLUDED.parent_celex) END,
                  status       = EXCLUDED.status,
                  proposing_dg = COALESCE(EXCLUDED.proposing_dg, secondary_acts.proposing_dg),
                  source_url   = COALESCE(EXCLUDED.source_url, secondary_acts.source_url),
                  policy_areas = COALESCE(EXCLUDED.policy_areas, secondary_acts.policy_areas),
                  planned_adoption_period = EXCLUDED.planned_adoption_period,
                  regdel_id    = COALESCE(EXCLUDED.regdel_id, secondary_acts.regdel_id),
                  parent_procedure_ref = COALESCE(EXCLUDED.parent_procedure_ref, secondary_acts.parent_procedure_ref),
                  description  = COALESCE(EXCLUDED.description, secondary_acts.description),
                  scrutiny_period = COALESCE(EXCLUDED.scrutiny_period, secondary_acts.scrutiny_period),
                  regdel_updated_at = COALESCE(EXCLUDED.regdel_updated_at, secondary_acts.regdel_updated_at),
                  last_updated = NOW()
    """

    INSERT_HEAD = """
                INSERT INTO secondary_acts
                  (id, act_type, reference, title, parent_celex, celex, status,
                   proposing_dg, source_url, policy_areas, planned_adoption_period,
                   regdel_id, parent_procedure_ref, description, scrutiny_period,
                   regdel_updated_at,
                   scraped_at, first_seen, last_updated)
                VALUES
                  (%(id)s, %(act_type)s, %(reference)s, %(title)s, %(parent_celex)s,
                   %(celex)s, %(status)s, %(proposing_dg)s, %(source_url)s, %(policy_areas)s,
                   %(planned_adoption_period)s, %(regdel_id)s, %(parent_procedure_ref)s,
                   %(description)s, %(scrutiny_period)s,
                   %(regdel_updated_at)s, NOW(), NOW(), NOW())
    """

    # On the CELEX path `reference` is deliberately NOT overwritten. When RegDel hands us
    # a different C-number for an act we already hold, we cannot tell from the export
    # which one is right -- and in 3 of the 7 cases found on 30 Sep the number we already
    # had contradicted its own adoption year, so the incoming one was the better value.
    # Keeping both, one in `reference` and the other in merged_from, leaves the evidence
    # for a human instead of silently picking. The @> guard stops the same alternative
    # being appended on every daily run.
    SQL_BY_CELEX = INSERT_HEAD + """
                ON CONFLICT (celex) WHERE celex IS NOT NULL AND celex <> ''
                DO UPDATE SET
    """ + SET_CLAUSE + """,
                  merged_from = CASE
                    WHEN secondary_acts.reference IS DISTINCT FROM EXCLUDED.reference
                     AND NOT (COALESCE(secondary_acts.merged_from, '[]'::jsonb)
                              @> jsonb_build_array(jsonb_build_object(
                                   'reference', EXCLUDED.reference)))
                    THEN COALESCE(secondary_acts.merged_from, '[]'::jsonb)
                         || jsonb_build_array(jsonb_build_object(
                              'reference', EXCLUDED.reference,
                              'source', 'regdel_alternative_ccode',
                              'seen', NOW()::text))
                    ELSE secondary_acts.merged_from END
                RETURNING (xmax = 0) AS was_inserted
    """

    SQL_BY_REFERENCE = INSERT_HEAD + """
                ON CONFLICT (reference) DO UPDATE SET
    """ + SET_CLAUSE + """,
                  celex = COALESCE(EXCLUDED.celex, secondary_acts.celex)
                RETURNING (xmax = 0) AS was_inserted
    """

    # Same as above but the CELEX WE hold wins. Used only on the fallback path, where the
    # export's CELEX has already been shown to disagree with a row we corrected against
    # Cellar. COALESCE order is reversed on purpose: ours first, theirs only if we have none.
    SQL_BY_REFERENCE_KEEP_CELEX = INSERT_HEAD + """
                ON CONFLICT (reference) DO UPDATE SET
    """ + SET_CLAUSE + """,
                  celex = COALESCE(secondary_acts.celex, EXCLUDED.celex)
                RETURNING (xmax = 0) AS was_inserted
    """

    # Counted from what the database RETURNS, not from how many statements were sent.
    # The old loop incremented `inserted` once per attempt, so an update and an insert
    # were indistinguishable and the total was really "rows tried".
    # One record per CELEX and per C-number, preferring the one the row already holds.
    celexes = sorted({r["celex"] for r in all_rows if r.get("celex")})
    cur.execute("SELECT celex, reference FROM secondary_acts WHERE celex = ANY(%s)", (celexes,))
    held = dict(cur.fetchall())
    all_rows, dropped = dedupe(all_rows, held)
    if dropped:
        print(f"[INFO] {len(dropped)} register record(s) duplicate an act already listed and "
              f"were not stored over it: " + ", ".join(sorted(r["reference"] for r in dropped)[:20]))

    inserted = updated = errors = celex_kept = 0
    for n, r in enumerate(all_rows, 1):
        # SAVEPOINT per row. conn.rollback() discards every uncommitted row in the
        # batch, not just the one that failed, so a single bad record used to throw
        # away up to 200 good ones silently. Same fix as ingest_transparency_meetings.
        try:
            cur.execute("SAVEPOINT one_row")
            try:
                cur.execute(SQL_BY_CELEX if r.get("celex") else SQL_BY_REFERENCE, r)
            except psycopg2.errors.UniqueViolation:
                # The CELEX path found no row to update and tried to INSERT, but this
                # act's C-number is already held by a row carrying a DIFFERENT CELEX.
                # That happens when we have corrected a CELEX the register still gets
                # wrong: C(2015)9013 is Regulation (EU) 2016/451, which RegDel exports
                # as 32015R0451 -- a CELEX that does not exist in Cellar at all.
                #
                # Fall back to matching on the C-number, and let the CELEX we already
                # hold win. Our value is the one checked against Cellar; re-applying the
                # export's would silently undo the correction on the next daily run.
                cur.execute("ROLLBACK TO SAVEPOINT one_row")
                cur.execute(SQL_BY_REFERENCE_KEEP_CELEX, r)
                celex_kept += 1
            row = cur.fetchone()
            if row and row[0]:
                inserted += 1
            else:
                updated += 1
            cur.execute("RELEASE SAVEPOINT one_row")
        except Exception as exc:
            cur.execute("ROLLBACK TO SAVEPOINT one_row")
            print(f"  [ERR] {r['reference']}: {exc}")
            errors += 1
        # Commit on rows PROCESSED, not on rows inserted: after the first full run
        # almost everything is an update, so an `inserted % 200` gate would hold the
        # whole run in one transaction.
        if n % 200 == 0:
            conn.commit()
    conn.commit()
    conn.close()

    print(f"[DONE] inserted={inserted} updated={updated} errors={errors} "
          f"of {len(all_rows)} record(s)")

    # Scrutiny events, on a fresh connection: the upserts above hold theirs for minutes.
    if register is not None and "delegated" in targets and not args.limit:
        conn = psycopg2.connect(db_url)
        try:
            ev = read_scrutiny(conn, register, args.events_seconds,
                               {r["regdel_id"] for r in all_rows
                                if r["act_type"] == "delegated" and r["status_urgent"] and r["regdel_id"]})
        finally:
            conn.close()
        print(f"[SCRUTINY] {ev['read']} of {ev['due']} act(s) read, {ev['failed']} failed; "
              f"adoption date filled on {ev['adoption_filled']}, corrected on "
              f"{ev['adoption_corrected']} (the act's title agrees with the register)")
        if ev["adoption_differs"]:
            print(f"[INFO] {len(ev['adoption_differs'])} act(s) whose held adoption date the "
                  f"register contradicts, left as held: " + "; ".join(ev["adoption_differs"][:20]))
        if ev["read"] + ev["failed"] < ev["due"]:
            degraded.append(f"scrutiny events read for {ev['read']} of {ev['due']} act(s); "
                            f"the rest resume next run")
        if ev["failed"] and ev["failed"] >= max(5, ev["read"] // 10):
            degraded.append(f"{ev['failed']} act(s) whose events could not be read")
    if degraded:
        print(f"[SYNC_STATUS] degraded: {'; '.join(degraded)}")
    if celex_kept:
        print(f"[INFO] {celex_kept} act(s) kept the CELEX we hold over the one the "
              f"register exports (ours is the one verified against Cellar)")

    if _UNMAPPED_STATUSES:
        print("[WARN] status value(s) the register uses that we do not map; "
              "stored as 'unknown':")
        for k, v in sorted(_UNMAPPED_STATUSES.items(), key=lambda kv: -kv[1]):
            print(f"        {k!r}: {v} act(s)")
        print("        add them to _STATUS_MAP and to secondary_act_status_enum")

    # Three states, never two. A run that stored nothing is not a success: the RegDel
    # export can return an empty or restructured sheet, and a silent green would hide
    # it for weeks (feedback_a_green_signal_from_a_check_that_never_looked).
    if not all_rows:
        print("[FATAL] the RegDel export yielded no usable rows")
        return 1
    if errors and inserted + updated == 0:
        print(f"[FATAL] every row failed ({errors} error(s))")
        return 1
    if errors:
        print(f"[DEGRADED] {errors} row(s) rejected, {inserted + updated} stored")
        return 0
    return 0


if __name__ == "__main__":
    # sys.exit(main()), not main(): a script that returns 1 but exits 0 is
    # a failure the scheduler records as a success.
    sys.exit(main())

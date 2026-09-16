"""Statistics from the Commission's 'Implementing EU law' dashboards, validated and cached.

Source
------
ec.europa.eu/implementing-eu-law serves three dashboards (infringement cases,
transposition of directives, pre-infringement dialogues). Every chart reads a JSON
endpoint under the same host, e.g. `get-cases-opened-closed-active?end-year=2025&
year-range=5`, returning Highcharts series `[{"name": ..., "data": [{"name", "y"}]}]`.
Traced from the dashboards' own chart scripts on 16 Sep 2026; plain HTTP.

Why the inputs are validated here
---------------------------------
The source never rejects a bad parameter: `member-state=GR` (the code is EL),
`policy-area=ENV` (the filter wants the numeric id 14) or an ISO date all answer 200
with a series of zeros, indistinguishable from "no cases". So every value is checked
and translated before the call, and anything unknown is a ValueError the API turns
into a 422, never a silent zero.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional

BASE = "https://ec.europa.eu/implementing-eu-law"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/140.0 Safari/537.36",
            "Accept": "application/json"}
CACHE_SECONDS = 6 * 3600
CACHE_MAX_ENTRIES = 500

MEMBER_STATES = {
    "AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "CY": "Cyprus", "CZ": "Czechia",
    "DE": "Germany", "DK": "Denmark", "EE": "Estonia", "EL": "Greece", "ES": "Spain",
    "FI": "Finland", "FR": "France", "HR": "Croatia", "HU": "Hungary", "IE": "Ireland",
    "IT": "Italy", "LT": "Lithuania", "LU": "Luxembourg", "LV": "Latvia", "MT": "Malta",
    "NL": "Netherlands", "PL": "Poland", "PT": "Portugal", "RO": "Romania", "SE": "Sweden",
    "SI": "Slovenia", "SK": "Slovakia",
}
# ISO 3166 codes people type, mapped to the codes the Commission uses.
MEMBER_STATE_ALIASES = {"GR": "EL"}
CASE_TYPES = {
    "BAD": "Bad application of directives",
    "REG": "Bad application of regulations, Treaties and decisions",
    "NCM": "Non-communication of transposition measures for directives",
    "NCF": "Non-conformity of transposition for directives",
}

# (section page, the get-web-data key holding that section's last update)
SECTIONS = {
    "infringements": ("member-state-infringement-cases", "LAST_UPDATE_DATE"),
    "transposition": ("transposition-directives", "TR_LAST_UPDATE_DATE"),
    "pre_infringement_dialogues": ("dialogue-member-state", "LAST_UPDATE_DATE"),
}
# Filter vocabularies differ per section.
_POLICY_AREA_FILTERS = {
    "infringements": "/get-filters-policy-area",
    "transposition": "/get-filters-policy-area-transpositions",
    "pre_infringement_dialogues": "/get-filters-policy-area-eu-pilot",
}


@dataclass(frozen=True)
class Dataset:
    key: str
    section: str
    path: str
    title: str
    description: str
    unit: str
    params: tuple  # accepted API params: date, year, month, end_year, year_range, member_state, case_type, policy_area
    lang: bool = False


DATASETS = {d.key: d for d in [
    Dataset("active-cases-by-member-state", "infringements", "/get-repartition-infringements-cases-member-state",
            "Active infringement cases per Member State",
            "Number of infringement cases open against each Member State on a given date.",
            "cases", ("date", "case_type", "policy_area")),
    Dataset("active-cases-by-type", "infringements", "/get-repartition-infringements-cases-type",
            "Active infringement cases by type of infringement",
            "Open cases on a given date, split into non-communication, non-conformity and bad application.",
            "cases", ("date", "member_state", "policy_area"), lang=True),
    Dataset("active-cases-by-policy-area", "infringements", "/get-repartition-infringements-cases-policy-area",
            "Active infringement cases by policy area",
            "Open cases on a given date, split by the Commission department responsible.",
            "cases", ("date", "member_state", "case_type"), lang=True),
    Dataset("decisions-adopted-in-year", "infringements", "/get-decisions-adopted-year",
            "Infringement decisions adopted in a year",
            "Letters of formal notice, reasoned opinions, Court referrals and closures adopted in one year.",
            "decisions", ("year", "member_state", "case_type", "policy_area"), lang=True),
    Dataset("cases-opened-closed-active", "infringements", "/get-cases-opened-closed-active",
            "Infringement cases opened, closed and active per year",
            "New, closed and active infringement cases for each year of a period.",
            "cases", ("end_year", "year_range", "member_state", "case_type", "policy_area")),
    Dataset("last-step-before-closure", "infringements", "/get-last-step-before-closure",
            "Stage reached before cases were closed",
            "For cases closed in each year of a period, the last decision adopted before closure.",
            "cases", ("end_year", "year_range", "member_state", "case_type", "policy_area")),
    Dataset("time-to-comply-with-court-rulings", "infringements", "/get-time-taken-to-comply",
            "Time taken by Member States to comply with Court rulings",
            "Average months between a Court of Justice ruling and the Member State's compliance, per year.",
            "months", ("end_year", "year_range", "case_type", "policy_area")),
    Dataset("average-case-duration", "infringements", "/get-average-duration",
            "Average duration of infringement cases",
            "Average handling time of infringement cases, in months, per year of a period.",
            "months", ("end_year", "year_range", "member_state", "case_type", "policy_area")),
    Dataset("transposition-deficit-by-member-state", "transposition", "/get-transposition-deficit-member-state",
            "Transposition deficit per Member State",
            "Share of directives whose transposition deadline has passed without complete notification, per Member State, for a given month.",
            "percent", ("year", "month", "policy_area")),
    Dataset("transposition-deficit-trend", "transposition", "/get-transposition-deficit-trend",
            "Transposition deficit over time",
            "The transposition deficit per year of a period, for the EU or one Member State.",
            "percent", ("end_year", "year_range", "member_state", "policy_area")),
    Dataset("conformity-deficit-by-member-state", "transposition", "/get-conformity-deficit-member-state",
            "Conformity deficit per Member State",
            "Share of transposed directives the Commission found incorrectly transposed, per Member State, for a given month.",
            "percent", ("year", "month", "policy_area")),
    Dataset("conformity-deficit-trend", "transposition", "/get-conformity-deficit-trend",
            "Conformity deficit over time",
            "The conformity deficit per year of a period, for the EU or one Member State.",
            "percent", ("end_year", "year_range", "member_state", "policy_area")),
    Dataset("directives-to-transpose-trend", "transposition", "/get-transposition-directive-trend",
            "Directives with a transposition deadline per year",
            "Number of directives whose transposition deadline fell in each year of a period.",
            "directives", ("end_year", "year_range", "policy_area")),
    Dataset("directives-by-policy-area", "transposition", "/get-repartition-directives-policy-area",
            "Directives to transpose by policy area",
            "Directives with a transposition deadline in a year, by Commission department.",
            "directives", ("year",), lang=True),
    Dataset("dialogues-by-member-state", "pre_infringement_dialogues", "/get-repartition-eu-pilot-cases-member-state",
            "Active pre-infringement dialogues per Member State",
            "Open pre-infringement dialogues (formerly EU Pilot) per Member State at the end of a year.",
            "dialogues", ("year", "policy_area")),
    Dataset("dialogues-by-policy-area", "pre_infringement_dialogues", "/get-repartition-eu-pilot-cases-policy-area",
            "Pre-infringement dialogues by policy area",
            "Pre-infringement dialogues in a year by Commission department.",
            "dialogues", ("year", "member_state"), lang=True),
    Dataset("dialogues-opened-closed-active", "pre_infringement_dialogues", "/get-eu-pilot-cases-opened-closed-active",
            "Pre-infringement dialogues opened, closed and active per year",
            "New, closed and active pre-infringement dialogues for each year of a period.",
            "dialogues", ("end_year", "year_range", "member_state", "policy_area")),
    Dataset("dialogue-average-duration", "pre_infringement_dialogues", "/get-eu-pilot-average-time-taken",
            "Average duration of pre-infringement dialogues",
            "Average time, in months, taken to handle pre-infringement dialogues per year.",
            "months", ("end_year", "year_range", "member_state", "policy_area")),
    Dataset("dialogue-resolution-rate", "pre_infringement_dialogues", "/get-eu-pilot-resolution-rate",
            "Resolution rate of pre-infringement dialogues",
            "Dialogues closed without escalating to an infringement case, per year, with the EU-level rate.",
            "dialogues and percent", ("end_year", "year_range")),
]}

_cache: dict[str, tuple[float, object]] = {}


def _get_json(path: str):
    import httpx

    now = time.monotonic()
    hit = _cache.get(path)
    if hit and now - hit[0] < CACHE_SECONDS:
        return hit[1]
    r = httpx.get(BASE + path, headers=_HEADERS, timeout=60)
    if r.status_code != 200:
        raise ConnectionError(f"source answered {r.status_code} for {path}")
    data = r.json()
    if len(_cache) >= CACHE_MAX_ENTRIES:
        # Every parameter combination is a key; drop expired entries, then the oldest.
        for k in [k for k, (t, _) in _cache.items() if now - t >= CACHE_SECONDS]:
            _cache.pop(k, None)
        while len(_cache) >= CACHE_MAX_ENTRIES:
            _cache.pop(min(_cache, key=lambda k: _cache[k][0]))
    _cache[path] = (now, data)
    return data


def last_update(section: str) -> Optional[date]:
    """The dashboard's own 'last update' date for a section, or None."""
    try:
        rows = _get_json("/get-web-data")
    except Exception:
        return None
    key = SECTIONS[section][1]
    for row in rows or []:
        if row.get("name") == key:
            try:
                return datetime.strptime(row["value"], "%d-%m-%Y").date()
            except (ValueError, TypeError, KeyError):
                return None
    return None


def policy_areas(section: str) -> list[dict]:
    """[{id, code, title}] the section's policy-area filter accepts."""
    rows = _get_json(_POLICY_AREA_FILTERS[section] + "?lang=EN")
    out = []
    for row in rows or []:
        if len(row) >= 2:
            out.append({"id": str(row[0]), "code": row[1], "title": row[2] if len(row) > 2 else None})
    return out


def normalise_member_state(value: Optional[str]) -> Optional[str]:
    if value is None or not value.strip():
        return None
    code = MEMBER_STATE_ALIASES.get(value.strip().upper(), value.strip().upper())
    if code not in MEMBER_STATES:
        raise ValueError(f"member_state must be one of {', '.join(sorted(MEMBER_STATES))} (Greece is EL)")
    return code


def normalise_case_types(values: Optional[list[str]]) -> list[str]:
    out = []
    for v in values or []:
        code = v.strip().upper()
        if code not in CASE_TYPES:
            raise ValueError(f"case_type must be one of {', '.join(CASE_TYPES)}")
        out.append(code)
    return out


def normalise_policy_areas(section: str, values: Optional[list[str]]) -> list[tuple[str, str]]:
    """[(id the source filters on, department code)] for each value given as either."""
    if not values:
        return []
    known = policy_areas(section)
    by_code = {a["code"].upper(): a["id"] for a in known if a.get("code")}
    code_of = {a["id"]: a["code"] for a in known}
    out = []
    for v in values:
        s = v.strip()
        if s in code_of:
            out.append((s, code_of[s]))
        elif s.upper() in by_code:
            out.append((by_code[s.upper()], s.upper()))
        else:
            raise ValueError(f"policy_area '{s}' is not a policy area of this section; "
                             f"use a department code such as {', '.join(sorted(by_code)[:6])}")
    return out


def fetch_dataset(key: str, *, day: Optional[date] = None, year: Optional[int] = None,
                  month: Optional[int] = None, end_year: Optional[int] = None,
                  year_range: Optional[int] = None, member_state: Optional[str] = None,
                  case_type: Optional[list[str]] = None, policy_area: Optional[list[str]] = None,
                  today: Optional[date] = None) -> dict:
    """Validated call to one dataset. Returns {dataset, parameters, series, rows, source_url,
    last_update, public_url}. Raises KeyError (unknown dataset), ValueError (bad or
    unsupported parameter) or ConnectionError (source unavailable)."""
    ds = DATASETS[key]
    today = today or date.today()
    given = {"date": day, "year": year, "month": month, "end_year": end_year, "year_range": year_range,
             "member_state": member_state, "case_type": case_type or None, "policy_area": policy_area or None}
    unsupported = [k for k, v in given.items() if v is not None and k not in ds.params]
    if unsupported:
        raise ValueError(f"{key} does not accept {', '.join(unsupported)}; it accepts {', '.join(ds.params) or 'no filters'}")

    applied: dict = {}
    query: list[tuple[str, str]] = []
    if "date" in ds.params:
        d = day or today
        if d > today:
            raise ValueError("date cannot be in the future")
        applied["date"] = d.isoformat()
        query.append(("date", d.strftime("%d-%m-%Y")))
    if "year" in ds.params:
        default_year = today.year if key in ("transposition-deficit-by-member-state", "conformity-deficit-by-member-state",
                                             "directives-by-policy-area") else today.year - 1
        y = year or default_year
        if not 2000 <= y <= today.year:
            raise ValueError(f"year must be between 2000 and {today.year}")
        applied["year"] = y
        if key == "dialogues-by-member-state":
            query.append(("date", f"31-12-{y}"))
        else:
            query.append(("year", str(y)))
    if "month" in ds.params:
        m = month or (today.month if (year or today.year) == today.year else 12)
        if not 1 <= m <= 12:
            raise ValueError("month must be between 1 and 12")
        applied["month"] = m
        query.append(("month", str(m)))
    if "end_year" in ds.params:
        ey = end_year or today.year - 1
        if not 2000 <= ey <= today.year:
            raise ValueError(f"end_year must be between 2000 and {today.year}")
        yr = year_range or 5
        if not 1 <= yr <= 25:
            raise ValueError("year_range must be between 1 and 25")
        applied.update(end_year=ey, year_range=yr)
        query += [("end-year", str(ey)), ("year-range", str(yr))]
    if ds.lang:
        query.append(("lang", "EN"))
    ms = normalise_member_state(member_state)
    if ms:
        applied["member_state"] = ms
        query.append(("member-state", ms))
    for ct in normalise_case_types(case_type):
        applied.setdefault("case_type", []).append(ct)
        query.append(("case-type", ct))
    for pa_id, pa_code in normalise_policy_areas(ds.section, policy_area):
        applied.setdefault("policy_area", []).append(pa_code)
        query.append(("policy-area", pa_id))

    from urllib.parse import urlencode
    path = ds.path + ("?" + urlencode(query) if query else "")
    raw = _get_json(path)
    series, rows = [], []
    for s in raw or []:
        points = [{"label": str(p.get("name")), "value": p.get("y")} for p in (s.get("data") or [])]
        series.append({"name": s.get("name"), "points": points})
        rows += [{"series": s.get("name"), **p} for p in points]
    page = SECTIONS[ds.section][0]
    return {
        "dataset": key, "section": ds.section, "title": ds.title, "description": ds.description,
        "unit": ds.unit, "parameters": applied, "series": series, "rows": rows,
        "source_url": BASE + path, "public_url": f"{BASE}/{page}/en",
        "last_update": last_update(ds.section),
        "fetched_at": datetime.now(timezone.utc),
    }

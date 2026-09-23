#!/usr/bin/env python3
"""Build the client-facing EU funding match report for Terraqui, GBSB and Cadence.

Pulls live opportunities from Brubru's production API v2 (funding + agency
folders + TED), verifies status, dates, English titles and budgets for every
Funding & Tenders portal row against the portal's own search API (the API's
`status` lags, some titles arrive in German/Polish/Swedish, and ~800 rows carry
no deadline), scores every opportunity against a written profile of each
organisation, and renders ONE self-contained HTML file.

Run every three days:

    python3.12 backend/scripts/build_funding_matches.py
    python3.12 backend/scripts/build_funding_matches.py --date 2026-09-18
    python3.12 backend/scripts/build_funding_matches.py --cache-dir /tmp/fm --use-cache

Nothing is committed, deployed or emailed. The API key is read from
backend/.env (BRUBRU_API_KEY) and never printed. Every request carries
`X-Brubru-Probe: 1` so the traffic is excluded from user analytics.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import html
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import uuid
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
REPO = Path(_REPO_ROOT)
BASE = "https://brubru-production.up.railway.app"
SEDIA_URL = "https://api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey=SEDIA&text=***"
FT_TOPIC = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/"
FT_TENDER = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/tender-details/"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140 Safari/537.36"
SEDIA_STATUS = {"31094501": "forthcoming", "31094502": "open", "31094503": "closed"}
EXCLUDED_ALL_TYPES = {"cohesion_allocation", "cap_payment", "solidarity_case"}


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def load_key() -> str:
    env = REPO / "backend" / ".env"
    key = None
    try:
        from dotenv import dotenv_values  # type: ignore
        key = dotenv_values(env).get("BRUBRU_API_KEY")
    except Exception:
        pass
    if not key and env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("BRUBRU_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        sys.exit("[ERROR] BRUBRU_API_KEY not found in backend/.env")
    return key


class Api:
    def __init__(self, key: str):
        self.key = key
        self.calls = 0
        self.failures: list[str] = []

    def get(self, path: str, **params):
        url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
        err = None
        for attempt in range(4):
            try:
                req = urllib.request.Request(url, headers={"X-API-Key": self.key, "X-Brubru-Probe": "1"})
                with urllib.request.urlopen(req, timeout=150) as resp:
                    self.calls += 1
                    unknown = resp.headers.get("X-Brubru-Unknown-Params")
                    if unknown:
                        print(f"[INFO] {path} ignored params: {unknown}")
                    return json.load(resp)
            except Exception as e:  # retry, then record
                err = e
                time.sleep(3 * (attempt + 1))
        self.failures.append(f"{path} {params}: {type(err).__name__}")
        raise err

    def all_pages(self, path: str, limit: int = 100, max_pages: int = 60, **params):
        out, page = [], 1
        while page <= max_pages:
            d = self.get(path, page=page, limit=limit, **params)
            items = d.get("data") or d.get("items") or []
            out += items
            if not d.get("has_more") or not items:
                break
            page += 1
        return out


def sedia_search(query: dict, page: int = 1, page_size: int = 100) -> dict:
    boundary = uuid.uuid4().hex
    parts = [("query", json.dumps(query)), ("languages", '["en"]')]
    body = b""
    for name, value in parts:
        body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{name}.json"\r\n'
                 f"Content-Type: application/json\r\n\r\n{value}\r\n").encode()
    body += f"--{boundary}--\r\n".encode()
    url = f"{SEDIA_URL}&pageSize={page_size}&pageNumber={page}"
    err = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
            return json.load(urllib.request.urlopen(req, timeout=120))
        except Exception as e:
            err = e
            time.sleep(4 * (attempt + 1))
    raise err


def sedia_enrich(identifiers: list[str]) -> dict[str, dict]:
    """Portal metadata per identifier. Batches of 20, paginated: a batch can
    return several hundred records, and an unpaginated call silently truncates."""
    out: dict[str, dict] = {}
    ids = sorted(set(i for i in identifiers if i))

    def one(batch):
        got, page = [], 1
        q = {"bool": {"must": [{"terms": {"identifier": batch}}, {"terms": {"type": ["0", "1", "2", "8"]}}]}}
        while True:
            r = sedia_search(q, page=page)
            res = r.get("results") or []
            got += res
            if page * 100 >= (r.get("totalResults") or 0) or not res:
                break
            page += 1
        return got

    batches = [ids[n:n + 20] for n in range(0, len(ids), 20)]
    with ThreadPoolExecutor(4) as ex:
        for res in ex.map(one, batches):
            for x in res:
                m = x.get("metadata") or {}
                iden = (m.get("identifier") or [None])[0]
                if iden:
                    out[iden] = m
    return out


def sedia_portal_open_all() -> list[dict]:
    """Every open or forthcoming topic, tender and cascade call on the portal
    (metadata only), used to show what Brubru's API does not yet hold."""
    q = {"bool": {"must": [{"terms": {"type": ["1", "2", "8"]}}, {"terms": {"status": ["31094501", "31094502"]}}]}}
    out, page = [], 1
    while True:
        r = sedia_search(q, page=page)
        res = r.get("results") or []
        out += [x.get("metadata") or {} for x in res]
        if page * 100 >= (r.get("totalResults") or 0) or not res:
            break
        page += 1
    return out


def sedia_portal_open_count() -> int | None:
    try:
        q = {"bool": {"must": [{"terms": {"type": ["1", "2", "8"]}}, {"terms": {"status": ["31094501", "31094502"]}}]}}
        return sedia_search(q, page=1, page_size=1).get("totalResults")
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Harvest
# --------------------------------------------------------------------------- #
FT_ENDPOINTS = ["/api/v2/funding/funding-opportunities", "/api/v2/funding/startups",
                "/api/v2/funding/innovation-fund", "/api/v2/funding/justice",
                "/api/v2/funding/ft-calls-for-tenders"]
AGENCY_ENDPOINTS = ["/api/v2/funding/all", "/api/v2/eismea/calls", "/api/v2/hadea/calls",
                    "/api/v2/hadea/tenders", "/api/v2/eccc/calls", "/api/v2/eeas/tenders"]


def harvest_ted(api: Api, today: dt.date) -> tuple[list[dict], list[str]]:
    """TED notices with a deadline from today. The endpoint orders only by
    publication_date, so pages are nondeterministic: slice by deadline day,
    then contract nature, then buyer country, keeping every slice <= 100."""
    notes: list[str] = []
    countries = ["AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "EL", "GR", "ES", "FI", "FR", "HR", "HU",
                 "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK", "NO", "CH",
                 "IS", "LI", "MK", "RS", "AL", "ME", "TR", "UA", "MD", "BA", "XK", "GE", "AM", "UK", "GB"]

    def window(start: dt.date, end: dt.date):
        base = dict(deadline_from=start.isoformat(), deadline_to=end.isoformat())
        d = api.get("/api/v2/funding/tenders", limit=100, **base)
        total = d.get("total") or 0
        if total <= 100:
            return total, d.get("data") or [], []
        rows, short = [], []
        for cn in ("services", "supplies", "works"):
            d2 = api.get("/api/v2/funding/tenders", limit=100, contract_nature=cn, **base)
            if (d2.get("total") or 0) <= 100:
                rows += d2.get("data") or []
                continue
            for c in countries:
                d3 = api.get("/api/v2/funding/tenders", limit=100, contract_nature=cn, buyer_country=c, **base)
                rows += d3.get("data") or []
                if (d3.get("total") or 0) > 100:
                    short.append(f"{start} {cn} {c} total {d3['total']}")
        return total, rows, short

    spans = [(today + dt.timedelta(days=k), today + dt.timedelta(days=k + 1)) for k in range(0, 150)]
    tail = today + dt.timedelta(days=150)
    spans += [(tail + dt.timedelta(days=7 * k), tail + dt.timedelta(days=7 * (k + 1))) for k in range(0, 40)]
    got: dict = {}
    total_sum = 0
    with ThreadPoolExecutor(6) as ex:
        for total, rows, short in ex.map(lambda s: window(*s), spans):
            total_sum += total
            for r in rows:
                got[r["id"]] = r
            notes += [f"TED slice still over 100 rows (truncated): {s}" for s in short]
    print(f"[INFO] TED: {len(got)} distinct notices with a deadline from {today} (sum of slice totals {total_sum})")
    return list(got.values()), notes


def harvest(api: Api, today: dt.date) -> dict:
    raw: dict = {}
    for p in FT_ENDPOINTS + AGENCY_ENDPOINTS:
        try:
            raw[p] = api.all_pages(p)
            print(f"[INFO] {p}: {len(raw[p])}")
        except Exception as e:
            raw[p] = []
            print(f"[ERROR] {p}: {type(e).__name__}")
    try:
        raw["/api/v2/funding/entrepreneur-instruments"] = api.all_pages("/api/v2/funding/entrepreneur-instruments", limit=50)
    except Exception as e:
        raw["/api/v2/funding/entrepreneur-instruments"] = []
        print(f"[ERROR] entrepreneur-instruments: {type(e).__name__}")
    try:
        raw["/api/v2/proprietary/tender-docs/templates"] = api.all_pages("/api/v2/proprietary/tender-docs/templates")
    except Exception:
        raw["/api/v2/proprietary/tender-docs/templates"] = []
    raw["ted"], raw["ted_notes"] = harvest_ted(api, today)
    # Publication-day ingest check (the 400-per-day cap) over the last 14 days.
    cap = {}
    for k in range(1, 15):
        day = today - dt.timedelta(days=k)
        try:
            d = api.get("/api/v2/funding/tenders", limit=1, published_from=day.isoformat(),
                        published_to=(day + dt.timedelta(days=1)).isoformat())
            cap[day.isoformat()] = d.get("total")
        except Exception:
            cap[day.isoformat()] = None
    raw["ted_daily_ingest"] = cap
    return raw


# --------------------------------------------------------------------------- #
# Normalisation
# --------------------------------------------------------------------------- #
PROGRAMME_PREFIXES = [
    ("HORIZON-JU-CHIPS", "Chips Joint Undertaking"), ("HORIZON-KDT", "Chips JU (KDT)"),
    ("HORIZON-EIC", "Horizon Europe: European Innovation Council"), ("HORIZON-EIT", "EIT (Horizon Europe)"),
    ("HORIZON-MSCA", "Horizon Europe: Marie Sklodowska-Curie Actions"), ("HORIZON-ERC", "European Research Council"),
    ("ERC", "European Research Council"),
    ("HORIZON-CL3", "Horizon Europe Cluster 3: Civil Security"),
    ("HORIZON-CL4-2026-SPACE", "Horizon Europe Cluster 4: Space"),
    ("HORIZON-CL4", "Horizon Europe Cluster 4: Digital, Industry and Space"),
    ("HORIZON-CL5", "Horizon Europe Cluster 5: Climate, Energy and Mobility"),
    ("HORIZON-CL6", "Horizon Europe Cluster 6: Food, Bioeconomy, Natural Resources and Environment"),
    ("HORIZON-CL2", "Horizon Europe Cluster 2: Culture, Creativity and Inclusive Society"),
    ("HORIZON-HLTH", "Horizon Europe Cluster 1: Health"), ("HORIZON-MISS", "Horizon Europe: EU Missions"),
    ("HORIZON-NEB", "Horizon Europe: New European Bauhaus"), ("HORIZON-WIDERA", "Horizon Europe: Widening and ERA"),
    ("HORIZON-CID", "Horizon Europe: Clean Industrial Deal"), ("HORIZON-JU-CBE", "Circular Bio-based Europe JU"),
    ("HORIZON-JU", "Horizon Europe Joint Undertaking"), ("HORIZON-EURATOM", "Euratom Research and Training"),
    ("HORIZON-INFRA", "Horizon Europe: Research Infrastructures"), ("HORIZON", "Horizon Europe"),
    ("LIFE", "LIFE Programme"), ("DIGITAL-ECCC", "Digital Europe (Cybersecurity Competence Centre)"),
    ("DIGITAL", "Digital Europe Programme"), ("CEF", "Connecting Europe Facility"),
    ("SMP", "Single Market Programme"), ("ERASMUS", "Erasmus+"), ("CREA", "Creative Europe"),
    ("ISF", "Internal Security Fund"), ("EDF", "European Defence Fund"), ("I3", "Interregional Innovation Investments"),
    ("CERV", "Citizens, Equality, Rights and Values"), ("JUST", "Justice Programme"),
    ("INNOVFUND", "Innovation Fund"), ("EU4H", "EU4Health"), ("AMIF", "Asylum, Migration and Integration Fund"),
    ("EMFAF", "European Maritime, Fisheries and Aquaculture Fund"), ("RFCS", "Research Fund for Coal and Steel"),
    ("AGRIP", "Promotion of agricultural products"), ("SOCPL", "Social Prerogatives"),
]


def programme_from_id(identifier: str) -> str:
    up = (identifier or "").upper()
    for pre, label in PROGRAMME_PREFIXES:
        if up.startswith(pre.upper()):
            return label
    return ""


def d10(value) -> dt.date | None:
    if not value:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(value))
    return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def first(meta: dict, key: str):
    v = meta.get(key)
    return v[0] if isinstance(v, list) and v else (v if not isinstance(v, list) else None)


def strip_html(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


FOREIGN_HINT = re.compile(
    r"(?i)\b(der|die|und|für|förderung|entwicklung|otwarta|skalowanie|och|för|nationella|plattformen|"
    r"kurzvorschlag|transformacja|meetmete|réamhluasaire|leathnú|apel|între|orașe|de la|des|pour|"
    r"virtuaalivaihto|itäisissä|intercambios|ontwerpmaatregelen|tegevustoetused|maisteriohjelmat|óige|"
    r"le chéile|becas|ψ|η)\b|[ąęłńśźżőűğşțșøåæ]")


def looks_non_english(title: str) -> bool:
    return bool(FOREIGN_HINT.search(title or "")) or bool(re.search(r"[Ͱ-ϿЀ-ӿ]", title or ""))


def budget_from_sedia(meta: dict, identifier: str) -> str:
    raw = first(meta, "budgetOverview")
    if raw:
        try:
            bo = json.loads(raw)
            total, mn, mx = 0.0, 0.0, 0.0
            for actions in (bo.get("budgetTopicActionMap") or {}).values():
                for a in actions:
                    if str(a.get("action", "")).startswith(identifier + " "):
                        total += sum(float(v or 0) for v in (a.get("budgetYearMap") or {}).values())
                        mn = max(mn, float(a.get("minContribution") or 0))
                        mx = max(mx, float(a.get("maxContribution") or 0))
            if total:
                s = f"EUR {total / 1e6:,.1f}m topic budget"
                if mx:
                    s += f"; EUR {mn / 1e6:,.1f}m to {mx / 1e6:,.1f}m per project" if mn else f"; up to EUR {mx / 1e6:,.1f}m per project"
                return s
        except Exception:
            pass
    val = first(meta, "cftEstimatedTotalProcedureValue")
    if val:
        m = re.match(r"([\d.]+)\s*(\w+)", str(val))
        if m and float(m.group(1)) > 0:
            return f"{m.group(2)} {float(m.group(1)) / 1e6:,.2f}m estimated value"
    return ""


def lead_authority(meta: dict) -> str:
    raw = first(meta, "cftLeadContractingAuthorityCode")
    if raw:
        try:
            return json.loads(raw)[0].get("name") or ""
        except Exception:
            pass
    return ""


def norm_ft(row: dict, source: str, meta: dict | None, today: dt.date, problems: Counter) -> dict | None:
    ident = row.get("topic_id") or row.get("tender_reference") or (row.get("public_url") or "").rstrip("/").split("/")[-1]
    is_tender = bool(row.get("tender_reference")) or re.search(r"-(CN|PIN|EXA)$", ident or "")
    api_title = (row.get("title") or "").strip()
    api_status = row.get("status")
    if meta is None:
        problems["F&T rows the portal search could not resolve (left out)"] += 1
        return None
    title = (first(meta, "title") or api_title).strip()
    if api_title and title and api_title != title and looks_non_english(api_title):
        problems["F&T titles served in a language other than English (English title taken from the portal)"] += 1
    sedia_status = SEDIA_STATUS.get(str(first(meta, "status")), "unknown")
    opening = d10(first(meta, "startDate")) or d10(row.get("published_at"))
    deadlines = sorted(d for d in (d10(x) for x in (meta.get("deadlineDate") or [])) if d)
    if not deadlines and row.get("deadline"):
        deadlines = [d10(row["deadline"])]
    nxt = [d for d in deadlines if d >= today]
    if sedia_status == "closed" or not nxt:
        if api_status in ("open", "forthcoming"):
            problems["API rows marked open/forthcoming that are closed or past deadline"] += 1
        return None
    status = "forthcoming" if (opening and opening > today) else "open"
    if api_status != status:
        problems["API status differs from the status derived from portal dates"] += 1
    if re.search(r"-(PIN)$", ident or ""):
        return None  # prior information notice, no deadline
    text = " ".join([title, strip_html(first(meta, "descriptionByte") or "")[:6000], row.get("description") or "",
                     " ".join(meta.get("tags") or []), " ".join(meta.get("keywords") or [])[:500],
                     first(meta, "callTitle") or "", " ".join(meta.get("typesOfAction") or []),
                     first(meta, "description") or "" if is_tender else ""])
    cpv = [str(c) for c in (meta.get("mainCpv") or [])]
    if is_tender:
        programme = "EU institutional procurement"
        action = "Call for tenders (service contract)"
        url = FT_TENDER + ident
        buyer = lead_authority(meta)
    else:
        programme = programme_from_id(ident) or (row.get("programme") if row.get("programme") and not re.match(r"\d{4} - \d{4}", str(row.get("programme"))) else "EU programme")
        action = (meta.get("typesOfAction") or [row.get("type_of_action") or ""])[0] or ""
        action = re.sub(r"\s+", " ", action).strip()
        if first(meta, "type") == "8":
            action = action or "Cascade funding (third-party open call)"
        meta_url = re.sub(r"\.json$", "", str(first(meta, "url") or ""))
        url = meta_url if meta_url.startswith("https://ec.europa.eu/") else FT_TOPIC + ident
        buyer = ""
    return dict(uid="ft:" + ident, ident=ident, source="EU Funding & Tenders portal" + (" (tender)" if is_tender else ""),
                kind="tender" if is_tender else "grant", title=title, title_note="", url=url, programme=programme,
                action=action, opens=opening, deadline=nxt[0], all_deadlines=deadlines, status=status,
                budget=budget_from_sedia(meta, ident), text=text, cpv=cpv, country="EU", buyer=buyer,
                via=source)


AGENCY_NAMES = {"efca": "EFCA", "cedefop": "Cedefop", "euaa": "EUAA", "eurojust": "Eurojust", "echa": "ECHA",
                "eeas": "EEAS", "era": "ERA", "enisa": "ENISA", "ecdc": "ECDC", "hadea": "HaDEA", "efsa": "EFSA",
                "euda": "EUDA", "etf": "ETF", "ema": "EMA", "eib": "EIB", "eu_osha": "EU-OSHA", "eismea": "EISMEA",
                "eccc": "ECCC", "innovfund": "Innovation Fund", "just": "Justice Programme"}


def fetch_page_deadline(url: str) -> dt.date | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        page = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "ignore")
    except Exception:
        return None
    txt = strip_html(page)
    months = "january|february|march|april|may|june|july|august|september|october|november|december"
    found = []
    for m in re.finditer(r"(?i)(deadline|closing date|submission)[^.]{0,80}?(\d{1,2})\s+(" + months + r")\s+(20\d\d)", txt):
        try:
            found.append(dt.datetime.strptime(f"{m.group(2)} {m.group(3)} {m.group(4)}", "%d %B %Y").date())
        except ValueError:
            pass
    for m in re.finditer(r"(?i)(deadline|closing date)[^.]{0,40}?(\d{1,2})[./](\d{1,2})[./](20\d\d)", txt):
        try:
            found.append(dt.date(int(m.group(4)), int(m.group(3)), int(m.group(2))))
        except ValueError:
            pass
    return max(found) if found else None


def norm_agency(row: dict, today: dt.date, problems: Counter, ft_idents: set) -> dict | None:
    if row.get("item_type") in EXCLUDED_ALL_TYPES:
        return None
    url = row.get("public_url") or ""
    last = url.rstrip("/").split("/")[-1]
    if ("topic-details/" in url or "tender-details/" in url) and last in ft_idents:
        return None  # already handled from the portal
    body = row.get("body_code") or ""
    summary = row.get("summary") or ""
    item_type = row.get("item_type") or ""
    deadline = None
    m = re.search(r"(20\d\d-\d\d-\d\d)\s*$", summary)
    if m:
        deadline = d10(m.group(1))
    elif item_type == "tender" and body in ("hadea", "eeas"):
        deadline = d10(row.get("document_date"))  # these folders store the deadline here
    elif item_type == "call":
        pub = d10(row.get("document_date"))
        if pub and (today - pub).days < 400:
            deadline = fetch_page_deadline(url)
            if deadline is None:
                problems["Agency call pages with no machine-readable deadline (left out)"] += 1
        else:
            return None
    if re.search(r"(?i)closed|awarded|cancel", summary):
        return None
    if not deadline:
        if item_type in ("tender", "eoi_call"):
            problems["Agency tenders with no deadline in the API (left out)"] += 1
        return None
    if deadline < today:
        return None
    title = (row.get("title") or "").strip()
    note = ""
    if looks_non_english(title):
        note = "Title as published by the agency (not in English)."
        problems["Agency titles not in English (kept, marked)"] += 1
    agency = AGENCY_NAMES.get(body, body.upper())
    kind = {"eoi_call": "expert_list", "call": "grant"}.get(item_type, "tender")
    action = {"expert_list": "Call for expression of interest (list of external experts)",
              "grant": "Call for proposals", "tender": "Call for tenders"}[kind]
    return dict(uid=f"ag:{body}:{row.get('id')}", ident=str(row.get("id")), source=f"EU agency: {agency}", kind=kind,
                title=title, title_note=note, url=url, programme=f"{agency} procurement" if kind != "grant" else agency,
                action=action, opens=None, deadline=deadline, all_deadlines=[deadline], status="open", budget="",
                text=" ".join([title, summary, row.get("body_txt") or ""]), cpv=[], country="EU", buyer=agency, via=body)


def norm_ted(row: dict, today: dt.date) -> dict | None:
    deadline = d10(row.get("submission_deadline"))
    if not deadline or deadline < today:
        return None
    full = row.get("title") or ""
    parts = full.split(" – ", 2)
    if len(parts) == 3:
        cpv_label, original = parts[1], parts[2]
    else:
        cpv_label, original = "", full
    note = "" if not looks_non_english(original) and re.match(r"^[\x00-\x7f]*$", original) else "Title in the language of the notice."
    pub = row.get("publication_number") or ""
    val = row.get("estimated_value")
    budget = f"{row.get('estimated_value_currency') or 'EUR'} {float(val) / 1e6:,.2f}m estimated" if val else ""
    eu = bool(EU_BUYER.search(row.get("official_name") or ""))
    return dict(uid="ted:" + pub, ident=pub, source="TED (Official Journal S series)", kind="ted",
                title=original.strip(), title_note=note, cpv_label=cpv_label, url=f"https://ted.europa.eu/en/notice/-/detail/{pub}",
                programme="EU institutional procurement (TED)" if eu else f"National public procurement ({COUNTRY.get(row.get('buyer_country'), row.get('buyer_country') or '?')})", action=f"Call for tenders: {cpv_label}" if cpv_label else "Call for tenders",
                opens=d10(row.get("publication_date")), deadline=deadline, all_deadlines=[deadline], status="open",
                budget=budget, text=" ".join([full, row.get("official_name") or ""]),
                cpv=[str(c) for c in (row.get("cpv_codes") or [])], country=row.get("buyer_country") or "",
                buyer=row.get("official_name") or "", via="ted")


# --------------------------------------------------------------------------- #
# Profiles and matching rules
# --------------------------------------------------------------------------- #
def R(key, weight, pattern=None, cpv=(), prefix=(), why="", ted=False, cap=None, role=None, core=True):
    return dict(key=key, weight=weight, rx=re.compile(pattern, re.I) if pattern else None, cpv=tuple(cpv),
                prefix=tuple(p.upper() for p in prefix), why=why, ted=ted, cap=cap, role=role, core=core)


COUNTRY = {"ES": "Spain", "FR": "France", "DE": "Germany", "IT": "Italy", "PT": "Portugal", "BE": "Belgium",
           "NL": "the Netherlands", "PL": "Poland", "MT": "Malta", "IE": "Ireland", "LU": "Luxembourg", "SE": "Sweden",
           "DK": "Denmark", "AT": "Austria", "CZ": "Czechia", "RO": "Romania", "GR": "Greece", "FI": "Finland",
           "HU": "Hungary", "SI": "Slovenia", "SK": "Slovakia", "HR": "Croatia", "BG": "Bulgaria", "LT": "Lithuania",
           "LV": "Latvia", "EE": "Estonia", "CY": "Cyprus", "NO": "Norway", "CH": "Switzerland"}

EU_BUYER = re.compile(r"(?i)european (commission|environment agency|chemicals agency|union|parliament|high.performance computing|investment bank)|\bDG [A-Z]+|joint undertaking|expertise france")

PROFILES = [
    dict(
        slug="terraqui", name="Terraqui",
        legal="Estudi Jurídic Ambiental, S.L.P. (trading as Terraqui), a Spanish professional law firm",
        site="https://www.terraqui.com/ca/",
        profile=[
            "Barcelona environmental-law firm (Diagonal 527) founded in 1996 by Christian Morron Lingl. It advises companies and public administrations on environmental management, represents clients in administrative and judicial proceedings, helps draft environmental legislation, and designs tailored training.",
            "Practice areas listed on its site: climate change and energy transition; biodiversity and ecosystems; water; circular economy and waste; sustainable activities; sustainable consumption and products (ecodesign, green claims, REACH/CLP, food-contact materials, extended producer responsibility); spatial planning; pollution and environmental liability. Its service pages expressly include legal support to identify and obtain grants, and drafting environmental clauses for public tenders.",
            "Live EU project: regulatory and policy partner in LIFE DPP-TEX (2026-2028, 8 partners from Spain, Bulgaria and the Netherlands, coordinated by Blue Room Innovation), setting the legal foundations of a textile digital product passport and running regulatory surveillance of ESPR delegated acts, textile EPR and standardisation. Its lawyer Joana Castella uses Brubru's DPP tools.",
        ],
        eligibility=[
            "A Spanish legal entity: eligible in its own right in LIFE, Horizon Europe, Digital Europe, Single Market Programme and Spanish or EU public procurement.",
            "Small team: the realistic role in large Horizon Innovation or Research actions is partner leading a legal, regulatory, standards or policy work package, not coordinator. LIFE governance projects and Coordination and Support Actions are the most natural fit for a lead role.",
            "Legal-services tenders outside Spain usually require local bar admission and the procurement language; treat them as consortium or subcontracting routes.",
        ],
        rules=[
            R("dpp", 5, r"digital product passport|product passport|\bdpp\b|ecodesign|eco-design|\bespr\b|energy labelling|product lifecycle|repair and refurbish", why="Ecodesign and product-information rules (ESPR, energy labelling, the digital product passport, repairability) are the regime Terraqui already covers as regulatory partner in LIFE DPP-TEX."),
            R("textile", 5, r"textile|textil|footwear|apparel", why="Textile circularity is the sector of LIFE DPP-TEX, where Terraqui sets the legal foundations and tracks textile EPR schemes and ESPR delegated acts."),
            R("circular", 3, r"circular economy|circularity|\bwaste\b|recycl|re-?use\b|repair|extended producer responsibility|\bepr\b|packaging|end-of-waste|by-product|residu|reciclaj|economía circular|economia circular|déchets|abfall", why="Circular economy and waste law (EPR, packaging, end-of-waste, waste shipments) is one of Terraqui's core practice areas."),
            R("legal", 2.5, r"legislat|regulat|\bpolicy\b|policies|governance|compliance|enforcement|implementation of|legal|juridic|jurídic|juridique|rechtlich|normativ|permitting|standardi[sz]|market surveillance|green claims|labelling|labeling|environmental impact assessment|impacto ambiental", why="The work calls for legal and regulatory analysis, compliance support or policy implementation, which is the service Terraqui sells."),
            R("chem", 1.5, r"\breach\b|chemical|hazardous substance|\bpfas\b|safe and sustainable by design|\bssbd\b|food contact|fertilis|biocid|pesticid|toxic-free", why="Terraqui advises on chemicals rules (REACH, CLP), food-contact materials and fertilisers."),
            R("climate", 1.5, r"climate|adaptation|mitigation|energy transition|renewable|energy communit|heating and cooling|emission|clean energy", why="Climate change and energy-transition law is a listed Terraqui practice area."),
            R("nature", 1.5, r"biodiversity|nature|habitat|natura 2000|protected area|\bwater\b|aquifer|groundwater|\bsoil\b|pollution|zero pollution|contaminat|wildlife", why="Biodiversity, water, soil and pollution law are listed Terraqui practice areas."),
            R("planning", 1, r"urban planning|spatial planning|land use|ordenación del territorio|urbanis|strategic environmental", why="Spatial planning and urban-planning law is a Terraqui practice area."),
            R("cpv_legal", 4.5, cpv=("791",), why="It is a legal-services contract.", ted=True),
            R("cpv_envconsult", 2.5, cpv=("90713", "90712", "71313", "90711"), why="It is an environmental advisory contract where permitting and regulatory knowledge is part of the job.", ted=True),
            R("cpv_consult", 1, cpv=("79411", "79419", "7322", "73200"), ted=True),
            R("ted_kw", 3, r"jur[ií]dic|juridique|legal advi|asesoramiento|assessorament|consultor[ií]a|residuos|economía circular|impacto ambiental|circular economy|waste management|environmental|ambiental|wildlife trade|déchets", ted=True),
            R("ted_eia", 2, r"impacto ambiental|environmental impact|évaluation environnementale|avaluació ambiental", why="Environmental impact assessment is a permitting procedure where Terraqui's environmental-law and planning experience applies directly.", ted=True),
            R("ted_waste", 2, r"residuos|waste|déchets|residus", why="Municipal waste services and their concession contracts are governed by the waste and circular-economy rules Terraqui advises on, including EPR and public-procurement environmental clauses.", ted=True),
            R("ted_eu", 2, r"wildlife trade|implementation and enforcement|legislation|regulation", why="The Commission is buying support on how EU environmental legislation is implemented and enforced, which is legal and policy analysis.", ted=True),
        ],
        negative=re.compile(r"(?i)nuclear|cancer|clinical|palliative|drone|military|defence|border surveillance|terror|spaceport|isotope|livestock|microbiome|biorefiner|thermoset|battery-grade|wind energy|space data|cryptograph|limpieza|cleaning|legionel|recogida de|transporte y gesti|mantenimiento|maintenance|suministro|laborator|analyses? des eaux|análisis|monitoring network|explotación|restauración de hábitats|obras|works\b|réhabilitation du site|sanitation|security services|vigilancia|campaign|kampaania|homeless|capital market|law enforcement|police|crime|camión|camion|contenedor|puntos limpios|recogida|transporte de residuos|vehículo|vehicul|dirección facultativa|dirección de obra|proyecto básico|web|eduki|tax|fiscal|dpo\b|data protection|building application|health services|ehds|cultural heritage|public transport|fishers|inland waterways|isotope|africa|arctic|seafood|it rooms|harbours|agricultur|nutrient|social cohesion|e-mobility|ukraine|turisme|turismo|marketing|movilidad"),
        ted_require=re.compile(r"(?i)consultor|asesor|assessor|asistencia técnica|assistència tècnica|jur[ií]dic|juridique|legal|estudio|estudi|study|diagnostic|roadmap|support to|dictamen|informe|expertise|conseil|accompagnement|advis|impacto ambiental|pilotage|review|revisión|évaluation|evaluation"),
        home_theme=re.compile(r"(?i)waste|circular|déchets|residu|environment|wildlife|biodivers|ecodesign|textile|chemical|pollution|climate|ambient|impacto ambiental|jur[ií]dic|juridique|legal|faune|flore|habitats|energy communit"),
        foreign_theme=re.compile(r"(?i)waste|circular|déchets|residu|environment|wildlife|biodivers|ecodesign|textile|chemical|pollution|climate|ambient|faune|flore|habitats|energy communit"),
        exclude_cpv=("0", "1", "2", "3", "4", "5", "6"),
        tech_penalty=re.compile(r"(?i)fibres|fibers|polymer|thermoset|coating|additive|biotech|biomass|biorefiner|chemicals|processing|manufacturing|materials|technolog|ingredient|remanufactur|process industr|data platform|digital twin|decision support|sampl|ukraine|mapping|demonstration|bio-based"),
        exclude_prefix=("EDF",),
        ted_high_keys=("cpv_legal", "cpv_envconsult", "ted_eu"),
        ted_country_bonus={"ES": 2.5, "AD": 0.5, "PT": 0.5},
        ted_foreign_malus=-2.5,
        prog_bonus={"LIFE": 1.5, "HORIZON-CL6": 0.5, "HORIZON-MISS": 0.5, "HORIZON-CL4-2027-01-MAT-PROD": 0.5, "SMP": 0.5},
    ),
    dict(
        slug="gbsb", name="GBSB Global Business School",
        legal="Global Business School Barcelona SLU (Spain, B65687121) and GBSB Global Business School Limited (Malta, C 91738); website controller Ivaen Education Ltd (Cyprus)",
        site="https://www.global-business-school.org/",
        profile=[
            "Private international business school founded in Barcelona (origins in 2005) with campuses in Barcelona, Madrid and Malta plus an online campus. Programmes run from Foundation and Bachelor to Masters, MBA and a PhD in Innovation Management, all taught in English, centred on digital transformation, sustainability, ethics and entrepreneurial leadership.",
            "Recognised as a foreign university centre in Catalonia (RUCT 08073661) and Madrid, licensed as a higher education institution in Malta (MFHEA 2020-12), accredited by ACBSP and ASIC, a Microsoft Showcase School. It holds the Erasmus Charter for Higher Education and runs student and staff mobility with partners in several countries. A Research Centre in Barcelona is building a research-active profile (innovation, management, finance, sustainability, digital transformation).",
            "Its Entrepreneurship Center runs the G-Accelerator Impact Call, a 6-month pre-accelerator (230 hours of training, 240 of mentoring) funded by the Generalitat de Catalunya and co-funded by the European Social Fund Plus, run with UVic-UCC and the University of Northampton, and leads Impuls AgriTech with IRTA (12 projects and 23 beneficiaries in 2026).",
        ],
        eligibility=[
            "Both the Spanish SLU and the Maltese Ltd are EU legal entities eligible in Erasmus+, Horizon Europe, Digital Europe, EIT and Single Market Programme calls. Check which entity holds the Participant Identification Code and the Erasmus Charter before applying; the Swiss GmbH entities are not the vehicle for EU grants.",
            "As a private higher education institution GBSB counts as a university or research organisation in most work programmes; it will usually be a partner in consortia led by public universities, innovation agencies or ecosystem builders.",
            "Malta is a Widening country under Horizon Europe, which can matter for Widening and EIC pre-accelerator topics; confirm the rules for the specific topic.",
        ],
        rules=[
            R("venture", 4, r"entrepreneur|start-?ups?\b|scale-?ups?\b|accelerat(or|ion)|incubat|pre-accelerat|emprend|aceler|incubad|\bventure|spin-?offs?|spin-?outs?|business model|proof of market|commerciali[sz]|valori[sz]ation|technology transfer|lab to market|intellectual assets", why="GBSB runs the G-Accelerator pre-accelerator and leads Impuls AgriTech, so startup support, mentoring and venture building are proven capabilities."),
            R("mentoring", 4, r"mentor|coaching|empoderamiento|empowerment|accompagnement à la création|création d.activit", why="Structured mentoring and coaching programmes are what GBSB's G-Accelerator delivers (230 hours of training and 240 of mentoring per cohort)."),
            R("talent", 3, r"talent|atracción de talento|capacidades|competencial|leadership|chefer|ledningsgrupp|management training", why="Talent attraction, leadership and competence development are the subject of GBSB's executive education and business programmes."),
            R("skills", 3, r"\bskills\b|upskilling|reskilling|training|education|curricul|higher education|universit|doctoral|\bphd\b|master|micro-credential|learning|edtech|teaching|academ|formación|formació|competenc", why="It is an education and skills action; GBSB is an accredited higher education institution delivering programmes from bachelor to PhD, executive education and short courses."),
            R("digital", 2, r"\bdigital\b|artificial intelligence|\bai\b|\bdata\b|edtech|digital transformation", why="GBSB's curriculum centres on digital transformation and AI in business, and it is a Microsoft Showcase School.", core=False),
            R("business", 2, r"\bbusiness|management|leadership|\bsmes?\b|pyme|innovation management|\bfinance|investment|capital market|market uptake|mentoring|mentoría|mentoria|talent", why="Management, finance and innovation-management teaching and research are GBSB's home ground.", core=False),
            R("impact", 1, r"sustainab|social economy|social innovation|impact|circular|agri-?food|agritech|women|inclusion|gender", why="GBSB's accelerator verticals include sustainable business, circular economy, agri-food and inclusion.", core=False),
            R("cpv_edu", 3, cpv=("805", "804", "80532", "80000000"), why="It is a training services contract.", ted=True),
            R("cpv_bizdev", 2, cpv=("79411100", "79414", "7322"), why="It is a business development and advisory services contract.", ted=True),
            R("ted_kw", 3, r"emprend|empren|aceler|incubad|mentor|entrepreneur|startup|start-up|atracción de talento|talent|leadership|management training|business school|capacitaci|chefer|création d.activit", ted=True),
        ],
        negative=re.compile(r"(?i)nuclear|euratom|cancer|clinical|palliative|drone|military|defence|border|terror|spaceport|space critical|biorefiner|fertilis|aquifer|insect|marine|deep sea|wind energy|reactor|battery|livestock|microbiome|thermoset|polymer|chemical|raw material|irradiation|soil|renovation|heating|buildings?\b|homeless|disaster|limpieza|cleaning|vigilancia|mantenimiento|maintenance|suministro|music|músic|nuclear|simulación|simulator|security services|cajeros|videolaringoscop|ocean|textile|process industries|bio-based|biomass|critical infrastructure|travel facilitation|missing persons|law enforcement|criminal|investigations|standardisation|climate|neighbourhood|vacant|public transport|pollution|artists|safer internet|screening|agriculture of data|planer|integrationsmanagement|opstart|envejecimiento|uptake in health|fusion|quantum|protein|forest|fisheries|arctic|vessels|seafood|invasive|foodome|biodiversity|blue forest|cybersecur|fuel|telco|robotics|remote sensing|ccam|carbon farming|mobility|civitas|energy sector|security|migration|african union|deeprap|cognitive ai|ncc network|coastal|tourism|artistic|media viability|disabilities|logistics|bioeconomy|pilot plants|living labs|nutrition|agriculture|pre-primary|ccsi|cultural and creative content|ai4creatives|albania|research management facility|eosc|déchets|mâchefer|waste|upscaling|operational validation|diseases|children|frontier ai|prize|award|women leadership|women innovators|cofund|choose europe|farmer|government in transition|cultural policies|advanced materials|re-manufacturing|energy input|materials"),
        ted_require=re.compile(r"(?i)emprend|empren|aceler|incubad|mentor|entrepreneur|startup|start-up|talent|leadership|management training|business school|capacitaci|formación|formació|training|création d.activit|chefer|ledningsgrupp|competenc"),
        foreign_theme=re.compile(r"(?i)entrepreneur|emprend|création d.activit|startup|leadership|management|chefer|ledning|business|mentor|talent|formación|formació|training"),
        exclude_prefix=("EDF", "HORIZON-EURATOM", "HORIZON-CL3", "HORIZON-HLTH"),
        ted_high_keys=("cpv_edu", "cpv_bizdev"),
        exclude_cpv=("0", "1", "2", "3", "4", "5", "6"),
        ted_country_bonus={"ES": 2.5, "MT": 2.5},
        ted_foreign_malus=-3,
        prog_bonus={"ERASMUS": 3, "DIGITAL-2026-SKILLS": 3, "DIGITAL": 0.5, "HORIZON-MSCA": 2, "HORIZON-EIT": 2, "HORIZON-WIDERA": 1, "HORIZON-CL4-2027-01-MAT-PROD-4": 1, "SMP": 1},
    ),
    dict(
        slug="cadence", name="Cadence",
        legal="Cadence Design Systems, Inc. (Nasdaq: CDNS, San Jose, California); international headquarters Cadence Design Systems, Ireland (Dublin), with offices in most EU Member States",
        site="https://www.cadence.com/",
        profile=[
            "Computational software company: electronic design automation for custom, analogue and digital chips, verification and emulation, IC package and PCB design, semiconductor IP (including Tensilica processors, AI IP and chiplets), and custom silicon services. 2025 revenue USD 5.29bn, 13,000+ employees, 70+ offices.",
            "Beyond chips it sells system analysis and simulation: computational fluid dynamics (Fidelity, and the Millennium M2000 supercomputer for AI-accelerated simulation), thermal, electromagnetic and signal-integrity solvers, the Reality digital twin platform, BETA CAE Systems and MSC Software for structural and multiphysics CAE, and molecular simulation for life sciences. Target markets on its site: hyperscale and data centres, AI, mobile and 5G, automotive (ISO 26262 certified flows), aerospace and defence, industrial, life sciences, robotics and physical AI.",
            "Cloud (source: cadence.com/en_US/home/solutions/cadence-oncloud.html, read 23 Sep 2026): Cadence OnCloud is a turnkey three-layer stack, accelerated compute on a multi-cloud platform, SaaS design and analysis tools front-end to back-end, for hybrid or all-cloud use, with an online marketplace. Offers: Cadence-managed Cloud Service (a full front-to-back chip design flow as SaaS), Cadence-managed Palladium and Protium Cloud (emulation and prototyping on leased capacity), and customer-managed Cloud Passport (Cadence software and a cloud licence server on the customer's own AWS, Azure, Google Cloud or IBM Cloud). Hybrid-cloud products include Pegasus TrueCloud on AWS and Spectre X on Azure; universities use OnCloud for teaching. The Reality Digital Twin is a data-centre design and management platform.",
            "The Cadence Academic Network supplies tools and training to 1,500+ universities, which makes Cadence a credible industrial partner for doctoral networks and advanced-skills actions. Its contact page lists offices in Austria, Belgium, Czechia, Denmark, Estonia, Finland, France, Germany, Greece, Hungary, Ireland, Italy, Latvia, Luxembourg, the Netherlands, Poland, Portugal, Slovakia, Spain and Sweden.",
        ],
        eligibility=[
            "The parent is a US company. Its EU subsidiaries (for example the Dublin international headquarters) are EU legal entities and can participate in most Horizon Europe topics, but they are controlled from a country not associated to Horizon Europe: topics restricted under Article 22(5) of the Horizon Europe Regulation (strategic autonomy, notably space, quantum and some digital and semiconductor topics) can exclude them or require security guarantees.",
            "European Defence Fund: entities controlled by non-associated third countries are ineligible unless the Member State where they are established provides guarantees approved under the EDF Regulation; assume exclusion unless that is secured.",
            "Digital Europe: several actions in high-performance computing, AI, cybersecurity and advanced skills carry Article 12(5)/(6) restrictions on third-country control. Chips JU calls can carry similar conditions. Where restrictions apply the realistic route is as a subcontracted tool, IP or services supplier, or as an associated partner without EU funding (MSCA Doctoral Networks accept associated partners from anywhere).",
            "Public procurement: the US is a party to the WTO Government Procurement Agreement, so Cadence can bid for covered EU public software and services contracts directly or through channel partners.",
        ],
        rules=[
            R("chips", 5, r"semiconductor|\bchips?\b|integrated circuit|\basic\b|\bfpga|system-on-chip|\bsoc\b|chiplet|\beda\b|electronic design|microelectronic|nanoelectronic|\bmmic|\bgan\b|eee component|processor|risc-v|photonic|3d integration|heterogeneous integration|halbleiter|mikroelektr|electronic components", why="The topic needs chip, microelectronics or electronic-component design, which is Cadence's core business (EDA flows, semiconductor IP, 3D-IC and chiplet design)."),
            # Cloud vertical (23 Sep 2026, Victor: a meeting with Cadence's cloud
            # team). Cadence sells its design and simulation software as cloud
            # services and designs the chips and data-centre systems clouds run
            # on, so cloud-edge, sovereign-cloud and design-platform calls fit.
            R("cloud", 3.5, r"\bcloud\b|cloud.edge|cloud-to-edge|edge computing|computing continuum|meta-?os\b|\bsaas\b|software as a service|platform as a service|\bpaas\b|sovereign cloud|cloud infrastructure|cloud service|multi-cloud|hybrid cloud|cloud.native|serverless|kubernetes|containeri[sz]|virtuali[sz]ation|ipcei.cis|\bsimpl\b|\b8ra\b|federated (compute|infrastructure)|design platform|virtual design|cloud-based design|emulation (platform|as a service)|hardware emulation|data cent(re|er) (design|efficiency|energy|infrastructure)|federated|decentrali[sz]ed.{0,40}data processing|ai data processing|\\bit rooms?\\b|server rooms?|waste heat recovery", why="The topic concerns cloud infrastructure, cloud services or the cloud-edge continuum. Cadence runs chip design, verification and simulation as cloud services: Cadence OnCloud (SaaS on a multi-cloud base, hybrid or all-cloud), a Cadence-managed front-to-back design cloud, Palladium and Protium emulation in the cloud, and Cloud Passport on AWS, Azure, Google Cloud or IBM Cloud; its Reality Digital Twin designs and manages data centres."),
            R("ai_infra", 1.5, r"gigafactor|ai factor", why="Building an AI factory or gigafactory is a data-centre and AI-system design job: Cadence's Reality Digital Twin designs and manages data centres, and its tools design the AI chips and systems inside them.", cap="Medium", role="technology partner to a bidding consortium (data-centre design and simulation, AI system design)"),
            R("hwsec", 3.5, r"security in software and hardware|hardware security|secure hardware|cryptographic implementation|high-assurance|side-channel|root of trust", why="Secure hardware design and high-assurance implementation depend on design and verification flows of the kind Cadence supplies."),
            R("simulation", 3, r"simulation|simulat|digital twin|multiphysics|multi-physics|computational fluid|\bcfd\b|\bcae\b|virtual prototyp|thermal analysis|electromagnetic|signal integrity|modelling platform|in silico|virtual human twin", why="The work relies on simulation, digital twins or multiphysics analysis, matching Cadence's system-analysis portfolio (CFD, thermal and electromagnetic solvers, BETA CAE and MSC Software, the Reality digital twin platform)."),
            R("compute", 2.5, r"high.performance computing|\bhpc\b|supercomput|ai factor|gigafactor|data cent|datacent|edge ai|energy-efficient computing|neuromorphic|ai hardware", why="It concerns AI and high-performance compute infrastructure, where Cadence designs AI chips and data-centre systems and sells the Millennium supercomputing platform."),
            R("sectors", 1.5, r"automotive|software-defined vehicle|avionics|aerospace|\bspace\b|satellite|defen[cs]e|military|radar|drones?|robot|autonomous|embodied|physical ai|5g|6g|telecommunication", why="Cadence serves automotive, aerospace, defence and telecoms electronics, including functional-safety certified flows.", core=False),
            R("academic", 3, r"doctoral network|msca|advanced digital skills|chip design skills|competence centre|joint doctorate", why="Through the Cadence Academic Network Cadence can contribute tools, training and industrial secondments."),
            R("cpv_cad", 5, cpv=("48321", "48322", "48323", "48329"), why="It is a procurement of computer-aided design and engineering software, Cadence's product category.", ted=True),
            R("cpv_sci", 2, cpv=("48460", "48461", "48462", "48463"), why="It is a procurement of analytical or scientific software, where Cadence's simulation tools compete.", ted=True),
            R("cpv_super", 2.5, cpv=("30211",), why="It is a supercomputer procurement; Cadence does not supply general-purpose HPC systems, but its Millennium platform and simulation software make it a possible technology partner to the bidding system integrator.", ted=True, cap="Medium", role="technology partner or software supplier to the bidding system integrator"),
            R("ted_kw", 3, r"platforma do modelowania|\bcad\b|\beda\b|fpga|asic|chip design|semiconductor|halbleiter|simulation software|simulationssoftware|\bcfd\b|supercomputer|digital twin|modelowania|electronic design|pcb design|leiterplatten", ted=True),
            R("ted_cae", 2, r"modelowania cae|\bcae\b.*(wibro|vibro|struct|dynam|modal)|wibroakust|vibroacoust|structural dynamic|\bmodal\b|modalnych", why="Structural dynamics, vibro-acoustics and modal analysis are the domain of Cadence's CAE tools (BETA CAE pre- and post-processing and MSC Software solvers).", ted=True),
        ],
        negative=re.compile(r"(?i)microsoft|oracle|\bsap\b|\berp\b|accounting|payroll|firewall|antivirus|records management|spisové|website|nuclear power|isotope|cancer patients|palliative|survivors|refractory|clinical trial|border surveillance|biorefiner|fertilis|insect|\bsoil\b|housing|homeless|travel facilitation|missing persons|addiction|age assessment|corruption|quantum computer|mixed reality|air.traffic control|driving|körkort|planetarium|laborator|cleaning|limpieza|renovation|biodivers|livestock|marine|textile|food|in health|citizens|cofund|choose europe|postdoctoral|déplacements|transport de marchandises|traffic|impact monitoring|assessment framework"),
        exclude_cpv=("3171", "3172", "31712"),
        ted_exclude=re.compile(r"(?i)phishing|security awareness|movpe|mocvd|epitax|reaktor|reactor|deposition|lithograph|sputter|anlage f(ü|u)r|clean ?room|reinraum"),
        ted_high_keys=("cpv_cad", "cpv_sci"),
        ted_country_bonus={},
        ted_foreign_malus=0,
        prog_bonus={"HORIZON-JU-CHIPS": 3, "DIGITAL-JU-CHIPS": 3, "HORIZON-KDT": 3, "HORIZON-CL4": 1, "HORIZON-MSCA": 2.5, "EDF": 0.5, "DIGITAL": 0.5, "HORIZON-CL3-2026-02-CS": 1},
    ),
]

THRESHOLDS = [("High", 8.0), ("Medium", 5.5), ("Stretch", 4.0)]


def role_for(org: str, opp: dict, strength: str) -> str:
    kind, action, ident = opp["kind"], (opp["action"] or "").lower(), opp["ident"].upper()
    home = opp.get("country") in ({"terraqui": {"ES"}, "gbsb": {"ES", "MT"}, "cadence": set()}[org])
    if kind == "expert_list":
        return "individual specialists from the organisation registering as external experts"
    if kind == "ted" and EU_BUYER.search(opp.get("buyer") or ""):
        kind = "tender"
    if kind == "ted":
        if org == "cadence":
            return "software vendor bidding directly or through a channel partner"
        return "tenderer in its own name" if home else "subcontractor to, or consortium member with, a local bidder"
    if kind == "tender":
        return {"terraqui": "consortium member or subcontractor delivering the legal and regulatory analysis",
                "gbsb": "consortium member delivering training, entrepreneurship or skills components",
                "cadence": "subcontractor or consortium member supplying tools and technical expertise"}[org]
    if "cascade" in action or ident.startswith("HORIZON-EIT"):
        return {"gbsb": "beneficiary of cascade funding or delivery partner for the programme",
                "terraqui": "beneficiary of cascade funding or service provider to selected projects",
                "cadence": "technology partner to applicants"}[org]
    if org == "terraqui":
        if "coordination and support" in action or ident.startswith(("LIFE-2026-PLP", "LIFE-2026-SAP-ENV-GOV", "LIFE-2026-SAP-CLIMA-GOV", "LIFE-2026-SAP-NAT-GOV")):
            return "partner leading the policy and legal analysis; coordinator of a small governance proposal is possible"
        if ident.startswith("LIFE"):
            return "partner owning the regulatory work package, as in LIFE DPP-TEX"
        return "partner for regulatory analysis, standards mapping and legal barriers to exploitation"
    if org == "gbsb":
        if ident.startswith("HORIZON-MSCA"):
            return "beneficiary or associated partner hosting doctoral candidates in innovation management"
        if "coordination and support" in action:
            return "partner delivering the entrepreneurship, skills or training activities"
        return "partner for training, business modelling, exploitation and market-uptake work"
    if ident.startswith("HORIZON-MSCA"):
        return "associated partner offering industrial secondments and tool access (no eligibility restriction for associated partners)"
    if ident.startswith(("EDF", "HORIZON-CL4-2026-SPACE")):
        return "tool and IP supplier to eligible European participants, subject to the control restrictions below"
    return "industrial partner through an EU subsidiary, or tool and IP supplier to the consortium"


def caveats_for(org: str, opp: dict) -> list[str]:
    ident, kind, out = opp["ident"].upper(), opp["kind"], []
    if kind == "ted":
        if org != "cadence" and opp["country"] not in ({"terraqui": {"ES"}, "gbsb": {"ES", "MT"}}[org]):
            out.append(f"Foreign tender ({COUNTRY.get(opp['country'], opp['country'])}): procurement language and local qualification rules apply.")
        out.append("Check the selection criteria (turnover, insurance, references) in the tender documents.")
        if opp.get("title_note"):
            out.append("Only a short title is published in Brubru's TED feed; read the notice before committing.")
    if kind == "tender":
        out.append("EU service contracts usually go to consultancy consortia; check exclusion and selection criteria.")
    if kind == "expert_list":
        out.append("Registration is individual, not corporate; contracts are awarded to named experts.")
    if org == "cadence":
        if ident.startswith(("HORIZON-CL4-2026-SPACE", "HORIZON-CL3")):
            out.append("Likely restricted to entities not controlled from non-associated countries (Article 22(5)); check the topic conditions.")
        elif ident.startswith("EDF"):
            out.append("EDF excludes entities controlled from non-associated third countries unless guarantees are approved.")
        elif ident.startswith("DIGITAL"):
            out.append("Check Article 12(5)/(6) restrictions on third-country control for this Digital Europe topic.")
        elif ident.startswith("HORIZON") and "MSCA" not in ident:
            out.append("Participate through an EU subsidiary; confirm the topic carries no Article 22(5) restriction.")
    if org == "terraqui" and ident.startswith("HORIZON") and "coordination and support" not in (opp["action"] or "").lower():
        out.append("Needs a technology-led consortium; Terraqui joins, it does not build the proposal alone.")
    if org == "gbsb" and ident.startswith("HORIZON") and not ident.startswith("HORIZON-MSCA"):
        out.append("A consortium with research or industry partners is required; GBSB is a partner, not a lead.")
    if org == "gbsb" and "ECHE" in ident:
        out.append("GBSB already holds the Erasmus Charter; this matters only if another GBSB legal entity (for example the Maltese or Madrid operation) needs its own charter.")
    if opp["status"] == "forthcoming":
        out.append("Forthcoming: the call text may still change before opening.")
    return out


def score(profile: dict, opp: dict) -> tuple[float, list[dict], str | None]:
    """Return (score, matched rules, strength cap). Title evidence counts in
    full; a keyword found only in the long call text counts 40-70% depending on
    how often it recurs, so boilerplate ('SMEs', 'policy') cannot carry a match."""
    title = opp["title"] + " " + opp.get("cpv_label", "")
    text = opp["text"]
    is_ted = opp["kind"] == "ted"
    if is_ted and (profile["negative"].search(title) or any(c.startswith("45") for c in opp["cpv"][:1])):
        return 0.0, [], None
    hits, s, title_hit, intitle = [], 0.0, False, set()
    for rule in profile["rules"]:
        if rule["ted"] and not is_ted:
            continue
        w = 0.0
        if rule["cpv"] and any(c.startswith(rule["cpv"]) for c in opp["cpv"]):
            w = rule["weight"]
        if rule["rx"] is not None:
            if rule["rx"].search(title):
                w = max(w, rule["weight"])
                intitle.add(rule["key"])
                title_hit = title_hit or rule["core"]
            elif not rule["ted"] and not is_ted:
                n = len(rule["rx"].findall(text))
                if n:
                    w = max(w, rule["weight"] * (0.25 + 0.15 * min(n, 3)))
        if w:
            hits.append(rule)
            s += w
    if not hits:
        return 0.0, [], None
    cap = None
    for h in hits:
        if h.get("cap") and (cap is None or STRENGTH_ORDER[h["cap"]] > STRENGTH_ORDER[cap]):
            cap = h["cap"]
    if profile.get("exclude_prefix") and opp["ident"].upper().startswith(profile["exclude_prefix"]):
        return 0.0, [], None
    if not is_ted and not title_hit:
        # Nothing in the title names the organisation's subject: keep as a Stretch at most.
        s *= 0.75
        cap = "Stretch"
    if is_ted:
        if not any(h["ted"] for h in hits):
            return 0.0, [], None
        if profile.get("exclude_cpv") and opp["cpv"] and all(c.startswith(profile["exclude_cpv"]) for c in opp["cpv"]):
            return 0.0, [], None
        req = profile.get("ted_require")
        if req is not None and not req.search(title):
            return 0.0, [], None
        # Words that make a notice NOT this organisation's business even when a
        # rule fired (23 Sep 2026: "Phishing-Simulation" hit Cadence's simulation
        # rule, and a MOVPE reactor, fab equipment, hit its chips rule).
        ted_ex = profile.get("ted_exclude")
        if ted_ex is not None and ted_ex.search(title):
            return 0.0, [], None
        theme = profile.get("home_theme") or profile.get("foreign_theme")
        if theme is not None and not theme.search(title) and not any(h["cpv"] and h["key"] in ("cpv_legal", "cpv_edu", "cpv_bizdev") for h in hits):
            return 0.0, [], None
        eu_buyer = bool(EU_BUYER.search(opp["buyer"] or ""))
        if eu_buyer:
            s += 1.5
        elif opp["country"] in profile["ted_country_bonus"]:
            s += profile["ted_country_bonus"][opp["country"]]
        else:
            if profile["ted_country_bonus"]:
                # Foreign national tender: needs the contract's own title to say so, and never rates above Stretch.
                if not any(h["key"] == "ted_kw" for h in hits) or not profile.get("foreign_theme", re.compile(".")).search(title):
                    return 0.0, [], None
                cap = "Stretch"
            s += profile["ted_foreign_malus"]
    for pre, bonus in profile["prog_bonus"].items():
        if opp["ident"].upper().startswith(pre.upper()):
            s += bonus
            break
    tech = profile.get("tech_penalty")
    if tech is not None and not is_ted and tech.search(opp["title"]) and "coordination and support" not in (opp["action"] or "").lower():
        s -= 3
        if not any(h["key"] in ("dpp", "textile") and h["rx"].search(opp["title"]) for h in hits):
            cap = "Stretch"  # technology-led topic: a legal partner is a supporting role at most
        elif cap is None or STRENGTH_ORDER[cap] < STRENGTH_ORDER["Medium"]:
            cap = "Medium"
    if not is_ted and profile["negative"].search(opp["title"]):
        s -= 5
    return s, sorted(hits, key=lambda h: (h["key"] not in intitle and not h["ted"], -h["weight"])), cap


ACTION_CLEAN = re.compile(r"^(HORIZON|LIFE|DIGITAL|EDF|JU|ERASMUS|EURATOM|ISF|JUST|CERV|SMP|CEF|EU4H|CREA)\s+(JU\s+)?", re.I)


def lead_sentence(opp: dict) -> str:
    if opp["kind"] == "ted":
        label = opp.get("cpv_label") or "services or supplies"
        label = label[0].lower() + label[1:] if len(label) > 1 and not label[1].isupper() else label
        where = "" if EU_BUYER.search(opp["buyer"] or "") else f" in {COUNTRY.get(opp['country'], opp['country'])}"
        return f"{opp['buyer'] or 'A public buyer'}{where} is tendering for {label}."
    if opp["kind"] in ("tender", "expert_list"):
        return f"{opp['buyer'] or opp['programme']} has an open {opp['action'].lower()}."
    action = ACTION_CLEAN.sub("", re.sub(r"\s+", " ", opp["action"] or "")).strip()
    action = re.sub(r"s$", "", action) if action.endswith(("Actions", "Grants", "Networks")) else action
    budget = f" ({opp['budget']})" if opp.get("budget") else ""
    what = (f"An {action} topic" if action[:1].upper() in "AEIOU" else f"A {action} topic") if action else "A call"
    return f"{what} under {opp['programme']}{budget}."


def explain(profile: dict, opp: dict, hits: list[dict], strength: str) -> str:
    sentences = [lead_sentence(opp)]
    seen = set()
    in_title = [h for h in hits if h["ted"] or (h["rx"] is not None and h["rx"].search(opp["title"] + " " + opp.get("cpv_label", ""))) or (h["cpv"] and any(c.startswith(h["cpv"]) for c in opp["cpv"]))]
    ordered = in_title + [h for h in hits if h not in in_title][: max(0, 1 - len([x for x in in_title if x["why"]]))]
    for h in ordered:
        if h["why"] and h["why"] not in seen:
            seen.add(h["why"])
            sentences.append(h["why"])
        if len(sentences) == 3:
            break
    role = next((h["role"] for h in hits if h.get("role")), None) or role_for(profile["slug"], opp, strength)
    sentences.append(f"Realistic role: {role}.")
    return " ".join(sentences)


# --------------------------------------------------------------------------- #
# HTML
# --------------------------------------------------------------------------- #
def logo_data_uri(path: Path, size: int = 96) -> str:
    try:
        from PIL import Image  # type: ignore
        im = Image.open(path)
        im.thumbnail((size, size))
        buf = io.BytesIO()
        im.save(buf, format="PNG", optimize=True)
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


def fmt_date(d: dt.date | None) -> str:
    return d.strftime("%-d %b %Y") if d else "Not stated"


def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


CSS = """
:root{--ink:#111827;--muted:#4b5563;--line:#e5e7eb;--bg:#ffffff;--soft:#f9fafb;--blue:#0693e3;--purple:#9b51e0;
--high:#059669;--med:#0693e3;--stretch:#9b51e0;--warn:#d97706}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding-inline:20px}
h1,h2,h3{font-family:"Adobe Caslon Pro","Libre Caslon Text",Georgia,"Times New Roman",serif;font-weight:600;letter-spacing:-.01em}
header.hero{background:linear-gradient(135deg,#06112f 0%,#1c3d7a 50%,#5b3a8c 100%);color:#fff;padding-block:44px 36px}
.hero .brand{display:flex;align-items:center;gap:10px;background:#fff;color:#111;border-radius:999px;padding:6px 14px 6px 6px;width:max-content;font-weight:600}
.hero .brand img{width:30px;height:30px}
.overline{font-family:"JetBrains Mono",ui-monospace,Menlo,monospace;font-size:12px;letter-spacing:.08em;text-transform:uppercase;opacity:.85;margin-top:22px}
.hero h1{font-size:clamp(1.7rem,4vw,2.9rem);margin:.25em 0 .3em;line-height:1.1}
.hero p{max-width:820px;opacity:.92;margin:0}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-block:26px 6px}
.stat{background:#fff;color:var(--ink);border-radius:10px;padding:14px 16px;border-left:5px solid var(--blue)}
.stat:nth-child(2){border-left-color:var(--purple)}.stat:nth-child(3){border-left-color:var(--high)}
.stat b{font-family:Georgia,serif;font-size:1.9rem;display:block;line-height:1.1}
.stat small{color:var(--muted)}
section{padding-block:26px}
.label{font-family:"JetBrains Mono",ui-monospace,Menlo,monospace;color:var(--purple);font-size:12px;letter-spacing:.08em;text-transform:uppercase}
.card{background:var(--soft);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin-block:12px}
.method ul,.card ul{margin:.3em 0 .2em 1.1em;padding:0}
.org h2{font-size:2rem;margin:.2em 0 .1em}
.org .legal{color:var(--muted);margin:0 0 .8em}
.counts{display:flex;gap:8px;flex-wrap:wrap;margin:.6em 0 1em}
.pill{display:inline-block;border-radius:999px;padding:2px 10px;font-size:12px;font-weight:600;color:#fff;white-space:nowrap}
.pill.High{background:var(--high)}.pill.Medium{background:var(--med)}.pill.Stretch{background:var(--stretch)}
.pill.ghost{background:#eef2ff;color:#3730a3}
.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:10px;-webkit-overflow-scrolling:touch}
table{border-collapse:collapse;width:100%;min-width:980px;background:#fff}
th,td{text-align:left;vertical-align:top;padding:10px 12px;border-bottom:1px solid var(--line);font-size:14px}
th{background:#f3f4f6;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:#374151;cursor:pointer;user-select:none;position:sticky;top:0}
th[aria-sort]::after{content:" \\2195";color:#9ca3af}
td.t a{color:#0b5cad;font-weight:600;text-decoration:none}td.t a:hover{text-decoration:underline}
td .note{display:block;color:var(--muted);font-size:12px;margin-top:2px}
td.why{min-width:320px}
td .cav{display:block;color:#92400e;font-size:12.5px;margin-top:6px}
.small{font-size:13px;color:var(--muted)}
.closing{border-left:4px solid var(--warn);background:#fffbeb}
footer{margin-top:30px;background:#fff;border-top:4px solid transparent;border-image:linear-gradient(90deg,#0693e3,#9b51e0) 1}
footer .wrap{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;padding-block:18px}
footer img{height:34px;width:auto;vertical-align:middle}
a{color:#0b5cad}
@media (max-width:900px){.stats{grid-template-columns:1fr 1fr}}
@media (max-width:767px){.wrap{padding-inline:16px}.stats{grid-template-columns:1fr}.hero h1{font-size:1.9rem}.org h2{font-size:1.6rem}}
"""

SORT_JS = """
document.querySelectorAll('table.sortable').forEach(function(t){
  t.querySelectorAll('th').forEach(function(th,i){
    th.setAttribute('aria-sort','none');
    th.addEventListener('click',function(){
      var body=t.tBodies[0],rows=Array.prototype.slice.call(body.rows),asc=th.getAttribute('aria-sort')!=='ascending';
      t.querySelectorAll('th').forEach(function(x){x.setAttribute('aria-sort','none')});
      th.setAttribute('aria-sort',asc?'ascending':'descending');
      rows.sort(function(a,b){var x=a.cells[i].getAttribute('data-sort')||a.cells[i].textContent,y=b.cells[i].getAttribute('data-sort')||b.cells[i].textContent;
        var nx=parseFloat(x),ny=parseFloat(y);if(!isNaN(nx)&&!isNaN(ny)){return asc?nx-ny:ny-nx}return asc?x.localeCompare(y):y.localeCompare(x)});
      rows.forEach(function(r){body.appendChild(r)});
    });
  });
});
"""

STRENGTH_ORDER = {"High": 0, "Medium": 1, "Stretch": 2}


def render_table(rows: list) -> str:
    t: list[str] = []
    t.append('<div class="tablewrap"><table class="sortable"><thead><tr><th>Opportunity</th><th>Programme and type</th><th>Opens</th><th>Deadline</th><th>Budget</th><th>Fit</th><th>Why it fits, role and caveats</th></tr></thead><tbody>')
    for m in rows:
        o = m["opp"]
        note = f'<span class="note">{esc(o["title_note"])}</span>' if o.get("title_note") else ""
        buyer = f'<span class="note">{esc(o["buyer"])}{" (" + esc(COUNTRY.get(o["country"], o["country"])) + ")" if o["kind"] == "ted" else ""}</span>' if o.get("buyer") else ""
        status = " (forthcoming)" if o["status"] == "forthcoming" else ""
        cav = "".join(f'<span class="cav">{esc(x)}</span>' for x in m["caveats"])
        t.append(
            f'<tr><td class="t" data-sort="{esc(o["title"])}"><a href="{esc(o["url"])}" target="_blank" rel="noopener">{esc(o["title"])}</a>{note}{buyer}<span class="note">{esc(o["source"])}</span></td>'
            f'<td>{esc(o["programme"])}<span class="note">{esc(o["action"])}{status}</span></td>'
            f'<td data-sort="{o["opens"].isoformat() if o["opens"] else ""}">{fmt_date(o["opens"])}</td>'
            f'<td data-sort="{o["deadline"].isoformat()}"><b>{fmt_date(o["deadline"])}</b></td>'
            f'<td>{esc(o["budget"]) or "Not stated"}</td>'
            f'<td data-sort="{STRENGTH_ORDER[m["strength"]]}"><span class="pill {m["strength"]}">{m["strength"]}</span></td>'
            f'<td class="why">{esc(m["why"])}{cav}</td></tr>')
    t.append("</tbody></table></div>")
    return "\n".join(t)




def render(today: dt.date, results: dict, closing: dict, stats: dict, problems: Counter, templates: list, gaps: dict) -> str:
    brubru = logo_data_uri(REPO / "frontend/public/assets/brubru_icon_colours.png", 64)
    beresol = logo_data_uri(REPO / "frontend/public/assets/beresol-logo.png", 120)
    date_txt = today.strftime("%-d %B %Y")
    h = [f"<title>EU Funding Matches, {esc(date_txt)}</title><style>{CSS}</style>"]
    h.append('<header class="hero"><div class="wrap">')
    brand_img = ('<img alt="Brubru" src="' + brubru + '">') if brubru else ""
    h.append(f'<div class="brand">{brand_img}Brubru</div>')
    h.append(f'<div class="overline">EU funding and tender matches &middot; {esc(date_txt)}</div>')
    h.append("<h1>Where EU money fits Terraqui, GBSB Global Business School and Cadence</h1>")
    h.append(f"<p>{stats['eligible_total']:,} open or forthcoming opportunities with a deadline on or after {esc(date_txt)} were scored against each organisation's own activities. Every match below links to its public page and says why it fits, what role is realistic and what could stop it.</p>")
    h.append('<div class="stats">')
    for p in PROFILES:
        c = Counter(m["strength"] for m in results[p["slug"]])
        h.append(f'<div class="stat"><b>{len(results[p["slug"]])}</b>{esc(p["name"])}<br><small>{c["High"]} high &middot; {c["Medium"]} medium &middot; {c["Stretch"]} stretch</small></div>')
    h.append("</div></div></header>")

    # Method
    h.append('<main class="wrap"><section class="method"><div class="label">Method and data</div><h2>How this report was built</h2>')
    h.append('<div class="card"><ul>')
    h.append(f"<li><b>Sources.</b> Brubru API v2, production: Funding and Tenders portal calls ({stats['ft_rows']:,} rows across funding-opportunities, startups, entrepreneur-instruments, innovation-fund, justice and calls for tenders), EU agency procurement and calls ({stats['agency_rows']:,} rows from funding/all, EISMEA, HaDEA, ECCC and EEAS, with cohesion allocations, CAP payments and Solidarity Fund cases ignored), and {stats['ted_rows']:,} TED notices with a deadline from {esc(date_txt)}.</li>")
    h.append("<li><b>Verification.</b> The API's status field lags and hundreds of portal rows have no deadline, so every portal row was checked against the portal's own search service for status, opening date, deadline, English title and budget. An opportunity is included only if it is open or forthcoming with a deadline on or after today. Agency calls without a readable deadline were left out rather than guessed.</li>")
    h.append("<li><b>Scoring.</b> Each organisation has a written profile (read from its website) turned into weighted themes: keywords in the title and full call text, CPV codes for tenders, programme and type of action, buyer country, and realistic role. Title evidence counts more than a keyword buried in a long call text. Out-of-scope subjects are penalised. Scores map to High (8+), Medium (5.5+) and Stretch (4+). Foreign national tenders never rate above Stretch for the two Spanish organisations. Opportunities closing within 48 hours are listed separately.</li>")
    h.append("<li><b>Strength means fit, not probability of winning.</b> High: the subject matter is squarely what the organisation does and a realistic role exists. Medium: clear overlap, but a partner, language or eligibility step is needed. Stretch: plausible angle worth a quick read.</li>")
    h.append("</ul></div>")
    h.append('<div class="card"><b>Caveats and data defects found</b><ul>')
    cap_days = [d for d, n in stats["ted_daily_ingest"].items() if n == 400]
    pub_days = [d for d, n in stats["ted_daily_ingest"].items() if n]
    h.append(f"<li><b>TED ingest cap.</b> Brubru ingests TED at about 400 notices per publication day; {len(cap_days)} of the {len(pub_days)} publication days in the last two weeks stopped at exactly 400, while the Official Journal S series publishes well over a thousand notices a day. Tender matches are therefore a sample of the market, not a census.</li>")
    if stats.get("portal_open_total"):
        h.append(f"<li><b>Coverage gap.</b> The Funding and Tenders portal lists {stats['portal_open_total']:,} open or forthcoming topics, tenders and cascade calls today. After verification Brubru's API holds {stats['ft_verified_open']:,} live portal items with a future deadline, and {stats.get('portal_gap', 0):,} live items are missing, including every Chips Joint Undertaking call and most cascade (third-party) calls. The main tables are built from Brubru's API only; High and Medium fits among the missing items are listed separately under each organisation.</li>")
    for k, v in problems.most_common():
        h.append(f"<li>{esc(k)}: {v:,}.</li>")
    h.append("<li>TED titles in Brubru's feed carry the CPV label in English plus the buyer's own title in the notice language, with no description; titles are shown as published and marked.</li>")
    h.append("<li>Eligibility notes are a first reading of general programme rules, not legal advice; every call's own conditions prevail.</li>")
    h.append("</ul></div></section>")

    tpl_by_prog = {}
    for t in templates:
        tpl_by_prog.setdefault(str(t.get("programme", "")).upper(), t)

    for p in PROFILES:
        rows = results[p["slug"]]
        c = Counter(m["strength"] for m in rows)
        h.append(f'<section class="org" id="{p["slug"]}"><div class="label">Organisation</div><h2>{esc(p["name"])}</h2>')
        h.append(f'<p class="legal">{esc(p["legal"])} &middot; <a href="{esc(p["site"])}">{esc(p["site"])}</a></p>')
        h.append('<div class="card">' + "".join(f"<p>{esc(x)}</p>" for x in p["profile"]) + "<b>Eligibility</b><ul>" + "".join(f"<li>{esc(x)}</li>" for x in p["eligibility"]) + "</ul></div>")
        h.append(f'<div class="counts"><span class="pill ghost">{len(rows)} matches</span><span class="pill High">{c["High"]} High</span><span class="pill Medium">{c["Medium"]} Medium</span><span class="pill Stretch">{c["Stretch"]} Stretch</span></div>')
        h.append(render_table(rows))
        cl = closing[p["slug"]]
        if cl:
            h.append('<div class="card closing"><b>Closing now (within 48 hours), listed for awareness only</b><ul>')
            for m in cl:
                o = m["opp"]
                h.append(f'<li><a href="{esc(o["url"])}" target="_blank" rel="noopener">{esc(o["title"])}</a>, {esc(o["programme"])}, deadline {fmt_date(o["deadline"])} ({m["strength"]} fit)</li>')
            h.append("</ul></div>")
        g = gaps.get(p["slug"]) or []
        if g:
            h.append(f'<h3>Also open on the EU portal, not yet in Brubru&rsquo;s API ({len(g)})</h3><p class="small">These High and Medium fits come from the Funding and Tenders portal\'s own open-call listing, scored the same way. They are not counted above because Brubru&rsquo;s API does not hold them yet.</p>')
            h.append(render_table(g))
        h.append("</section>")

    if templates:
        h.append('<section><div class="label">Next step</div><h2>Application templates in Brubru</h2><div class="card"><p>Brubru keeps official application templates for the main programmes that appear above, reachable through the Tenderator and the API:</p><ul>')
        for t in templates:
            if str(t.get("programme")) in ("LIFE", "DIGITAL", "EIC", "ERASMUS+", "CEF", "ESF+"):
                h.append(f'<li><a href="{esc(t.get("public_url"))}" target="_blank" rel="noopener">{esc(t.get("name"))}</a></li>')
        h.append("</ul></div></section>")
    h.append("</main>")
    beresol_img = ('<img alt="Beresol" src="' + beresol + '">') if beresol else "Beresol"
    h.append(f'<footer><div class="wrap"><div class="small">Data: Brubru API v2, retrieved {esc(date_txt)}. Built by Brubru, All the EU, with AI. <a href="https://brubru.beresol.eu">brubru.beresol.eu</a> &middot; hello@beresol.eu</div>'
             f'<div class="small">by {beresol_img}</div></div></footer>')
    h.append(f"<script>{SORT_JS}</script>")
    # House style: no em dashes in user-facing text (source titles included).
    return "\n".join(h).replace("\u2014", ", ").replace(" \u2013 ", " - ")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", default=dt.date.today().isoformat(), help="report date (YYYY-MM-DD), default today")
    ap.add_argument("--out", default=None, help="output HTML path")
    ap.add_argument("--cache-dir", default=None, help="directory to save (or read with --use-cache) the raw harvest")
    ap.add_argument("--use-cache", action="store_true", help="reuse raw.json and sedia.json from --cache-dir")
    ap.add_argument("--json", default=None, help="optional path to write the match list as JSON")
    args = ap.parse_args()

    today = dt.date.fromisoformat(args.date)
    out = Path(args.out) if args.out else REPO / "docs" / "funding_matches" / f"{today.isoformat()}-funding-matches.html"
    cache = Path(args.cache_dir) if args.cache_dir else None
    api = Api(load_key())

    if cache and args.use_cache and (cache / "raw.json").exists():
        raw = json.loads((cache / "raw.json").read_text())
        print("[INFO] using cached harvest")
    else:
        raw = harvest(api, today)
        if cache:
            cache.mkdir(parents=True, exist_ok=True)
            (cache / "raw.json").write_text(json.dumps(raw))

    problems: Counter = Counter()

    # Portal rows: gather identifiers from every portal-backed endpoint.
    ft_rows: list[tuple[str, dict]] = []
    for p in FT_ENDPOINTS + ["/api/v2/funding/entrepreneur-instruments"]:
        for r in raw.get(p) or []:
            ft_rows.append((p, r))
    for r in raw.get("/api/v2/funding/all") or []:
        u = r.get("public_url") or ""
        if "topic-details/" in u or "tender-details/" in u:
            ft_rows.append(("/api/v2/funding/all", {"tender_reference": u.rstrip("/").split("/")[-1]} if "tender-details/" in u else {"topic_id": u.rstrip("/").split("/")[-1], "title": r.get("title")}))
    idents = [(r.get("topic_id") or r.get("tender_reference") or (r.get("public_url") or "").rstrip("/").split("/")[-1]) for _, r in ft_rows]

    for r in raw.get("/api/v2/funding/entrepreneur-instruments") or []:
        dd = d10(r.get("deadline"))
        if r.get("status") in ("open", "forthcoming") and dd and dd < today:
            problems["entrepreneur-instruments rows marked open/forthcoming with a past deadline (excluded)"] += 1
    ctas = [r for r in raw.get("/api/v2/funding/ft-calls-for-tenders") or []]
    if ctas:
        problems["ft-calls-for-tenders rows whose contracting_authority holds a programme period instead of a buyer"] += sum(1 for r in ctas if re.match(r"^\d{4} - \d{4}$", str(r.get("contracting_authority") or "")))
        problems["ft-calls-for-tenders rows with no deadline in the API"] += sum(1 for r in ctas if not r.get("deadline"))

    if cache and args.use_cache and (cache / "sedia.json").exists():
        meta = json.loads((cache / "sedia.json").read_text())
    else:
        print(f"[INFO] verifying {len(set(idents)):,} portal identifiers")
        meta = sedia_enrich(idents)
        if cache:
            (cache / "sedia.json").write_text(json.dumps(meta))

    opps: dict[str, dict] = {}
    ft_idents = set()
    for (src, r), ident in zip(ft_rows, idents):
        if not ident or ident in ft_idents:
            continue
        ft_idents.add(ident)
        o = norm_ft(r, src, meta.get(ident), today, problems)
        if o:
            opps[o["uid"]] = o
    ft_verified_open = len(opps)
    agency_rows = 0
    seen_agency = set()
    for p in AGENCY_ENDPOINTS:
        for r in raw.get(p) or []:
            key = (r.get("body_code"), r.get("id"))
            if key in seen_agency:
                continue
            seen_agency.add(key)
            if r.get("item_type") in EXCLUDED_ALL_TYPES:
                continue
            agency_rows += 1
            o = norm_agency(r, today, problems, ft_idents)
            if o:
                opps[o["uid"]] = o
    for r in raw.get("ted") or []:
        o = norm_ted(r, today)
        if o:
            opps.setdefault(o["uid"], o)
    for n in raw.get("ted_notes") or []:
        problems[n] += 1

    # Portal items that Brubru's API does not hold (reported separately).
    gap_opps: dict[str, dict] = {}
    if cache and args.use_cache and (cache / "portal_open.json").exists():
        portal_all = json.loads((cache / "portal_open.json").read_text())
    else:
        try:
            portal_all = sedia_portal_open_all()
        except Exception as e:
            portal_all = []
            print(f"[ERROR] portal listing failed: {type(e).__name__}")
        if cache:
            (cache / "portal_open.json").write_text(json.dumps(portal_all))
    gap_problems: Counter = Counter()
    for m in portal_all:
        ident = first(m, "identifier")
        if not ident or ident in ft_idents or ("ft:" + ident) in gap_opps:
            continue
        o = norm_ft({"topic_id": ident}, "portal", m, today, gap_problems)
        if o:
            o["source"] = "EU Funding & Tenders portal (not yet in Brubru's API)"
            gap_opps[o["uid"]] = o

    results, closing, gaps = {}, {}, {}
    for p in PROFILES:
        gm = []
        for o in gap_opps.values():
            s_, hits_, cap_ = score(p, o)
            st_ = next((name for name, t in THRESHOLDS if s_ >= t), None)
            if st_ in ("High", "Medium") and (o["deadline"] - today).days > 2:
                gm.append(dict(opp=o, score=round(s_, 2), strength=st_, why=explain(p, o, hits_, st_),
                               caveats=caveats_for(p["slug"], o), rules=[h["key"] for h in hits_]))
        gaps[p["slug"]] = sorted(gm, key=lambda m: (STRENGTH_ORDER[m["strength"]], -m["score"], m["opp"]["deadline"]))
    main_titles = {re.sub(r"\W+", " ", o["title"]).strip().lower() for o in opps.values()}
    for slug in gaps:
        # The same call can reach Brubru through an agency page under another identifier.
        gaps[slug] = [m for m in gaps[slug] if re.sub(r"\W+", " ", m["opp"]["title"]).strip().lower() not in main_titles]
    for p in PROFILES:
        matches, near = [], []
        for o in opps.values():
            s, hits, cap = score(p, o)
            strength = next((name for name, t in THRESHOLDS if s >= t), None)
            if not strength:
                continue
            if o["kind"] == "ted" and strength == "High" and not any(h["key"] in p.get("ted_high_keys", ()) for h in hits):
                strength = "Medium"  # a national tender rates High only when its CPV code is the organisation's own service
            if cap and STRENGTH_ORDER[strength] < STRENGTH_ORDER[cap]:
                strength = cap
            m = dict(opp=o, score=round(s, 2), strength=strength, why=explain(p, o, hits, strength),
                     caveats=caveats_for(p["slug"], o), rules=[h["key"] for h in hits])
            (near if (o["deadline"] - today).days <= 2 else matches).append(m)
        # One row per TED notice title+buyer (lots are often published as separate notices).
        dedup, keys = [], set()
        for m in sorted(matches, key=lambda m: (STRENGTH_ORDER[m["strength"]], -m["score"], m["opp"]["deadline"])):
            k = (m["opp"]["title"].lower(), m["opp"]["buyer"].lower())
            if k in keys:
                continue
            keys.add(k)
            dedup.append(m)
        results[p["slug"]] = dedup
        closing[p["slug"]] = sorted(near, key=lambda m: -m["score"])

    stats = dict(eligible_total=len(opps), ft_rows=len(ft_rows), agency_rows=agency_rows, ted_rows=len(raw.get("ted") or []),
                 ted_daily_ingest=raw.get("ted_daily_ingest") or {}, ft_verified_open=ft_verified_open,
                 portal_open_total=len(portal_all) or sedia_portal_open_count(), portal_gap=len(gap_opps))
    templates = raw.get("/api/v2/proprietary/tender-docs/templates") or []
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(today, results, closing, stats, problems, templates, gaps), encoding="utf-8")
    print(f"[OK] wrote {out}")
    print(f"[INFO] eligible opportunities: {len(opps):,} (portal {ft_verified_open}, agency+TED {len(opps) - ft_verified_open}); API calls {api.calls}")
    for p in PROFILES:
        c = Counter(m["strength"] for m in results[p["slug"]])
        print(f"[INFO] {p['name']}: portal-gap High/Medium {len(gaps[p['slug']])}")
        print(f"[INFO] {p['name']}: {len(results[p['slug']])} matches (High {c['High']}, Medium {c['Medium']}, Stretch {c['Stretch']}); closing now {len(closing[p['slug']])}")
        for m in results[p["slug"]][:5]:
            print(f"    {m['strength']:7} {m['score']:5} {m['opp']['deadline']} {m['opp']['title'][:90]} | {m['opp']['url']}")
    for k, v in problems.most_common():
        print(f"[INFO] data: {k}: {v}")
    if api.failures:
        print(f"[ERROR] {len(api.failures)} API requests failed after retries: {api.failures[:5]}")
    if args.json:
        Path(args.json).write_text(json.dumps({s + suffix: [dict(title=m["opp"]["title"], url=m["opp"]["url"], strength=m["strength"], score=m["score"],
                                                         deadline=m["opp"]["deadline"].isoformat(), programme=m["opp"]["programme"], why=m["why"], source=m["opp"].get("source"),
                                                         caveats=m["caveats"], rules=m["rules"]) for m in rows] for suffix, src in (("", results), ("_gap", gaps)) for s, rows in src.items()}, indent=1))
    if api.failures:
        sys.exit(1)


if __name__ == "__main__":
    main()

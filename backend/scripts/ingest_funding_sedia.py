"""
Real ingestion of EU funding opportunities via the SEDIA search API.

The F&T Portal (https://ec.europa.eu/info/funding-tenders/opportunities) is a
JS-rendered SPA and exposes no useful RSS feed. The portal IS backed by a
public search API at api.tech.ec.europa.eu — that's what the SPA calls under
the hood. We use it directly here.

Endpoint:
    POST https://api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey=SEDIA&text=***
         &pageNumber=N&pageSize=100
    multipart/form-data parts (JSON blobs): query (bool filter on type/status/
    identifier), languages (["en"]), sort.

Passes (see main):
    1. every open/forthcoming grant topic (type 1, 8) and, with --write-ft,
       every open/forthcoming call for tenders (type 0), English, uncapped;
    2. re-read by identifier of stored rows that can still be wrong;
    3. optional (--discover / --text) full-text prefix discovery;
    then a date-derived status pass over all three tables.

Mapping:
    topic_id      = identifier (e.g. "HORIZON-CL5-2026-D2-01-04")
    call_id       = callIdentifier
    programme     = frameworkProgramme code -> label (facet), NEVER programmePeriod
    title         = title (English record)
    status        = derived from startDate + deadlineDate, SEDIA status as fallback
    deadline      = next cut-off still to come, else the last one
    tenders       = contracting_authority from cftLeadContractingAuthorityCode,
                    value from cftEstimatedOverallContractAmount

UPSERT on topic_id. Run:
    python3.12 backend/scripts/ingest_funding_sedia.py [--limit 200] [--apply]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

import psycopg2
import psycopg2.extras
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
SEDIA_URL_TEMPLATE = (
    "https://api.tech.ec.europa.eu/search-api/prod/rest/search"
    "?apiKey=SEDIA&text={text}"
)
PORTAL_BASE = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details"
USER_AGENT = "Mozilla/5.0 (compatible; BrubruIngest/1.0; +https://brubru.beresol.eu)"

# SEDIA status code mapping (from the portal's Angular source).
STATUS_MAP = {
    "31094501": "forthcoming",
    "31094502": "open",
    "31094503": "closed",
}


def get_env(key: str) -> str:
    """Config value from the real environment first, then a local .env file.

    The os.environ branch is the whole point. This function used to read the
    repo-root .env and nothing else, and Railway has no .env file -- config
    arrives as environment variables. So under cron every script using this
    helper got "" for DATABASE_URL, printed "[FATAL] DATABASE_URL missing" and
    exited 1, which _run_script logged as a failure and moved past. The three
    SEDIA-backed daily jobs (this one, ingest_ft_news_events,
    ingest_ft_programme_calls) had therefore never written a row in production:
    funding_opportunities stopped at 29 Jun 2026 and the ftportal news/events
    rows at 14 Jun, both dates of the last manual run from a laptop.

    Local .env stays as the fallback so the scripts still run from a checkout.
    """
    from_environ = os.environ.get(key)
    if from_environ:
        return from_environ.strip()
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def html_strip(html: str, max_len: int = 4000) -> str:
    if not html:
        return ""
    try:
        text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    except Exception:  # noqa: BLE001
        text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return (text[:max_len] + "…") if len(text) > max_len else text


# SEDIA record types (from the facet endpoint, 15 Sep 2026):
#   0 Tender, 1 Grant (a call topic), 2 Calls for proposals (external action),
#   8 Cascade funding calls.
# Type 6 is NOT in that list and is the trap: it is a topic UPDATE / announcement
# record that reuses the topic identifier and title but carries no status and no
# deadline, and whose startDate is the time the update was posted. Ingesting it is
# how 700 calls ended at status 'unknown' and how HORIZON-MISS-2026-02-CANCER-04
# acquired a published_at two days after the call actually opened.
TENDER_TYPES = ["0"]
GRANT_TYPES = ["1", "8"]
OPEN_STATUS_CODES = ["31094501", "31094502"]  # forthcoming, open


def _multipart(fields: Dict[str, Any]) -> tuple[bytes, str]:
    """Encode SEDIA's multipart form. Each part is a JSON blob, as the portal SPA sends."""
    boundary = "----brubru" + os.urandom(8).hex()
    out = []
    for name, value in fields.items():
        out.append(f"--{boundary}\r\n".encode())
        out.append(
            f'Content-Disposition: form-data; name="{name}"; filename="blob"\r\n'
            "Content-Type: application/json\r\n\r\n".encode()
        )
        out.append(json.dumps(value).encode())
        out.append(b"\r\n")
    out.append(f"--{boundary}--\r\n".encode())
    return b"".join(out), f"multipart/form-data; boundary={boundary}"


def fetch_sedia_page(page: int, page_size: int = 100, status_filter: Optional[str] = None,
                     text: str = "***", *, query: Optional[Dict[str, Any]] = None,
                     languages: Optional[List[str]] = ("en",),
                     sort: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """One page of SEDIA results.

    Pagination MUST go in the URL — the API ignores pageNumber/pageSize in the
    body.

    Filters DO work, but only as a multipart form (parts `query`, `languages`,
    `sort`, each a JSON blob), which is what the portal SPA sends. The previous
    version POSTed a JSON body `{}`, concluded "the API doesn't honour body-level
    filters", and therefore received every topic once per EU language, interleaved.
    With a `--limit 500` budget the English record often never arrived, which is
    why the Tenderator served "Frühere und präzisere Palliativpflege" and "Skalowanie
    EIC STEP" for calls SEDIA holds in English. `languages=["en"]` is now the
    default; pass `languages=None` to get every language.

    `text` is a SEDIA full-text query ('***' = everything). `query` is an
    Elasticsearch-style bool filter, e.g.
    {"bool": {"must": [{"terms": {"type": ["1"]}}, {"terms": {"status": [...]}}]}}.
    `status_filter` (a single SEDIA status code) is folded into `query`.
    """
    url = SEDIA_URL_TEMPLATE.format(text=urllib_request.quote(text, safe="*")) + f"&pageNumber={page}&pageSize={page_size}"
    must = list(((query or {}).get("bool") or {}).get("must") or [])
    if status_filter:
        must.append({"terms": {"status": [status_filter]}})
    fields: Dict[str, Any] = {}
    if must:
        fields["query"] = {"bool": {"must": must}}
    if languages:
        fields["languages"] = list(languages)
    if sort:
        fields["sort"] = sort
    if fields:
        body, ctype = _multipart(fields)
    else:
        body, ctype = b"{}", "application/json"
    req = urllib_request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": ctype,
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib_request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib_error.HTTPError as e:
        print(f"  [HTTP {e.code}] page={page}: {e.read()[:200]}")
        return {}
    except Exception as e:  # noqa: BLE001
        print(f"  [{type(e).__name__}] page={page}: {str(e)[:80]}")
        return {}


# ---------------------------------------------------------------------------
# Programme labels
# ---------------------------------------------------------------------------
# `programme` / `framework_programme` used to hold `programmePeriod`, i.e. the
# literal "2021 - 2027" on 1,314 calls and "2014 - 2020" on 534, so a filter such
# as framework_programme=Horizon matched nothing SEDIA wrote. The programme is
# `frameworkProgramme`, a numeric code whose labels come from SEDIA's facet
# endpoint. Fetched once per run; this static copy (the facet as read on 15 Sep
# 2026, the programmes Brubru ingests) is the fallback when the facet call fails.
_STATIC_PROGRAMME_LABELS = {
    "31045243": "Horizon 2020 Framework Programme (H2020 - 2014-2020)",
    "43108390": "Horizon Europe (HORIZON)",
    "43152860": "Digital Europe Programme (DIGITAL)",
    "43251567": "Connecting Europe Facility (CEF)",
    "43353764": "Erasmus+ (ERASMUS+)",
    "44181033": "European Defence Fund (EDF)",
    "43252405": "Programme for the Environment and Climate Action (LIFE)",
    "43252476": "Single Market Programme (SMP)",
    "43251814": "Creative Europe Programme (CREA)",
    "43251589": "Citizens, Equality, Rights and Values Programme (CERV)",
    "31059643": "Programme for the Competitiveness of Enterprises and small and medium-sized enterprises (COSME - 2014-2020)",
    "43332642": "EU4Health Programme (EU4H)",
    "43298916": "Euratom Research and Training Programme (EURATOM)",
    "43089234": "Innovation Fund (INNOVFUND)",
    "43252368": "Internal Security Fund (ISF)",
    "43252386": "Justice Programme (JUST)",
    "43251447": "Asylum, Migration and Integration Fund (AMIF)",
    "43251530": "Border Management and Visa Policy Instrument (BMVI)",
    "44416173": "Interregional Innovation Investments Instrument (I3)",
    "43254019": "European Social Fund+ (ESF+)",
    "43392145": "European Maritime, Fisheries and Aquaculture Fund (EMFAF)",
    "43252449": "Research Fund for Coal & Steel (RFCS)",
    "43298203": "Union Civil Protection Mechanism (UCPM)",
    "43252517": "Social Prerogative and Specific Competencies Lines (SOCPL)",
    "43637601": "Pilot Projects & Preparation Actions (PPPA)",
    "43254037": "European Solidarity Corps (ESC)",
    "44773066": "Just Transition Mechanism (JTM)",
}

# Last resort when a record carries no frameworkProgramme code: the identifier
# prefix. Longest prefix first. Never falls back to the programme PERIOD.
_PREFIX_PROGRAMME = [
    ("HORIZON-", "43108390"), ("H2020-", "31045243"), ("DIGITAL-", "43152860"),
    ("CEF-", "43251567"), ("ERASMUS-", "43353764"), ("EDF-", "44181033"),
    ("LIFE-", "43252405"), ("SMP-", "43252476"), ("CREA-", "43251814"),
    ("CERV-", "43251589"), ("COS-", "31059643"), ("EU4H-", "43332642"),
    ("EURATOM-", "43298916"), ("INNOVFUND-", "43089234"), ("ISF-", "43252368"),
    ("JUST-", "43252386"), ("AMIF-", "43251447"), ("BMVI-", "43251530"),
    ("I3-", "44416173"), ("ESF-", "43254019"), ("EMFAF-", "43392145"),
    ("RFCS-", "43252449"), ("UCPM-", "43298203"), ("SOCPL-", "43252517"),
    ("PPPA-", "43637601"), ("ESC-", "43254037"), ("JTM-", "44773066"),
]

_PROGRAMME_LABELS: Dict[str, str] = dict(_STATIC_PROGRAMME_LABELS)
_PERIOD_RE = re.compile(r"^\s*\d{4}\s*-\s*\d{4}\s*$")


def clean_facet_label(raw: str) -> str:
    """SEDIA's facet labels arrive half URL-encoded ('Coal %26 Steel') and with
    '+' decoded to a space ('Erasmus  (ERASMUS )')."""
    from urllib.parse import unquote
    label = unquote(raw or "")
    label = re.sub(r"\bErasmus\s{2,}\(ERASMUS\s*\)", "Erasmus+ (ERASMUS+)", label)
    label = re.sub(r"\bErasmus\s{2,}Programme", "Erasmus+ Programme", label)
    label = re.sub(r"\s+", " ", label).strip()
    label = label.replace("European Social Fund (ESF)", "European Social Fund+ (ESF+)")
    return label


_PARTY_LABELS: Dict[str, str] = {}
_CONTRACT_TYPE_LABELS: Dict[str, str] = {
    "31095498": "Services", "31095499": "Supplies", "31095501": "Works",
    "42893160": "Grants", "42958121": "Twinning",
}


def load_programme_labels() -> int:
    """Refresh the code->label maps (programme, buying DG/agency, contract type)
    from SEDIA's facet endpoint. Returns how many programme labels loaded."""
    url = "https://api.tech.ec.europa.eu/search-api/prod/rest/facet?apiKey=SEDIA&text=***"
    body, ctype = _multipart({
        "query": {"bool": {"must": [{"terms": {"type": ["0", "1", "2", "8"]}}]}},
        "languages": ["en"],
    })
    req = urllib_request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": ctype, "Accept": "application/json",
                                          "User-Agent": USER_AGENT})
    try:
        with urllib_request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        print(f"  [WARN] programme facet unavailable ({type(e).__name__}); using static labels")
        return 0
    n = 0
    targets = {"frameworkProgramme": _PROGRAMME_LABELS, "cftPartyLegalEntityId": _PARTY_LABELS,
               "contractType": _CONTRACT_TYPE_LABELS}
    for facet in data.get("facets") or []:
        target = targets.get(facet.get("name"))
        if target is None:
            continue
        for v in facet.get("values") or []:
            code, label = str(v.get("rawValue") or ""), clean_facet_label(v.get("value") or "")
            if code and label and label != code:
                target[code] = label
                if target is _PROGRAMME_LABELS:
                    n += 1
    return n


def programme_label(md: Dict[str, Any], identifier: str) -> Optional[str]:
    """The programme NAME for a record, or None. Never the programme period."""
    code = str(first_or_none(md.get("frameworkProgramme")) or "")
    if code and code in _PROGRAMME_LABELS:
        return _PROGRAMME_LABELS[code][:120]
    ident = (identifier or "").upper()
    for prefix, pcode in sorted(_PREFIX_PROGRAMME, key=lambda p: -len(p[0])):
        if ident.startswith(prefix):
            return _PROGRAMME_LABELS.get(pcode, _STATIC_PROGRAMME_LABELS[pcode])[:120]
    return None


def is_programme_period(value: Optional[str]) -> bool:
    return bool(value) and bool(_PERIOD_RE.match(value))


# ---------------------------------------------------------------------------
# Status from dates
# ---------------------------------------------------------------------------
def pick_deadlines(values, today: dt.date) -> tuple[Optional[dt.datetime], Optional[dt.datetime]]:
    """(deadline, final_deadline) from SEDIA's deadlineDate list.

    Multi-cut-off and rolling topics carry several dates.
    ERASMUS-EDU-2022-ECHE-CERT-FP lists 2022-05-03 ... 2027-01-26; taking the
    FIRST stored 2022-05-03 against an 'open' status, i.e. an open call whose
    deadline had passed four years ago. `deadline` is the next cut-off still to
    come (else the last one); `final_deadline` is the last, which decides closure.
    """
    parsed = sorted(d for d in (parse_iso_date(v) for v in (values or [])) if d)
    if not parsed:
        return None, None
    upcoming = [d for d in parsed if d.date() >= today]
    return (upcoming[0] if upcoming else parsed[-1]), parsed[-1]


def derive_status(sedia_status: Optional[str], opening: Optional[dt.datetime],
                  final_deadline: Optional[dt.datetime], today: dt.date) -> str:
    """forthcoming | open | closed | unknown, with the DATES winning over SEDIA.

    SEDIA's status field lags its own dates: topics opening on 15 Sep were still
    'forthcoming' in the 04:00 UTC sync, and 'open' rows kept deadlines that had
    passed. A deadline DATE equal to today still counts as open, because SEDIA
    stores the day at 00:00 while the real cut-off is 17:00 Brussels time.
    """
    if final_deadline is not None and final_deadline.date() < today:
        return "closed"
    if opening is not None and final_deadline is not None:
        return "forthcoming" if opening.date() > today else "open"
    # No deadline: nothing to derive from. A prior information notice or a
    # rolling call can be 'forthcoming' long after its publication date, so the
    # opening date alone must not promote it to 'open'.
    return sedia_status or "unknown"


def first_or_none(arr) -> Optional[Any]:
    if isinstance(arr, list) and arr:
        return arr[0]
    return None


def parse_iso_date(s: str) -> Optional[dt.datetime]:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00").replace("+0000", "+00:00").replace(".000", ""))
    except Exception:  # noqa: BLE001
        return None


TENDER_PORTAL_BASE = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/tender-details"


def _lead_authority(md: Dict[str, Any]) -> Optional[str]:
    """The buying institution of a call for tenders.

    `cftLeadContractingAuthorityCode` is a list of JSON strings such as
    '[{"name":"European Union Agency for Fundamental Rights","isLeadAuthority":true}]'.
    Falls back to the DG / agency label of `cftPartyLegalEntityId`.
    """
    for raw in md.get("cftLeadContractingAuthorityCode") or []:
        try:
            parties = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            continue
        if isinstance(parties, dict):
            parties = [parties]
        names = [p.get("name") for p in parties or [] if isinstance(p, dict) and p.get("name")]
        lead = [p.get("name") for p in parties or []
                if isinstance(p, dict) and p.get("isLeadAuthority") and p.get("name")]
        if lead or names:
            return (lead or names)[0].strip()
    party = str(first_or_none(md.get("cftPartyLegalEntityId")) or "")
    return _PARTY_LABELS.get(party) or None


def _to_number(value) -> Optional[float]:
    try:
        return float(str(value).strip()) if value not in (None, "") else None
    except ValueError:
        return None


def normalise_row(result: Dict[str, Any], today: Optional[dt.date] = None) -> Optional[Dict[str, Any]]:
    today = today or dt.date.today()
    md = result.get("metadata") or {}
    topic_id = first_or_none(md.get("identifier"))
    title = first_or_none(md.get("title")) or result.get("content")
    if not topic_id or not title:
        return None
    record_type = str(first_or_none(md.get("type")) or "")
    is_tender = record_type in TENDER_TYPES or str(topic_id).endswith(("-CN", "-PIN"))
    description_html = (first_or_none(md.get("descriptionByte"))
                        or first_or_none(md.get("description")) or "")
    short_html = (description_html or "").split("</p>", 1)[0] + "</p>" if "</p>" in description_html else description_html[:600]

    status_code = first_or_none(md.get("status"))
    sedia_status = STATUS_MAP.get(str(status_code))

    deadline, final_deadline = pick_deadlines(md.get("deadlineDate"), today)
    published = parse_iso_date(first_or_none(md.get("startDate"))) or parse_iso_date(first_or_none(md.get("es_SortDate")))
    status = derive_status(sedia_status, published, final_deadline, today)
    types = md.get("typesOfAction") or []
    type_of_action = types[0] if types else None

    keywords = md.get("keywords") or []
    if not isinstance(keywords, list):
        keywords = [keywords]

    portal_url = f"{TENDER_PORTAL_BASE if is_tender else PORTAL_BASE}/{topic_id}"
    documents_url = first_or_none(md.get("url")) or first_or_none(md.get("esST_URL"))

    call_id = first_or_none(md.get("callIdentifier"))
    # SEDIA publishes the SAME topic once per EU language. fetch_sedia_page now
    # asks for English only, but the language is still carried so a caller that
    # opts into every language can prefer English.
    record_lang = (first_or_none(md.get("language")) or "").lower()

    row = {
        "record_lang": record_lang,
        "record_type": record_type,
        "is_tender": is_tender,
        "topic_id": topic_id,
        "call_id": call_id,
        # The programme NAME ("Horizon Europe (HORIZON)"), never programmePeriod.
        "programme": None if is_tender else programme_label(md, topic_id),
        "title": title,
        "short_summary": html_strip(short_html, 600),
        "description": html_strip(description_html, 8000),
        "status": status,
        "type_of_action": type_of_action,
        "deadline": deadline,
        "deadline_secondary": final_deadline if final_deadline and final_deadline != deadline else None,
        "indicative_budget": None,
        "budget_currency": "EUR",
        "source_url": portal_url,
        "documents_url": documents_url,
        "keywords": keywords,
        "target_audience": None,
        "published_at": published,
    }
    if is_tender:
        ct = str(first_or_none(md.get("contractType")) or "")
        row.update({
            "contracting_authority": _lead_authority(md),
            "contract_type": _CONTRACT_TYPE_LABELS.get(ct) or type_of_action,
            "indicative_budget": _to_number(first_or_none(md.get("cftEstimatedOverallContractAmount"))),
            "budget_currency": first_or_none(md.get("cftEstimatedOverallContractCurrency")) or "EUR",
        })
    return row


def upsert(cur, row: Dict[str, Any]) -> None:
    cur.execute(
        """
        INSERT INTO funding_opportunities
            (topic_id, call_id, programme, title, short_summary, description, status,
             type_of_action, deadline, deadline_secondary, indicative_budget,
             budget_currency, source_url, documents_url, keywords, target_audience,
             published_at, scraped_at, last_updated)
        VALUES (%(topic_id)s, %(call_id)s, %(programme)s, %(title)s, %(short_summary)s,
                %(description)s, %(status)s, %(type_of_action)s, %(deadline)s,
                %(deadline_secondary)s, %(indicative_budget)s, %(budget_currency)s,
                %(source_url)s, %(documents_url)s, %(keywords)s, %(target_audience)s,
                %(published_at)s, NOW(), NOW())
        ON CONFLICT (topic_id) DO UPDATE SET
            call_id = EXCLUDED.call_id,
            title = EXCLUDED.title,
            short_summary = EXCLUDED.short_summary,
            description = EXCLUDED.description,
            -- The SEDIA search record carries no status field at all, so
            -- normalise_row falls back to 'unknown' on every row. Assigning
            -- that unconditionally overwrote a known 'open' or 'closed' with
            -- 'unknown' on every nightly run, which is how twelve LIFE 2025
            -- calls ended up statusless, and it would have undone
            -- close_expired_calls.py the same night it ran. Only a real status
            -- may replace a real status.
            status = CASE WHEN EXCLUDED.status = 'unknown'
                          THEN funding_opportunities.status ELSE EXCLUDED.status END,
            type_of_action = COALESCE(EXCLUDED.type_of_action, funding_opportunities.type_of_action),
            -- The programme NAME. Until 15 Sep 2026 this column held the programme
            -- PERIOD ("2021 - 2027") and was never updated on conflict, so the
            -- period is cleared here whenever no name is available.
            programme = COALESCE(EXCLUDED.programme,
                                 CASE WHEN funding_opportunities.programme ~ '^ *[0-9]{4} *- *[0-9]{4} *$'
                                      THEN NULL ELSE funding_opportunities.programme END),
            published_at = COALESCE(EXCLUDED.published_at, funding_opportunities.published_at),
            deadline_secondary = COALESCE(EXCLUDED.deadline_secondary, funding_opportunities.deadline_secondary),
            -- Never let an absent field erase a present one. The SEDIA search
            -- record carries no deadline for many topics, so EXCLUDED.deadline
            -- is NULL and a plain assignment wiped the real date: one run
            -- cleared the deadline on all 31 LIFE 2026 calls, which is the
            -- single most important thing a funding feed knows. Same reasoning
            -- for the budget, which the search API never carries at all and
            -- which is filled in from the portal's topic page.
            deadline = COALESCE(EXCLUDED.deadline, funding_opportunities.deadline),
            keywords = EXCLUDED.keywords,
            -- scraped_at on the conflict path too, so "when did we last SEE
            -- this call" is answerable. Without it scraped_at only ever
            -- recorded a topic's first sighting, so the table looked frozen
            -- whether the job was healthy or dead and there was no way to
            -- tell the two apart from the data.
            scraped_at = NOW(),
            last_updated = NOW()
        """,
        row,
    )


def is_call_for_tenders(row: Dict[str, Any]) -> bool:
    """True when a SEDIA row is a call for TENDERS, not a call for proposals.

    SEDIA returns both through the same search index. The discriminator is the
    record `type` ("0" = Tender); a UUID identifier suffixed "-CN" (contract
    notice) or "-PIN" (prior information notice) is the fallback for callers that
    built the row without it.
    """
    if row.get("is_tender") is not None:
        return bool(row["is_tender"])
    return str(row.get("topic_id") or "").endswith(("-CN", "-PIN"))


def upsert_ft_tenders(cur, row: Dict[str, Any]) -> None:
    """Write a SEDIA call-for-tenders row into ft_calls_for_tenders.

    This table is what the Tenderator's "Calls for tenders" chip reads, and it
    had no writer at all: its 386 rows were a one-off seed from 31 Dec 2025 and
    every one had closed, so the chip could only ever render an empty list. The
    calls themselves were arriving on every run and being filed into
    ft_calls_for_proposals, which is the wrong table and the wrong shape.
    """
    payload = {
        "tender_reference": row["topic_id"],
        "title": row.get("title") or row["topic_id"],
        "description": row.get("description"),
        "status": row.get("status"),
        "deadline": row.get("deadline"),
        # The BUYER. This was row["programme"], which held the programme period,
        # so 46 of 46 SEDIA tenders named "2014 - 2020" as their contracting
        # authority. The period is never a buyer: store NULL rather than that.
        "contracting_authority": (None if is_programme_period(row.get("contracting_authority"))
                                  else row.get("contracting_authority")),
        "contract_type": row.get("contract_type") or row.get("type_of_action"),
        "estimated_value": row.get("indicative_budget"),
        "value_currency": row.get("budget_currency"),
        # source_url is NOT NULL; the portal URL is always derivable.
        "source_url": row.get("source_url") or "",
        "documents_url": row.get("documents_url"),
        "published_at": row.get("published_at"),
    }
    cur.execute(
        """
        INSERT INTO ft_calls_for_tenders
            (tender_reference, title, description, status, deadline,
             contracting_authority, contract_type, estimated_value,
             value_currency, source_url, documents_url, published_at,
             is_test, scraped_at, last_updated)
        VALUES (%(tender_reference)s, %(title)s, %(description)s, %(status)s,
                %(deadline)s, %(contracting_authority)s, %(contract_type)s,
                %(estimated_value)s, %(value_currency)s, %(source_url)s,
                %(documents_url)s, %(published_at)s, FALSE, NOW(), NOW())
        ON CONFLICT (tender_reference) DO UPDATE SET
            title = EXCLUDED.title,
            description = EXCLUDED.description,
            status = CASE WHEN EXCLUDED.status IS NULL OR EXCLUDED.status = 'unknown'
                          THEN ft_calls_for_tenders.status ELSE EXCLUDED.status END,
            deadline = COALESCE(EXCLUDED.deadline, ft_calls_for_tenders.deadline),
            contracting_authority = COALESCE(EXCLUDED.contracting_authority,
                CASE WHEN ft_calls_for_tenders.contracting_authority ~ '^ *[0-9]{4} *- *[0-9]{4} *$'
                     THEN NULL ELSE ft_calls_for_tenders.contracting_authority END),
            contract_type = COALESCE(EXCLUDED.contract_type, ft_calls_for_tenders.contract_type),
            estimated_value = COALESCE(EXCLUDED.estimated_value, ft_calls_for_tenders.estimated_value),
            value_currency = COALESCE(EXCLUDED.value_currency, ft_calls_for_tenders.value_currency),
            source_url = COALESCE(NULLIF(EXCLUDED.source_url, ''), ft_calls_for_tenders.source_url),
            published_at = COALESCE(EXCLUDED.published_at, ft_calls_for_tenders.published_at),
            documents_url = COALESCE(EXCLUDED.documents_url, ft_calls_for_tenders.documents_url),
            scraped_at = NOW(),
            last_updated = NOW()
        """,
        payload,
    )


def upsert_ft_calls(cur, row: Dict[str, Any]) -> None:
    """Mirror the same row into the sibling ft_calls_for_proposals table.

    Schema parity: ft_calls_for_proposals has `framework_programme` where
    funding_opportunities has `programme`, and no `short_summary` field.
    All other columns line up 1:1, so we just rename + drop.
    """
    payload = dict(row)
    payload["framework_programme"] = payload.pop("programme", None)
    payload.pop("short_summary", None)
    cur.execute(
        """
        INSERT INTO ft_calls_for_proposals
            (topic_id, call_id, framework_programme, title, description, status,
             type_of_action, deadline, deadline_secondary, indicative_budget,
             budget_currency, source_url, documents_url, keywords, target_audience,
             published_at, scraped_at, last_updated)
        VALUES (%(topic_id)s, %(call_id)s, %(framework_programme)s, %(title)s,
                %(description)s, %(status)s, %(type_of_action)s, %(deadline)s,
                %(deadline_secondary)s, %(indicative_budget)s, %(budget_currency)s,
                %(source_url)s, %(documents_url)s, %(keywords)s, %(target_audience)s,
                %(published_at)s, NOW(), NOW())
        ON CONFLICT (topic_id) DO UPDATE SET
            call_id = EXCLUDED.call_id,
            title = EXCLUDED.title,
            -- A changed title invalidates both the detected language and any
            -- sidecar translation derived from the old one. Without this reset,
            -- correcting a German title to the portal's own English left
            -- detected_lang='de' behind, and the Tenderator's translation
            -- overlay then covered the correct English with a machine
            -- translation of the German, em-dash included.
            detected_lang = CASE WHEN EXCLUDED.title IS DISTINCT FROM ft_calls_for_proposals.title
                                 THEN NULL ELSE ft_calls_for_proposals.detected_lang END,
            description = EXCLUDED.description,
            -- The SEDIA search record carries no status field at all, so
            -- normalise_row falls back to 'unknown' on every row. Assigning
            -- that unconditionally overwrote a known 'open' or 'closed' with
            -- 'unknown' on every nightly run, which is how twelve LIFE 2025
            -- calls ended up statusless, and it would have undone
            -- close_expired_calls.py the same night it ran. Only a real status
            -- may replace a real status.
            status = CASE WHEN EXCLUDED.status = 'unknown'
                          THEN ft_calls_for_proposals.status ELSE EXCLUDED.status END,
            type_of_action = COALESCE(EXCLUDED.type_of_action, ft_calls_for_proposals.type_of_action),
            -- See funding_opportunities.programme: the period is not a programme.
            framework_programme = COALESCE(EXCLUDED.framework_programme,
                CASE WHEN ft_calls_for_proposals.framework_programme ~ '^ *[0-9]{4} *- *[0-9]{4} *$'
                     THEN NULL ELSE ft_calls_for_proposals.framework_programme END),
            published_at = COALESCE(EXCLUDED.published_at, ft_calls_for_proposals.published_at),
            deadline_secondary = COALESCE(EXCLUDED.deadline_secondary, ft_calls_for_proposals.deadline_secondary),
            deadline = COALESCE(EXCLUDED.deadline, ft_calls_for_proposals.deadline),
            keywords = EXCLUDED.keywords,
            -- scraped_at on the conflict path too, so "when did we last SEE
            -- this call" is answerable. Without it scraped_at only ever
            -- recorded a topic's first sighting, so the table looked frozen
            -- whether the job was healthy or dead and there was no way to
            -- tell the two apart from the data.
            scraped_at = NOW(),
            last_updated = NOW()
        """,
        payload,
    )


# Default prefix-anchored SEDIA queries. Each entry narrows the 4M-row SEDIA
# index to one programme's topic-call documents. text='*' returns ~4M rows
# dominated by SEDIA_FAQ + SEDIA_PERSON noise and yields ~0 valid topic rows;
# prefix queries (proven shape, mirrored from ingest_ft_programme_calls.py)
# return only matching call/topic rows.
DEFAULT_QUERIES: list[str] = [
    "HORIZON-",
    "HORIZON-CL",
    "EIC-",
    "EIE-",
    "DIGITAL-",
    "CEF-",
    "ERASMUS-",
    "CERV-",
    "CREA-",
    "EU4H-",
    "LIFE-",
    "JUST-",
    "AMIF-",
    "BMVI-",
    "ISF-",
    "INNOVFUND-",
    "ESF-",
    "EUDF-",
    "EISMEA",
]


def _write(cur, row: Dict[str, Any], write_ft: bool) -> None:
    """One row, inside a savepoint so a bad row cannot roll back its neighbours.

    Before this, a DB error called conn.rollback(), silently discarding every
    upsert since the last page commit while rows_written had already counted them.
    """
    cur.execute("SAVEPOINT sedia_row")
    try:
        if is_call_for_tenders(row):
            # A call for tenders is not a funding opportunity; it belongs to
            # ft_calls_for_tenders only.
            if write_ft:
                upsert_ft_tenders(cur, row)
        else:
            upsert(cur, row)
            if write_ft:
                upsert_ft_calls(cur, row)
        cur.execute("RELEASE SAVEPOINT sedia_row")
    except Exception:
        cur.execute("ROLLBACK TO SAVEPOINT sedia_row")
        raise


def iter_structured(query: Dict[str, Any], page_size: int = 100, max_pages: int = 60,
                    pause: float = 0.4):
    """Every record of a filtered SEDIA query, English only, page by page.

    Yields (page_number, results). Stops on an empty page, a short page, or a
    failed fetch; a failed fetch yields (page, None) so the caller can count it.
    """
    for page in range(1, max_pages + 1):
        data = fetch_sedia_page(page, page_size=page_size, query=query)
        if not data:
            # One retry: under load SEDIA times out on the odd page, and a lost
            # page silently drops up to 100 calls.
            time.sleep(5)
            data = fetch_sedia_page(page, page_size=page_size, query=query)
        if not data:
            yield page, None
            return
        results = data.get("results") or []
        yield page, results
        if len(results) < page_size:
            return
        time.sleep(pause)


def prefer(existing: Optional[Dict[str, Any]], row: Dict[str, Any]) -> Dict[str, Any]:
    """Pick the better of two records for one identifier.

    SEDIA can hold several type-1 records for one topic (ERASMUS-EDU-2022-ECHE-CERT-FP
    has two, with different deadline lists). Prefer a real status, then the later
    final deadline.
    """
    if existing is None:
        return row
    def key(r):
        final = r.get("deadline_secondary") or r.get("deadline")
        return (r.get("status") != "unknown", final.timestamp() if final else 0.0)
    return row if key(row) > key(existing) else existing


def refresh_status_from_dates(cur, today_sql: str = "CURRENT_DATE") -> Dict[str, int]:
    """Date-derived status for EVERY row, including rows SEDIA no longer returns.

    Mirrors derive_status(): a deadline before today closes the call; a
    forthcoming call whose opening date has arrived and whose deadline has not
    passed is open. Rows without a deadline are never guessed at.
    """
    changed = {}
    for table in ("ft_calls_for_proposals", "funding_opportunities", "ft_calls_for_tenders"):
        final = ("GREATEST(deadline, COALESCE(deadline_secondary, deadline))"
                 if table != "ft_calls_for_tenders" else "deadline")
        cur.execute(f"""
            UPDATE {table} SET status = 'closed', last_updated = now()
             WHERE status IN ('open', 'forthcoming', 'unknown')
               AND deadline IS NOT NULL AND ({final})::date < {today_sql}""")
        closed = cur.rowcount
        cur.execute(f"""
            UPDATE {table} SET status = 'open', last_updated = now()
             WHERE status IN ('forthcoming', 'unknown')
               AND published_at IS NOT NULL AND published_at::date <= {today_sql}
               AND deadline IS NOT NULL AND ({final})::date >= {today_sql}""")
        changed[table] = closed + cur.rowcount
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=2000,
                    help="Max rows for the legacy prefix-discovery pass (default 2000). "
                         "The open/forthcoming and refresh passes are not capped.")
    ap.add_argument("--apply", action="store_true", help="Write to DB. Default is dry-run.")
    ap.add_argument("--page-size", type=int, default=100)
    ap.add_argument("--status", choices=["forthcoming", "open", "closed", "any"], default="any")
    ap.add_argument("--text", default=None,
                    help="SEDIA full-text query for the prefix-discovery pass. If "
                         "omitted, iterates over the DEFAULT_QUERIES programme prefixes.")
    ap.add_argument("--write-ft", action="store_true",
                    help="Also write ft_calls_for_proposals and ft_calls_for_tenders "
                         "(the tables the Tenderator and /api/v2/funding/ft-* read).")
    ap.add_argument("--discover", action="store_true",
                    help="Also run the legacy full-text prefix queries to find closed "
                         "historical topics never stored (slow; implied by --text).")
    ap.add_argument("--dump-json", default=None,
                    help="Write the normalised rows to this JSON file (for verification).")
    ap.add_argument("--skip-refresh", action="store_true",
                    help="Skip re-reading every stored topic by identifier.")
    args = ap.parse_args()

    db = get_env("DATABASE_URL")
    if not db:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)

    n_labels = load_programme_labels()
    print(f"[INFO] programme labels from SEDIA facet: {n_labels} "
          f"(static fallback {len(_STATIC_PROGRAMME_LABELS)})")

    stats = {"fetched": 0, "written": 0, "errors": 0, "fetch_failures": 0}
    # identifier -> best row seen this run
    rows: Dict[str, Dict[str, Any]] = {}

    def collect(results, allow_tenders: bool) -> int:
        n = 0
        for r in results:
            row = normalise_row(r)
            if row is None:
                continue
            if row["record_type"] and row["record_type"] not in GRANT_TYPES + TENDER_TYPES + ["2"]:
                continue  # type 6 update records and other noise
            if row["is_tender"] and not allow_tenders:
                continue
            rows[row["topic_id"]] = prefer(rows.get(row["topic_id"]), row)
            n += 1
        return n

    # Pass 1: every OPEN or FORTHCOMING call topic, English, uncapped (~1,400).
    # This is the pass that answers "what can I apply to"; it used to depend on
    # a 500-row budget shared with 19 full-text prefix queries.
    for label, types, allow_tenders in (("grants", GRANT_TYPES, False),
                                        ("tenders", TENDER_TYPES, True)):
        if label == "tenders" and not args.write_ft:
            continue
        q = {"bool": {"must": [{"terms": {"type": types}},
                               {"terms": {"status": OPEN_STATUS_CODES}}]}}
        got = 0
        for page, results in iter_structured(q, page_size=args.page_size):
            if results is None:
                stats["fetch_failures"] += 1
                break
            got += collect(results, allow_tenders)
        print(f"[PASS 1] open/forthcoming {label}: {got} records")
        stats["fetched"] += got

    # Pass 2: re-read every topic we already store, by identifier, so titles,
    # programme, dates and status of CLOSED and historical rows get corrected too
    # (the rows pass 1 cannot see). ~20 requests for ~2,000 topics.
    if not args.skip_refresh:
        # Short-lived connection: the SEDIA passes take minutes and the Supabase
        # session pooler is shared with production, so no connection is held
        # across network work.
        conn = psycopg2.connect(db)
        try:
            cur = conn.cursor()
            # Only rows that can still be wrong: anything not closed, plus closed
            # rows still carrying a programme PERIOD, a non-English title or no
            # status. Settled closed rows do not change upstream, and re-reading all
            # ~2,000 daily pushed the job past its cron timeout (SEDIA ~10 s/page).
            cur.execute("""
                SELECT topic_id FROM ft_calls_for_proposals
                 WHERE NOT is_test AND (status IS DISTINCT FROM 'closed'
                       OR framework_programme ~ '^ *[0-9]{4} *- *[0-9]{4} *$'
                       OR COALESCE(detected_lang, 'en') <> 'en')
                UNION SELECT topic_id FROM funding_opportunities
                 WHERE NOT is_test AND (status IS DISTINCT FROM 'closed'
                       OR programme ~ '^ *[0-9]{4} *- *[0-9]{4} *$')
                UNION SELECT tender_reference FROM ft_calls_for_tenders
                 WHERE tender_reference ~ '-(CN|PIN)$'
                   AND (status IS DISTINCT FROM 'closed'
                        OR contracting_authority ~ '^ *[0-9]{4} *- *[0-9]{4} *$')""")
            stored = sorted({r[0] for r in cur.fetchall()} - set(rows))
        finally:
            conn.close()
        got = 0
        for i in range(0, len(stored), 100):
            batch = stored[i:i + 100]
            q = {"bool": {"must": [{"terms": {"identifier": batch}},
                                   {"terms": {"type": GRANT_TYPES + TENDER_TYPES + ["2"]}}]}}
            for page, results in iter_structured(q, page_size=100, max_pages=5, pause=0.3):
                if results is None:
                    stats["fetch_failures"] += 1
                    break
                got += collect(results, allow_tenders=args.write_ft)
        print(f"[PASS 2] refresh of {len(stored)} stored identifiers: {got} records")
        stats["fetched"] += got

    # Pass 3: legacy prefix discovery of topics not yet stored, capped by --limit.
    status_filter = None
    if args.status != "any":
        status_filter = next((k for k, v in STATUS_MAP.items() if v == args.status), None)
    # Opt-in: pass 1 already sees every call while it is forthcoming or open, so a
    # new call can no longer be missed without it, and SEDIA answers ~10 s a page.
    queries = [args.text] if args.text else (DEFAULT_QUERIES if args.discover else [])
    discovered = 0
    for query in queries:
        if discovered >= args.limit:
            break
        q = {"bool": {"must": [{"terms": {"type": GRANT_TYPES}}]}}
        for page in range(1, 11):
            data = fetch_sedia_page(page, page_size=args.page_size, status_filter=status_filter,
                                    text=query, query=q)
            results = (data or {}).get("results") or []
            if not data:
                stats["fetch_failures"] += 1
            if not results:
                break
            before = len(rows)
            collect(results, allow_tenders=False)
            discovered += len(rows) - before
            if len(rows) == before or discovered >= args.limit:
                break
            time.sleep(0.4)
    print(f"[PASS 3] prefix discovery: {discovered} new identifiers")

    if args.dump_json:
        with open(args.dump_json, "w") as fh:
            json.dump(rows, fh, default=str, ensure_ascii=False, indent=1)
    if args.apply and rows:
        conn = psycopg2.connect(db)
        try:
            cur = conn.cursor()
            for tid, row in sorted(rows.items()):
                try:
                    _write(cur, row, args.write_ft)
                    stats["written"] += 1
                except Exception as exc:  # noqa: BLE001
                    stats["errors"] += 1
                    print(f"    [DB ERR] {tid}: {type(exc).__name__}: {str(exc)[:160]}")
            conn.commit()
            changed = refresh_status_from_dates(cur)
            conn.commit()
            print(f"[STATUS] date-derived status changes: {changed}")
        finally:
            conn.close()

    by_status: Dict[str, int] = {}
    for row in rows.values():
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
    print(f"\n[DONE] identifiers={len(rows)} tenders={sum(1 for r in rows.values() if r['is_tender'])} "
          f"by_status={by_status} written={stats['written']} errors={stats['errors']} "
          f"fetch_failures={stats['fetch_failures']} apply={args.apply}")

    # Silence is not success: an empty run or a run that could not write must not exit 0.
    if not rows:
        print("[ERROR] SEDIA returned no call records; nothing was ingested")
        sys.exit(2)
    if args.apply and stats["errors"]:
        print(f"[ERROR] {stats['errors']} row(s) failed to write")
        sys.exit(3)
    if stats["fetch_failures"]:
        print(f"[ERROR] {stats['fetch_failures']} SEDIA page fetch(es) failed after retry; "
              "the run is incomplete")
        sys.exit(4)


if __name__ == "__main__":
    main()

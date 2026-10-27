"""
The F&T Portal's Partner Search, read as its own page reads it (27 Oct 2026, funding standard Phase 1 C2).

The portal's Partner Search page asks the EC search API (api.tech.ec.europa.eu/search-api) with the
key `modules.sedia.personProfileApiKey` of its public configuration (portal/assets/openid-login-config.json,
sent to every visitor). The key is read from that file at each run, never stored: Victor's decision of
27 Oct 2026. The index holds organisation profiles (type ORGANISATION, 867,602; 11,537 with Partner
Search on 27 Oct), person profiles (type PERSON) and announcements (type ANNOUNCEMENT: 358,356 by
organisations, 10,195 by persons). Only organisations are read: never a person's profile or a
person's announcement.

What is not read, and why:
- An announcement's text is its first 500 characters, as the index holds it; the full text
  (partnerSearch/announcementDetail.json) needs an EU Login.
- The index's `validationStatus` (Open / Forthcoming / Closed) is the topic's status when the
  announcement was indexed: 2019 announcements still say Forthcoming. It is not kept; the topic's
  status comes from ft_calls_for_proposals.
- A profile's own `announcements` list is absent on 97 of 100 sampled profiles, and its
  `noOfPartnerSearch` differs from the index (DIN: 188 against 254 announcements): the
  announcements are read as documents.
- Country and organisation type come as codes (20000883, 31079048) or as English labels: both are
  read through the index's own facet labels at each run.

E-mail addresses, ORCIDs, LinkedIn profile links and telephone numbers are removed from the texts:
an organisation's announcement often carries its contact person's own address.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from datetime import date, datetime, timedelta
from typing import Dict, Iterator, List, Optional, Tuple

import requests

from services.funding.countries import country_code

CONFIG_URL = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/assets/openid-login-config.json"
PORTAL_ORG = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/how-to-participate/org-details/{pic}"
PAGE_SIZE = 100
CAP = 10_000                     # the index serves at most 10,000 results per query (page x size)
TEXT_LIMIT = 500                 # the index's announcementSummary is cut here
FIRST_DAY = date(2018, 1, 1)     # the earliest announcement requested (measured 27 Oct 2026: 2018)

ANNOUNCEMENT_FIELDS = ["announcementId", "pic", "name", "country", "organisationType", "expertise", "topics",
                       "title", "requestedDate", "announcementSummary", "es_SortDate"]
PROFILE_FIELDS = ["pic", "name", "city", "country", "organisationType", "noOfPartnerSearch", "noOfProjects",
                  "topics", "hasPartnerSearch"]
_ORG_ANNOUNCEMENTS = [{"terms": {"type": ["ANNOUNCEMENT"]}}, {"terms": {"announcementType": ["ORGANISATION"]}}]
_PROFILES = [{"terms": {"type": ["ORGANISATION"]}}, {"terms": {"hasPartnerSearch": ["true"]}}]
_EXPERTISE = {"Expertise_offer": "offer", "Expertise_request": "request"}

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# A researcher's ORCID and a person's LinkedIn page identify that person (27 Oct 2026: 837 of 1,339
# announcements of one week carried an e-mail address, most on gmail.com; ORCIDs were seen too).
_ORCID = re.compile(r"(?:https?://)?(?:orcid\.org/)?\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b")
_LINKEDIN = re.compile(r"(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/in/[^\s),;]+", re.I)
# A number written as a telephone: an international prefix, or after a telephone label. Budgets,
# years and topic codes ("2021-2027", "HORIZON-CL5-2024-D4-02-05") carry neither.
_PHONE = re.compile(r"(?:(?<![\w+])(?:\+|00)\s?\d[\d\s()./-]{6,}\d)"
                    r"|(?:(?i:\b(?:tel|phone|mobile|mob|t[ée]l[ée]fono|telefon|t[ée]l)\b)\.?\s*[:.]?\s*[+(]?\d[\d\s()./-]{6,}\d)")
REMOVED = "[removed]"


def redact(text: Optional[str]) -> Optional[str]:
    """The text without e-mail addresses, ORCIDs, LinkedIn profiles and telephone numbers."""
    if not text:
        return text
    for pattern in (_EMAIL, _LINKEDIN, _ORCID, _PHONE):
        text = pattern.sub(REMOVED, text)
    return text


class PartnerSearch:
    """The portal's search index, with its key and facet labels read once per run."""

    def __init__(self, session: requests.Session, sleep: float = 0.3):
        self.session, self.sleep = session, sleep
        cfg = session.get(CONFIG_URL, timeout=60)
        cfg.raise_for_status()
        sedia = cfg.json()["modules"]["sedia"]
        self._search = sedia["corporateSearchUrl"] + sedia["personProfileApiKey"]
        self._facet = self._search.replace("/rest/search", "/rest/facet", 1)
        self._labels: Dict[str, Dict[str, str]] = {}

    @staticmethod
    def _multipart(parts: dict) -> Tuple[bytes, str]:
        b = uuid.uuid4().hex
        body = b"".join(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"blob\"\r\n"
                        f"Content-Type: application/json\r\n\r\n".encode() + json.dumps(v).encode() + b"\r\n"
                        for k, v in parts.items()) + f"--{b}--\r\n".encode()
        return body, f"multipart/form-data; boundary={b}"

    def _post(self, url: str, parts: dict) -> dict:
        for attempt in range(4):
            body, ctype = self._multipart(parts)
            r = self.session.post(url, data=body, headers={"Content-Type": ctype}, timeout=120)
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            time.sleep(self.sleep)
            return r.json()
        raise RuntimeError("unreachable")

    def search(self, must: list, page: int = 1, size: int = PAGE_SIZE, fields: Optional[list] = None) -> dict:
        parts = {"query": {"bool": {"must": must}}, "sort": {"field": "es_SortDate", "order": "ASC"},
                 "languages": ["en"]}
        if fields:
            parts["displayFields"] = fields
        return self._post(f"{self._search}&text=***&pageSize={size}&pageNumber={page}", parts)

    def total(self, must: list) -> int:
        return int(self.search(must, size=1)["totalResults"])

    def labels(self, field: str) -> Dict[str, str]:
        """The index's own label for each code of a field (country 20000883 -> Spain)."""
        if field not in self._labels:
            out = {}
            for must in (_ORG_ANNOUNCEMENTS, _PROFILES):
                d = self._post(f"{self._facet}&text=***", {"query": {"bool": {"must": must}}, "facets": [field],
                                                          "languages": ["en"]})
                # The facet service answers every facet whatever is asked: keep this field's.
                for f in d.get("facets", []):
                    if f.get("name") != field:
                        continue
                    for v in f.get("values", []):
                        out.setdefault(str(v.get("rawValue")), v.get("value"))
            self._labels[field] = out
        return self._labels[field]

    def _pages(self, must: list, fields: list) -> Iterator[dict]:
        first = self.search(must, fields=fields)
        total = int(first["totalResults"])
        yield {"total": total, "results": first.get("results", [])}
        for page in range(2, (min(total, CAP) + PAGE_SIZE - 1) // PAGE_SIZE + 1):
            yield {"total": total, "results": self.search(must, page=page, fields=fields).get("results", [])}

    def slices(self, start: date, end: date) -> List[Tuple[date, date, int]]:
        """Requested-date ranges [start, end) of at most CAP announcements each, split in halves."""
        n = self.total(_ORG_ANNOUNCEMENTS + [_requested(start, end)])
        if n <= CAP or (end - start).days <= 1:
            return [(start, end, n)] if n else []
        mid = start + timedelta(days=(end - start).days // 2)
        return self.slices(start, mid) + self.slices(mid, end)

    def announcements(self, start: date, end: date) -> Tuple[List[dict], int, bool]:
        """Every organisation announcement requested in [start, end): (rows, the index's count,
        whether every one was read)."""
        rows, expected, complete = [], 0, True
        for a, b, n in self.slices(start, end):
            expected += n
            seen = 0
            for page in self._pages(_ORG_ANNOUNCEMENTS + [_requested(a, b)], ANNOUNCEMENT_FIELDS):
                for r in page["results"]:
                    row = self.announcement(r.get("metadata") or {})
                    if row:
                        rows.append(row)
                        seen += 1
                if page["total"] > CAP:
                    complete = False          # a one-day slice above the cap: only its first 10,000
            if seen < n:
                complete = False              # the index moved under the read, or a row was unreadable
        return rows, expected, complete

    def profiles(self) -> Tuple[List[dict], int, bool]:
        """Every organisation profile with Partner Search, read country by country (11,537 > the cap)."""
        rows, expected, complete = [], 0, True
        for cc in sorted(self.labels("country")):
            must = _PROFILES + [{"terms": {"country": [cc]}}]
            seen = 0
            for page in self._pages(must, PROFILE_FIELDS):
                if seen == 0:
                    expected += page["total"]
                    if page["total"] > CAP:
                        complete = False
                for r in page["results"]:
                    row = self.profile(r.get("metadata") or {})
                    if row:
                        rows.append(row)
                        seen += 1
        # A profile without a country is in no country's slice.
        overall = self.total(_PROFILES)
        if expected < overall:
            complete = False
        return rows, max(expected, overall), complete

    def _country(self, raw: Optional[str]) -> Optional[str]:
        if not raw:
            return None
        # "Kosovo * UN resolution": the portal's label carries the EU's footnote mark and its subject.
        return country_code(self.labels("country").get(raw, raw).split(" * ")[0])

    def _type(self, raw: Optional[str]) -> Optional[str]:
        return self.labels("organisationType").get(raw, raw) if raw else None

    def announcement(self, md: dict) -> Optional[dict]:
        aid, pic = _one(md, "announcementId"), _one(md, "pic")
        if not aid or not pic:
            return None
        text = _one(md, "announcementSummary")
        topics = [t for t in (md.get("topics") or []) if t]
        return {
            "announcement_id": aid, "pic": pic, "organisation_name": _line(_one(md, "name")),
            "country": self._country(_one(md, "country")), "organisation_type": self._type(_one(md, "organisationType")),
            "expertise": _EXPERTISE.get(_one(md, "expertise") or ""), "topic_id": topics[0] if topics else None,
            "topic_ids": topics, "topic_title": _line(_one(md, "title")), "summary": redact(text),
            "summary_cut": bool(text) and len(text) >= TEXT_LIMIT,
            "requested_date": _day(_one(md, "requestedDate")), "indexed_at": _stamp(_one(md, "es_SortDate")),
            "public_url": PORTAL_ORG.format(pic=pic),
        }

    def profile(self, md: dict) -> Optional[dict]:
        pic = _one(md, "pic")
        if not pic or (_one(md, "hasPartnerSearch") or "").lower() != "true":
            return None
        return {
            "pic": pic, "name": _line(_one(md, "name")), "city": _line(_one(md, "city")),
            "country": self._country(_one(md, "country")), "organisation_type": self._type(_one(md, "organisationType")),
            "projects": _int(_one(md, "noOfProjects")), "portal_announcements": _int(_one(md, "noOfPartnerSearch")),
            "topics": [t for t in (md.get("topics") or []) if t], "public_url": PORTAL_ORG.format(pic=pic),
        }


def _requested(start: date, end: date) -> dict:
    return {"range": {"requestedDate": {"gte": f"{start.isoformat()}T00:00:00.000+0000",
                                        "lt": f"{end.isoformat()}T00:00:00.000+0000"}}}


def _one(md: dict, key: str) -> Optional[str]:
    v = md.get(key)
    if isinstance(v, list):
        v = v[0] if v else None
    return str(v).strip() if v not in (None, "", "NA") else None


def _line(v: Optional[str]) -> Optional[str]:
    return " ".join(v.split()) if v else None


def _day(v: Optional[str]) -> Optional[str]:
    return v[:10] if v and re.match(r"\d{4}-\d{2}-\d{2}", v) else None


def _stamp(v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    try:
        return datetime.strptime(v, "%Y-%m-%dT%H:%M:%S.%f%z").isoformat()
    except ValueError:
        return None


def _int(v: Optional[str]) -> Optional[int]:
    return int(v) if v and v.isdigit() else None


def compose_body(a: dict) -> Tuple[str, str]:
    """An announcement as text and as HTML: who, offering or seeking what, for which topic."""
    import html
    who = a.get("organisation_name") or a.get("pic")
    what = {"offer": "offers its expertise", "request": "seeks expertise"}.get(a.get("expertise") or "", "is looking for partners")
    head = f"{who} ({a.get('country') or '?'}, {a.get('organisation_type') or 'organisation'}) {what}"
    topic = f"Topic {a.get('topic_id')}: {a.get('topic_title')}" if a.get("topic_id") else (a.get("topic_title") or "")
    text = a.get("summary") or ""
    note = " [first 500 characters, as the portal's search shows them]" if a.get("summary_cut") else ""
    txt = "\n".join(x for x in (head, topic, f"Requested {a.get('requested_date')}" if a.get("requested_date") else "",
                                text + note) if x)
    page = "".join(f"<p>{html.escape(x)}</p>" for x in txt.split("\n"))
    return txt, page

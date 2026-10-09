"""OEIL procedure probe: find procedure files by asking for their URL.

OEIL serves one page per procedure at
    https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=YYYY/NNNN(TYPE)
A page that exists answers HTTP 200. One that does not answers HTTP 404 with a JSON body
saying the procedure "does not exist or is in the process of being initiated". The TYPE is
mandatory, so finding every procedure of a year means asking, for each reference number,
the types that can occur in that number's series.

Measured 9 Oct 2026 (experiment, 518 procedures of 2026, every one also in the EP Open Data
list): plain GET, no WAF, server-rendered, about 2.5 requests per second sustained.
Details: memory `project_oeil_url_probe_experiment_2026_10_09`.

Rules built in (do not weaken them):
  * Three outcomes are kept apart: HIT (200 and the page really is that reference), MISS
    (404 WITH OEIL's own message) and an anomaly (anything else). An anomaly raises
    `ProbeBlocked`; it is never read as a miss, because a wall must not look like "nothing".
  * A 404 can mean "not published yet", so a miss is never permanent.
  * Sequential, paced, honest user agent, backoff on 429/5xx, no LLM, no database access.
This module does no I/O except HTTP; the database comparison lives in the script.
"""
from __future__ import annotations

import logging
import re
import time
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import httpx
from bs4 import BeautifulSoup

from services.scrapers.user_agent import BOT_UA

logger = logging.getLogger(__name__)

PROCEDURE_URL = "https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference="
EPOD_PROCEDURES_URL = "https://data.europarl.europa.eu/api/v2/procedures"
NOT_FOUND_MARK = "does not exist"
REF_RE = re.compile(r"^(\d{4})/(\d{4})\(([A-Z]{3})\)$")
R_SUFFIX_RE = re.compile(r"(\d{4})R\(")
# Parliament motions (B10-0069/2026, RC-B10-0069/2026) and adopted texts (T10-0023/2026): term number varies.
MOTION_RE = re.compile(r"\b(?:RC-)?B\d{1,2}-\d{4}/\d{4}\b")
TEXT_RE = re.compile(r"\bT\d{1,2}-\d{4}/\d{4}\b")


# --------------------------------------------------------------------------- bands


@dataclass(frozen=True)
class Band:
    """A series of reference numbers and the procedure types seen in it."""
    name: str
    lo: int
    hi: int
    types: Tuple[str, ...]


# Series observed for 2026 (9 Oct 2026). Numbers fall in series, not one running count:
# Commission-proposal-driven procedures in 0001-0999, Parliament-originated ones from 2000,
# topical resolutions / delegated and implementing acts from about 2500. A year can move
# these; `derive_bands` widens the type sets from what Brubru already holds, and the weekly
# full scan checks the whole thing against the EP Open Data list.
DEFAULT_BANDS: Tuple[Band, ...] = (
    Band("proposals", 1, 799, ("COD", "NLE", "BUD", "CNS", "APP")),
    # 0800-0999 is its own series (appointments, a few consents): seen 2024-2026 as NLE 0801-0906,
    # APP 0900, CNS 0806. Kept apart so the frontier of the proposals series is not hidden by it.
    Band("appointments", 800, 999, ("NLE", "APP", "CNS")),
    Band("parliament", 2000, 2499, ("INI", "IMM", "DEC", "INL", "REG", "BUI", "ACI", "INS")),
    Band("resolutions", 2500, 3999, ("RSP", "DEA", "RPS", "RSO")),
)


def parse_ref(ref: str) -> Optional[Tuple[int, int, str]]:
    m = REF_RE.match(ref or "")
    return (int(m.group(1)), int(m.group(2)), m.group(3)) if m else None


def band_of(number: int, bands: Sequence[Band] = DEFAULT_BANDS) -> Optional[Band]:
    for b in bands:
        if b.lo <= number <= b.hi:
            return b
    return None


def derive_bands(
    known_refs: Iterable[str], bands: Sequence[Band] = DEFAULT_BANDS, *, min_count: int = 2
) -> Tuple[Band, ...]:
    """Add to each band the types Brubru's own data shows in that number range, most frequent first.

    The defaults stay in; observed types only ADD, and only when seen at least `min_count` times in
    the band (one stray ref can be a derived one: Brubru holds some that OEIL answers 404 to, and a
    COD at number 3502 in 2025 would otherwise add COD to every number of the resolutions series).
    """
    seen: Dict[str, Counter] = {b.name: Counter() for b in bands}
    for ref in known_refs:
        p = parse_ref(ref)
        if not p:
            continue
        b = band_of(p[1], bands)
        if b:
            seen[b.name][p[2]] += 1
    out = []
    for b in bands:
        extra = [t for t, c in seen[b.name].most_common() if t not in b.types and c >= min_count]
        ordered = [t for t, _ in seen[b.name].most_common() if t in b.types]
        ordered += [t for t in b.types if t not in ordered]
        out.append(Band(b.name, b.lo, b.hi, tuple(ordered + extra)))
    return tuple(out)


def numbers_by_band(refs: Iterable[str], year: int, bands: Sequence[Band] = DEFAULT_BANDS) -> Dict[str, Set[int]]:
    out: Dict[str, Set[int]] = {b.name: set() for b in bands}
    for ref in refs:
        p = parse_ref(ref)
        if p and p[0] == year:
            b = band_of(p[1], bands)
            if b:
                out[b.name].add(p[1])
    return out


def audit_targets(
    known: Dict[str, Set[int]],
    bands: Sequence[Band],
    *,
    request_budget: int,
    day_ordinal: int,
    frontier_span: int = 40,
) -> List[Tuple[int, Tuple[str, ...]]]:
    """The (number, types) pairs one budgeted audit run should probe.

    Frontier first: the numbers just above the highest one Brubru holds in each band, where
    new procedures appear. Then a rotating window over the numbers Brubru does NOT hold, which
    advances with `day_ordinal` so successive runs cover the whole gap list. A number Brubru
    already holds is never probed: a hit there could not be a gap.
    Worst case a number costs `len(types)` requests; the budget is counted that way.
    """
    targets: List[Tuple[int, Tuple[str, ...]]] = []
    spent = 0
    unknown_by_band: Dict[str, List[int]] = {}
    # The frontier may use at most half the budget, split equally over the bands, so that a small
    # budget still looks above the highest held number in EVERY series (the first band must not
    # eat it all).
    frontier_cap = (request_budget // 2) // max(1, len(bands))
    for b in bands:
        held = known.get(b.name, set())
        top = max(held) if held else b.lo - 1
        band_numbers = min(frontier_span, frontier_cap // len(b.types))
        for n in range(top + 1, top + 1 + band_numbers):
            if n < b.lo:
                continue
            cost = len(b.types)
            if spent + cost > request_budget:
                break
            targets.append((n, b.types))
            spent += cost
        unknown_by_band[b.name] = [n for n in range(b.lo, top + 1) if n not in held]
    remaining = request_budget - spent
    total_unknown_cost = sum(len(unknown_by_band[b.name]) * len(b.types) for b in bands) or 1
    for b in bands:
        cands = unknown_by_band[b.name]
        if not cands or remaining <= 0:
            continue
        share = int(remaining * (len(cands) * len(b.types)) / total_unknown_cost)
        count = min(len(cands), share // len(b.types))
        if count <= 0:
            continue
        start = (day_ordinal * count) % len(cands)
        window = [cands[(start + i) % len(cands)] for i in range(count)]
        targets.extend((n, b.types) for n in sorted(window))
    return targets


# --------------------------------------------------------------------------- parsing


def _txt(el) -> str:
    return " ".join(el.get_text(" ", strip=True).split())


def parse_procedure(html: str) -> dict:
    """Read the fields of an OEIL procedure page; missing fields stay None."""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    out: dict = {"ref": None, "title": None, "type_code": None, "type_label": None, "instrument": None,
                 "extras": [], "subject": None, "status": None, "key_events": [], "motion_refs": [], "text_refs": []}
    ttl = soup.title.get_text(strip=True) if soup.title else ""
    m = re.search(r"Procedure File:\s*(\d{4}/\d{4}\([A-Z]+\))", ttl)
    out["ref"] = m.group(1) if m else None
    h2s = [_txt(h) for h in soup.find_all("h2")]
    if out["ref"] in h2s:
        i = h2s.index(out["ref"])
        for cand in h2s[i + 1:i + 3]:
            if cand and cand != "Basic information":
                out["title"] = cand
                break
    sec = soup.find(id="section1")
    if sec:
        cols = sec.select("div.col-6")
        if cols:
            texts = [(_txt(p), "font-weight-bold" in (p.get("class") or [])) for p in cols[0].find_all("p")]
            if len(texts) > 1:
                m2 = re.match(r"([A-Z]{3})\s*-\s*(.+)", texts[1][0])
                if m2:
                    out["type_code"], out["type_label"] = m2.group(1), m2.group(2)
            extras, j = [], 2
            while j < len(texts) and not texts[j][1]:
                extras.append(texts[j][0])
                j += 1
            out["extras"] = extras
            out["instrument"] = extras[0] if extras else None
            if j < len(texts) and texts[j][0] == "Subject":
                subj, j = [], j + 1
                while j < len(texts) and not texts[j][1]:
                    subj.append(texts[j][0])
                    j += 1
                out["subject"] = " | ".join(subj) or None
        if len(cols) > 1:
            ps = cols[1].find_all("p")
            for k, p in enumerate(ps):
                if _txt(p) == "Status" and k + 1 < len(ps):
                    out["status"] = _txt(ps[k + 1])
    out["key_events"] = _key_events(soup)
    text = " ".join(soup.get_text(" ", strip=True).split())
    out["motion_refs"] = sorted(set(MOTION_RE.findall(text)))
    out["text_refs"] = sorted(set(TEXT_RE.findall(text)))
    return out


def _iso(d: str) -> Optional[str]:
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})$", d or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def _key_events(soup) -> List[dict]:
    """Rows of the 'Key events' table (Date, Event, Reference, Summary) as {date, event, reference}.

    Plain structure read for the feed. The carriage pipeline's own parser
    (services/scrapers/oeil_procedure_parser.py) stays the authority for committees and roles.
    """
    h = next((x for x in soup.find_all("h2") if _txt(x) == "Key events"), None)
    table = h.find_next("table") if h else None
    events: List[dict] = []
    if table is None:
        return events
    for tr in table.find_all("tr"):
        cells = [_txt(c) for c in tr.find_all(["td", "th"])]
        if len(cells) >= 2 and cells[0] != "Date" and cells[1]:
            events.append({"date": _iso(cells[0]), "event": cells[1], "reference": cells[2] if len(cells) > 2 else ""})
    return events


def classify_response(status: int, text: str) -> str:
    """'hit', 'miss' or 'anomaly' from one HTTP answer. Pure."""
    if status == 200:
        return "hit"
    if status == 404 and NOT_FOUND_MARK in (text or ""):
        return "miss"
    return "anomaly"


def cod_instrument(instrument: Optional[str]) -> str:
    """Regulation / Directive / Decision for a COD page's instrument line, else the raw text."""
    s = (instrument or "").strip()
    low = s.lower()
    for name in ("Regulation", "Directive", "Decision"):
        if low.startswith(name.lower()):
            return name
    return f"Other: {s}" if s else "Not stated"


def normalise_label(label: str) -> str:
    """The EP Open Data list spells some labels with an R (0182R(NLE)); OEIL serves them without."""
    return R_SUFFIX_RE.sub(r"\1(", label)


# --------------------------------------------------------------------------- prober


class ProbeBlocked(RuntimeError):
    """A wall or an unexplained answer: stop, report, never retry around it."""


@dataclass
class ProbeResult:
    ref: str
    kind: str                        # 'hit' | 'miss'
    record: Optional[dict] = None


class OeilProber:
    """Sequential, paced prober. `sleep` and `clock` are injectable so tests need no real time."""

    def __init__(
        self,
        *,
        pace: float = 0.35,
        retry_delays: Sequence[float] = (5, 20, 60),
        client: Optional[httpx.Client] = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.pace = pace
        self.retry_delays = tuple(retry_delays)
        self._sleep, self._clock = sleep, clock
        self.client = client or httpx.Client(headers={"User-Agent": BOT_UA}, timeout=30, follow_redirects=True)
        self._last = float("-inf")
        self.requests = 0

    def _pace(self) -> None:
        wait = self.pace - (self._clock() - self._last)
        if wait > 0:
            self._sleep(wait)
        self._last = self._clock()

    def _get(self, ref: str) -> Tuple[int, str]:
        url = PROCEDURE_URL + ref
        for attempt in range(len(self.retry_delays) + 1):
            self._pace()
            try:
                r = self.client.get(url)
                self.requests += 1
                if r.status_code in (429, 500, 502, 503, 504):
                    if attempt < len(self.retry_delays):
                        self._sleep(self.retry_delays[attempt])
                        continue
                    raise ProbeBlocked(f"{ref}: HTTP {r.status_code} after {attempt + 1} tries")
                return r.status_code, r.text
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt < len(self.retry_delays):
                    self._sleep(self.retry_delays[attempt])
                    continue
                raise ProbeBlocked(f"{ref}: {type(exc).__name__} after {attempt + 1} tries") from exc
        raise ProbeBlocked(f"{ref}: no answer")  # pragma: no cover

    def probe(self, ref: str) -> ProbeResult:
        status, text = self._get(ref)
        kind = classify_response(status, text)
        if kind == "miss":
            return ProbeResult(ref, "miss")
        if kind == "hit":
            rec = parse_procedure(text)
            if rec.get("ref") != ref:
                raise ProbeBlocked(f"{ref}: HTTP 200 but the page says {rec.get('ref')!r}")
            return ProbeResult(ref, "hit", rec)
        raise ProbeBlocked(f"{ref}: HTTP {status} without OEIL's not-found message (wall or decoy?)")

    def sweep(self, year: int, number: int, types: Sequence[str]) -> Optional[ProbeResult]:
        """Try the types in order; return the first hit, or None when every type missed."""
        for t in types:
            res = self.probe(f"{year}/{number:04d}({t})")
            if res.kind == "hit":
                return res
        return None


# --------------------------------------------------------------------------- reconcile


def reconcile(hit_refs: Iterable[str], held_refs: Iterable[str]) -> Dict[str, List[str]]:
    """OEIL serves these and Brubru does not hold them / the reverse among the hits' numbers."""
    hits, held = set(hit_refs), set(held_refs)
    return {"on_oeil_not_held": sorted(hits - held), "held_and_on_oeil": sorted(hits & held)}


def split_gaps_by_held_type(gaps: Iterable[str], tracked_refs: Iterable[str]) -> Tuple[List[str], List[str]]:
    """(counted, untracked): a gap counts only when some Brubru procedure table holds that TYPE.

    `tracked_refs` is every ref the procedure tables hold, any year. A type with no ref anywhere
    (2026/2002(INS), a motion of censure, is the first case) has no table meant to hold it, so
    reporting it as a gap would keep an audit degraded for ever on a procedure nothing is meant
    to ingest. Such refs are listed apart. The test is data-driven: the day a table starts holding
    that type, its gaps count again with no code change.
    """
    held_types = {p[2] for p in (parse_ref(r) for r in tracked_refs) if p}
    counted: List[str] = []
    untracked: List[str] = []
    for ref in gaps:
        p = parse_ref(ref)
        (counted if p and p[2] in held_types else untracked).append(ref)
    return counted, untracked


# --------------------------------------------------------------------------- EP Open Data list


def fetch_epod_union(
    year: int,
    *,
    page_sizes: Sequence[int] = (100, 50, 37, 29),
    client: Optional[httpx.Client] = None,
    sleep: Callable[[float], None] = time.sleep,
    page_pause: float = 2.0,
) -> Tuple[Set[str], Optional[int]]:
    """Labels of the EP Open Data /procedures list for `year`, as the UNION of several paging runs.

    Offset paging on this endpoint is unstable (measured 9 Oct 2026, year 2026, reported total
    622): one run returns duplicates and silent gaps (568 to 610 distinct labels depending on page
    size). Only the union of runs with different page sizes reached the reported total. A 200
    whose body has an `error` key (or no `data`) is a failure, never an empty page; a 429 waits
    for Retry-After. Returns (labels, reported_total); labels == total means the list is complete.
    """
    own = client is None
    client = client or httpx.Client(headers={"User-Agent": BOT_UA, "Accept": "application/ld+json"}, timeout=60)
    labels: Set[str] = set()
    total: Optional[int] = None
    try:
        for size in page_sizes:
            offset = 0
            while True:
                body = None
                for attempt in range(6):
                    r = client.get(EPOD_PROCEDURES_URL, params={"year": year, "limit": size, "offset": offset,
                                                                "format": "application/ld+json"})
                    if r.status_code == 429:
                        sleep(int(r.headers.get("Retry-After", "60")))
                        continue
                    if r.status_code != 200:
                        sleep(10)
                        continue
                    data = r.json()
                    if "error" in data or "data" not in data:
                        sleep(15)
                        continue
                    body = data
                    break
                if body is None:
                    raise ProbeBlocked(f"EP Open Data /procedures: no usable page at offset {offset}, size {size}")
                total = body.get("meta", {}).get("total", total)
                page = body["data"]
                labels.update(x["label"] for x in page if x.get("label"))
                offset += size
                if not page or offset >= (total or 0):
                    break
                sleep(page_pause)
            sleep(page_pause)
    finally:
        if own:
            client.close()
    return labels, total

"""Official gazettes the Terraqui / LIFE DPP-TEX client watch depends on: BOE and DOGC.

Why (8 Oct 2026). The client source ledger (backend/data/client_sources/) listed both as
"NOT INGESTED: a gap", with the reason that the Spanish textile and footwear Royal Decree
will be published in the BOE and Catalan waste and circular-economy rules in the DOGC. A
quiet DPP watch was therefore UNPROVEN for exactly the two places a Spanish textile rule
first becomes binding. Both publishers expose open data, no key and no scraping wall:

  * BOE   https://www.boe.es/datosabiertos/api/boe/sumario/YYYYMMDD  (daily summary, JSON;
          Monday to Saturday, a 404 on a day with no issue is an empty day, not an error).
  * DOGC  Generalitat open-data dataset n6hn-rmy7 "Normativa del DOGC": laws, decrees and
          orders published in section 1 since 1977, Catalan and Spanish titles, ELI links.

We keep only items that match the client's remit (the matcher below) plus a count of
everything SCANNED, because "matched nothing" and "read nothing" must stay distinguishable
(a job that stores nothing and exits 0 is the failure this repo has been bitten by before).

Matching is done on accent-folded, lower-cased text so a Catalan "tèxtil" and a Spanish
"textil" are one rule. Two tiers:

  strict  textile, footwear, ecodesign, digital product passport, extended producer
          responsibility. Policy terms match in every BOE section; garment terms in
          sections 1 and 3 and, elsewhere, only next to a rule or consultation word
          (contract awards for uniforms are not the regime).
  broad   waste, packaging, batteries, circular economy, climate, biodiversity, water,
          environmental assessment and liability. Matched only in BOE sections 1 and 3
          (rules and resolutions): the announcements sections carry hundreds of
          project-level notices that would drown the signal.
"""
from __future__ import annotations

import logging
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Iterable, Optional

import requests

logger = logging.getLogger(__name__)

BOE_SUMMARY_URL = "https://www.boe.es/datosabiertos/api/boe/sumario/{ymd}"
DOGC_URL = "https://analisi.transparenciacatalunya.cat/resource/n6hn-rmy7.json"
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/141.0 Safari/537.36"
_TIMEOUT = 40

# BOE sections: 1 general provisions, 2A/2B appointments and competitions, 3 other
# provisions, 5A/5B announcements. Only 1 and 3 get the broad tier.
BROAD_SECTIONS = {"1", "3"}

# POLICY terms are the regime itself and count in every section. GARMENT terms are goods:
# in the announcement sections they mostly name contract awards ("suministro de
# vestuario"), so there they only count next to a rule or a consultation.
POLICY_RX = re.compile(
    r"ecodisen|ecodissen|productos? sostenible|productes? sostenible"
    r"|pasaporte digital|passaport digital|pasaporte de producto|passaport de producte"
    r"|responsabilidad ampliada|responsabilitat ampliada"
)
GARMENT_RX = re.compile(r"textil|calzado|calcat|confeccion|prendas|indumentaria|vestuari|moda sostenible")
RULE_CONTEXT_RX = re.compile(
    r"real decreto|proyecto de|projecte de|decreto|decret|orden |ordre |ley |llei |reglamento|reglament"
    r"|informacion publica|informacio publica|consulta publica|audiencia|audiencia e informacion"
)
NOT_A_RULE_RX = re.compile(r"formalizacion de contratos|licitacion|adjudicacion|anuncio de licitacion|contrato")
# Education and recruitment norms that merely MENTION a garment trade ("curriculum del cicle
# formatiu d'indumentaria", measured on the DOGC, 5 of its first 13 hits): not the regime.
EDUCATION_RX = re.compile(r"curriculum|cicle formatiu|ciclo formativo|ensenyament|ensenanza|formacion profesional|oposicion|proces selectiu")
BROAD_RX = re.compile(
    r"residuo|residu|envase|envasos|economia circular|bateria|acumulador"
    r"|cambio climatico|canvi climatic|ley de clima|llei del canvi"
    r"|biodiversidad|biodiversitat|evaluacion ambiental|avaluacio ambiental"
    r"|responsabilidad medioambiental|responsabilitat mediambiental"
    r"|emisiones industriales|emissions industrials|suelos contaminados|sols contaminats"
    r"|aguas residuales|aigues residuals|marco del agua|marc de l.aigua"
    r"|derechos de emision|drets d.emissio|comercio de derechos"
)


def fold(text: str) -> str:
    """Lower-case and strip accents: 'Tèxtil' and 'TEXTIL' compare equal."""
    nfd = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").lower()


def classify(title: str, section: Optional[str] = None, *, always_broad: bool = False) -> tuple[Optional[str], list[str]]:
    """Return (tier, matched terms) or (None, []) when the item is outside the remit.

    `section` is the BOE section code; DOGC rows are all rules, so they pass
    `always_broad=True`.
    """
    t = fold(title)
    strict = sorted(set(m.group(0) for m in POLICY_RX.finditer(t)))
    garments = sorted(set(m.group(0) for m in GARMENT_RX.finditer(t)))
    if garments and not EDUCATION_RX.search(t):
        in_rules = always_broad or (section in BROAD_SECTIONS)
        if in_rules or (RULE_CONTEXT_RX.search(t) and not NOT_A_RULE_RX.search(t)):
            strict = sorted(set(strict) | set(garments))
    if strict:
        return "strict", strict
    if always_broad or (section in BROAD_SECTIONS):
        broad = sorted(set(m.group(0) for m in BROAD_RX.finditer(t)))
        if broad:
            return "broad", broad
    return None, []


@dataclass
class GazetteItem:
    gazette: str                 # 'boe' | 'dogc'
    identifier: str              # BOE-A-2026-20910, or the DOGC control number
    published_date: date
    title: str
    url: str
    section: Optional[str] = None
    department: Optional[str] = None
    rank: Optional[str] = None
    pdf_url: Optional[str] = None
    title_es: Optional[str] = None
    tier: Optional[str] = None
    matched: list[str] = field(default_factory=list)


@dataclass
class ScanResult:
    """What a fetch actually did, so a caller can tell 'nothing matched' from 'read nothing'."""
    gazette: str
    days_requested: int = 0
    days_with_issue: int = 0     # BOE: days that returned a summary (Sundays do not)
    scanned: int = 0             # every item read, matched or not
    items: list[GazetteItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    newest_published: Optional[date] = None


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": _UA, "Accept": "application/json"})
    return s


def _as_list(x) -> list:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def parse_boe_summary(payload: dict, day: date) -> tuple[int, list[GazetteItem]]:
    """Flatten one BOE daily summary. Returns (items scanned, matching items).

    The nesting is section > department > (item | epigraph > item), and the API
    returns a bare object where a list would have one element, hence _as_list().
    """
    scanned, out = 0, []
    sumario = (payload.get("data") or {}).get("sumario") or {}
    for diario in _as_list(sumario.get("diario")):
        for sec in _as_list(diario.get("seccion")):
            code = str(sec.get("codigo") or "")
            for dep in _as_list(sec.get("departamento")):
                dep_name = dep.get("nombre")
                rows = [(None, it) for it in _as_list(dep.get("item"))]
                for ep in _as_list(dep.get("epigrafe")):
                    rows += [(ep.get("nombre"), it) for it in _as_list(ep.get("item"))]
                for ep_name, it in rows:
                    ident, title = it.get("identificador"), (it.get("titulo") or "").strip()
                    if not ident or not title:
                        continue
                    scanned += 1
                    tier, matched = classify(title, code)
                    if not tier:
                        continue
                    pdf = it.get("url_pdf")
                    out.append(GazetteItem(
                        gazette="boe", identifier=ident, published_date=day, title=title,
                        url=it.get("url_html") or (pdf.get("texto") if isinstance(pdf, dict) else pdf) or "",
                        section=code, department=dep_name, rank=ep_name,
                        pdf_url=(pdf.get("texto") if isinstance(pdf, dict) else pdf),
                        tier=tier, matched=matched))
    return scanned, out


def fetch_boe(days: int, *, today: Optional[date] = None, session: Optional[requests.Session] = None,
              pace: float = 0.3) -> ScanResult:
    """Read the BOE daily summaries for the last `days` days (today included)."""
    s = session or _session()
    today = today or date.today()
    res = ScanResult(gazette="boe", days_requested=days)
    for back in range(days):
        day = today - timedelta(days=back)
        try:
            r = s.get(BOE_SUMMARY_URL.format(ymd=day.strftime("%Y%m%d")), timeout=_TIMEOUT)
        except requests.RequestException as exc:
            res.errors.append(f"{day}: {type(exc).__name__}")
            continue
        if r.status_code == 404:
            # No issue that day (Sundays, some holidays): an empty day, not a failure.
            continue
        if r.status_code != 200:
            res.errors.append(f"{day}: HTTP {r.status_code}")
            continue
        try:
            payload = r.json()
        except ValueError:
            res.errors.append(f"{day}: not JSON")
            continue
        scanned, items = parse_boe_summary(payload, day)
        res.days_with_issue += 1
        res.scanned += scanned
        res.items += items
        res.newest_published = max(res.newest_published or day, day)
        time.sleep(pace)
    return res


def fetch_dogc(days: int, *, today: Optional[date] = None, session: Optional[requests.Session] = None) -> ScanResult:
    """Read DOGC section-1 norms published in the last `days` days from the open dataset."""
    s = session or _session()
    today = today or date.today()
    since = today - timedelta(days=days)
    res = ScanResult(gazette="dogc", days_requested=days)
    offset, page = 0, 1000
    while True:
        try:
            r = s.get(DOGC_URL, params={
                "$where": f"data_de_publicaci_del_diari >= '{since.isoformat()}T00:00:00'",
                "$order": "data_de_publicaci_del_diari DESC", "$limit": page, "$offset": offset,
            }, timeout=_TIMEOUT)
            r.raise_for_status()
            rows = r.json()
        except (requests.RequestException, ValueError) as exc:
            res.errors.append(f"offset {offset}: {type(exc).__name__}")
            break
        if not isinstance(rows, list):
            res.errors.append(f"offset {offset}: unexpected payload {str(rows)[:80]}")
            break
        for row in rows:
            ident = row.get("n_mero_de_control")
            title = (row.get("t_tol_de_la_norma") or "").strip()
            title_es = (row.get("t_tol_de_la_norma_es") or "").strip()
            pub = (row.get("data_de_publicaci_del_diari") or "")[:10]
            if not ident or not title or not pub:
                continue
            res.scanned += 1
            published = date.fromisoformat(pub)
            res.newest_published = max(res.newest_published or published, published)
            tier, matched = classify(f"{title} {title_es}", always_broad=True)
            if not tier:
                continue
            link = (row.get("url_ltima_versi_format_html") or row.get("format_html") or {}).get("url", "")
            pdf = (row.get("format_pdf") or {}).get("url")
            res.items.append(GazetteItem(
                gazette="dogc", identifier=str(ident), published_date=published, title=title,
                title_es=title_es or None, url=link, rank=row.get("rang_de_norma"),
                pdf_url=pdf, section="1", department=row.get("diari_oficial") or "DOGC",
                tier=tier, matched=matched))
        if len(rows) < page:
            break
        offset += page
    res.days_with_issue = len({i.published_date for i in res.items})
    return res

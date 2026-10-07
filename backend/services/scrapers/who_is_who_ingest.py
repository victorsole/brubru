"""Who is Who ingest — the EU interinstitutional directory via the EU SPARQL endpoint.

The directory (op.europa.eu/web/who-is-who) is published as structured data through
the EU SPARQL endpoint (publications.europa.eu/webapi/rdf/sparql) — the same query
data.europa.eu exposes as the "EU Whoiswho" dataset CSV. One query returns every
department (organisational unit) and every official (name + position) across all
EU institutions. No PDF parsing, no WAF.

Feeds who_is_who_departments + who_is_who_officials (migration 113).
"""

from __future__ import annotations

import hashlib
import html as _html
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

SPARQL_ENDPOINT = "http://publications.europa.eu/webapi/rdf/sparql"
ORG_PAGE = "https://op.europa.eu/en/web/who-is-who/organization/-/organization/{code}"
DIRECTORY_URL = "https://op.europa.eu/en/web/who-is-who"
# Each official has a REAL page on EU Whoiswho, keyed by the tail of their person URI.
# Reported by GovClipping on 1 October 2026: "les urls a person_uri i a public_url porten
# a pagines web que no existeixen". Both were constructed and both 404:
#
#   public_url  was ORG_PAGE with the FULL DOTTED mnemonic ("EDPS.EDPB.LCE") -> 404.
#               Only the top-level code resolves ("EDPS" -> 200). Worse, 13,238 of the
#               18,377 officials have no mnemonic at all and were handed the bare
#               directory URL, which resolves but points at a search page, not at them.
#   person_uri  is publications.europa.eu/resource/directory/person/<id>, which 404s as a
#               page AND under Accept: application/rdf+xml. It is an internal SPARQL
#               identifier, not an address, so it must never be presented as a link.
#
# PERSON_PAGE was verified against 6 random officials before being adopted: 6/6 returned
# 200 and the page title named the person we store (EP_DPPE256815 -> "Mr Marjan SAREC",
# COM_000037D63D -> "Cristina RUEDA CATRY").
#
# That sample was not enough, and the claim that first stood here -- that every one of the
# 18,377 rows carries a person_uri, so every official can have a page of their own -- was
# wrong. 600 rows carry a person id of the form UNDEFINED_<something>: the directory's own
# placeholder for a record with no published page. All 6 sampled ids happened to be real
# ones, so the defect shipped. Those 600 are mostly agency staff (ENISA, EASA, CPVO, ACER,
# Frontex...) who exist in the SPARQL directory but have no Whoiswho page, and stripping
# the UNDEFINED_ prefix does not reveal one: both forms 404.
PERSON_PAGE = "https://op.europa.eu/en/web/who-is-who/person/-/person/{person_id}"

# The directory's placeholder for "this person has no published page".
NO_PERSON_PAGE_MARKER = "UNDEFINED"


def person_page_id(pid: str) -> str:
    """The id the Whoiswho PAGE uses, which is not always the SPARQL person id.

    Found by Victor on 2 Oct 2026, after 5,311 officials had been marked as having no
    page: the directory writes some ids differently in its page URLs.
      COR_COR_2038234  -> COR_2038234    (the institution prefix is doubled in SPARQL)
      EESC_EESC_2038818 -> EESC_2038818
      EIB_EIB-2955     -> EIB_EIB2955    (the hyphen is dropped)
    Each rule was verified on 4 random dead rows of its family, 12/12 returning 200,
    and on the three pages Victor found by name. Hex ids (COM, ERCEA, EACI, EEAS, REA)
    were tested with their leading zeros stripped and still 404: they keep their id.
    """
    fam, sep, rest = pid.partition("_")
    if not sep:
        return pid
    if rest.startswith(fam + "_"):
        rest = rest[len(fam) + 1:]
    if fam == "EIB" and rest.startswith("EIB-"):
        rest = "EIB" + rest[4:]
    return f"{fam}_{rest}"


def undefined_page_id(pid: str, institution_uri: Optional[str]) -> Optional[str]:
    """The page id for an UNDEFINED_ placeholder: the institution's code replaces the prefix.

    Found by Victor on 7 Oct 2026 (UNDEFINED_EMA_I1014 -> EMEA_EMA_I1014, UNDEFINED_NRE525717
    -> EUROFOUND_NRE525717) and verified on 25 random placeholders, 25/25 returning 200 with
    the person named in the page title. The 575 officials this covers had been served with
    no public_url since 2 Oct, when the placeholder was read as "no page exists".
    """
    code = (institution_uri or "").rstrip("/").rsplit("/", 1)[-1].strip()
    rest = pid.split("_", 1)[1] if "_" in pid else ""
    return f"{code}_{rest}" if code and rest else None


def _person_page(person_uri: Optional[str], mnemonic: Optional[str],
                 institution_uri: Optional[str] = None) -> Optional[str]:
    """The official's own Whoiswho page, or None when they do not have one.

    Returns None rather than a substitute. The organisation page was considered for the
    600 and rejected: it resolves for only 123 of them, and it is a page about a body,
    not about the person the row describes. Presenting it as that official's public_url
    is the same error as the 404 it would replace -- a link that does not lead to the
    thing it claims. A client can tell an empty field is empty; it cannot tell that a
    200 points at the wrong page.

    The dotted-mnemonic fallback below stays for departments, whose rows reach this with
    no person id at all. Never return a URL built from a dotted mnemonic ("EDPS.EDPB.LCE"):
    the organisation route rejects it, so it is a 404 dressed as a link.
    """
    if person_uri:
        pid = person_uri.rstrip("/").rsplit("/", 1)[-1].strip()
        if pid and NO_PERSON_PAGE_MARKER not in pid:
            return PERSON_PAGE.format(person_id=person_page_id(pid))
        if pid:
            # A placeholder id: the page lives under the institution's code instead.
            page_id = undefined_page_id(pid, institution_uri)
            return PERSON_PAGE.format(person_id=page_id) if page_id else None
    if mnemonic:
        return ORG_PAGE.format(code=mnemonic.split(".", 1)[0])
    return DIRECTORY_URL

# The EU Whoiswho directory query (all departments + officials under EURUN).
QUERY = """PREFIX euvoc:<http://publications.europa.eu/ontology/euvoc#>
PREFIX org:<http://www.w3.org/ns/org#>
prefix skos:<http://www.w3.org/2004/02/skos/core#>
PREFIX vcard:<http://www.w3.org/2006/vcard/ns#>
PREFIX foaf:<http://xmlns.com/foaf/0.1/>
prefix useC:<http://publications.europa.eu/resource/authority/use-context/>
SELECT distinct str(?CB) as ?CorporateBody str(?mnem) as ?entity ?orgLabel concat(?gN," ",?fN) as ?name ?hon ?person ?position WHERE{
?org org:subOrganizationOf+ <http://publications.europa.eu/resource/authority/corporate-body/EURUN>.
?org skos:prefLabel ?orgLabel.FILTER(LANGMATCHES(LANG(?orgLabel),"en"))
?MS org:organization ?org.
optional{?MS euvoc:order ?order}
optional{?MS euvoc:positionComplement ?position FILTER(LANGMATCHES(LANG(?position),"en"))}
?person org:hasMembership ?MS.
?person foaf:familyName ?fN.?person foaf:givenName ?gN.
OPTIONAL{?person vcard:hasHonorificPrefix ?hon}
OPTIONAL{?org org:identifier ?mnem.Filter(datatype(?mnem)=useC:MNEMONIC)}
OPTIONAL{?org org:identifier ?CB.Filter(datatype(?CB)=useC:WHOISWHO-institution-uri)}
} LIMIT 50000"""

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BrubruBot/1.0)",
            "Accept": "application/sparql-results+json"}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:120]


def _v(b: dict, k: str) -> Optional[str]:
    val = (b.get(k) or {}).get("value")
    return val.strip() if isinstance(val, str) and val.strip() else None


def fetch_rows(timeout: int = 180) -> list:
    import httpx
    with httpx.Client(timeout=timeout, headers=_HEADERS, follow_redirects=True) as c:
        r = c.get(SPARQL_ENDPOINT, params={"query": QUERY, "format": "application/sparql-results+json"})
        if r.status_code != 200:
            logger.warning("[who-is-who] SPARQL HTTP %s", r.status_code)
            return []
        return r.json().get("results", {}).get("bindings", [])


# The directory gives the honorific as an authority URI (.../honorific/MR). Stored raw
# until 22 Sep 2026, it opened 15,611 of 15,732 official bodies with a URL.
_HONORIFICS = {"MR": "Mr", "MS": "Ms", "MRS": "Mrs", "DR": "Dr", "PROF": "Prof."}


def _honorific(value):
    if not value:
        return value
    code = str(value).rstrip("/").rsplit("/", 1)[-1].upper()
    return _HONORIFICS.get(code, code.title())


def build() -> tuple:
    """Return (departments[], officials[]) ready to upsert."""
    rows = fetch_rows()
    logger.info("[who-is-who] SPARQL rows: %d", len(rows))

    depts: dict = {}
    officials = []
    off_keys = set()
    for b in rows:
        name = _v(b, "name")
        if not name:
            continue
        mnem = _v(b, "entity")
        org = _v(b, "orgLabel")
        cb = _v(b, "CorporateBody")
        position = _v(b, "position")
        hon = _honorific(_v(b, "hon"))
        person = _v(b, "person")
        if not org:
            continue

        dkey = mnem or _slug(org)
        d = depts.get(dkey)
        if d is None:
            url = ORG_PAGE.format(code=mnem.split(".", 1)[0]) if mnem else DIRECTORY_URL
            d = {"dept_key": dkey, "mnemonic": mnem, "name": org, "institution_uri": cb,
                 "official_count": 0, "public_url": url, "_count": 0}
            depts[dkey] = d
        d["_count"] += 1
        if cb and not d["institution_uri"]:
            d["institution_uri"] = cb

        okey = hashlib.md5(f"{person or name}|{dkey}|{position or ''}".encode()).hexdigest()
        if okey in off_keys:
            continue
        off_keys.add(okey)
        officials.append({
            "official_key": okey, "name": name, "honorific": hon, "position": position,
            "department": org, "mnemonic": mnem, "institution_uri": cb, "person_uri": person,
            "public_url": _person_page(person, mnem, cb),
        })

    # finalise departments (count + body)
    dept_rows = []
    for d in depts.values():
        d["official_count"] = d.pop("_count")
        d["body_txt"], d["body_html"] = _dept_body(d)
        dept_rows.append(d)
    for o in officials:
        o["body_txt"], o["body_html"] = _official_body(o)

    logger.info("[who-is-who] %d departments + %d officials", len(dept_rows), len(officials))
    return dept_rows, officials


def _dept_body(d: dict) -> tuple:
    lines = [d["name"]]
    if d.get("mnemonic"):
        lines.append(f"Code: {d['mnemonic']}")
    lines.append(f"Officials listed: {d['official_count']}")
    lines.append("Part of the EU interinstitutional directory (Who is Who).")
    txt = "\n".join(lines)
    html = (f"<article><h2>{_html.escape(d['name'])}</h2><ul>"
            + (f"<li><strong>Code:</strong> {_html.escape(d['mnemonic'])}</li>" if d.get("mnemonic") else "")
            + f"<li><strong>Officials listed:</strong> {d['official_count']}</li></ul>"
            + f'<p><a href="{_html.escape(d["public_url"])}">View on EU Who is Who</a></p></article>')
    return txt, html


def _official_body(o: dict) -> tuple:
    disp = f"{o['honorific']} {o['name']}".strip() if o.get("honorific") else o["name"]
    lines = [disp]
    if o.get("position"):
        lines.append(f"Position: {o['position']}")
    if o.get("department"):
        lines.append(f"Department: {o['department']}")
    lines.append("Source: EU interinstitutional directory (Who is Who).")
    txt = "\n".join(lines)
    meta = [("Position", o.get("position")), ("Department", o.get("department")),
            ("Code", o.get("mnemonic"))]
    li = "".join(f"<li><strong>{k}:</strong> {_html.escape(str(v))}</li>" for k, v in meta if v)
    # An official with no page has public_url None; escaping None raised and failed the
    # whole daily sync on 2 Oct 2026. No page, no link.
    link = (f'<p><a href="{_html.escape(o["public_url"])}">View on EU Who is Who</a></p>'
            if o.get("public_url") else "")
    html = f"<article><h2>{_html.escape(disp)}</h2><ul>{li}</ul>{link}</article>"
    return txt, html

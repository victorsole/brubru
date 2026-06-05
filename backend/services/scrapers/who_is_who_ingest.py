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
        hon = _v(b, "hon")
        person = _v(b, "person")
        if not org:
            continue

        dkey = mnem or _slug(org)
        d = depts.get(dkey)
        if d is None:
            url = ORG_PAGE.format(code=mnem) if mnem else DIRECTORY_URL
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
            "public_url": ORG_PAGE.format(code=mnem) if mnem else DIRECTORY_URL,
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
    html = (f"<article><h2>{_html.escape(disp)}</h2><ul>{li}</ul>"
            + f'<p><a href="{_html.escape(o["public_url"])}">View on EU Who is Who</a></p></article>')
    return txt, html

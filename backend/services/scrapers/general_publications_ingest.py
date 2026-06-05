"""EU general publications ingest — Cellar PUB_GEN works via the EU SPARQL endpoint.

The EU Publications Office's general publications (brochures, reports, studies)
are Cellar works of resource-type PUB_GEN. One SPARQL query (paginated) returns
them with title + date + Cellar URI. No WAF.

Feeds eu_general_publications (migration 114).
"""

from __future__ import annotations

import html as _html
import logging
import re
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)

SPARQL = "http://publications.europa.eu/webapi/rdf/sparql"
DETAIL = "https://op.europa.eu/en/publication-detail/-/publication/{uuid}"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BrubruBot/1.0)"}
_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")

_QUERY = """PREFIX cdm:<http://publications.europa.eu/ontology/cdm#>
PREFIX lang:<http://publications.europa.eu/resource/authority/language/>
SELECT ?w ?title (MIN(?d) as ?date) WHERE {{
 ?w cdm:work_has_resource-type <http://publications.europa.eu/resource/authority/resource-type/PUB_GEN> .
 ?exp cdm:expression_belongs_to_work ?w ;
      cdm:expression_uses_language lang:ENG ;
      cdm:expression_title ?title .
 OPTIONAL {{ ?w cdm:work_date_document ?d . }}
}} GROUP BY ?w ?title ORDER BY DESC(?date) LIMIT {limit} OFFSET {offset}"""


def _date(s) -> Optional[date]:
    m = _ISO.match(s or "")
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def fetch(limit_total: int = 6000, page: int = 1000) -> list:
    import httpx
    rows = []
    seen = set()
    with httpx.Client(timeout=120, headers=_HEADERS, follow_redirects=True) as c:
        offset = 0
        while offset < limit_total:
            q = _QUERY.format(limit=page, offset=offset)
            r = c.get(SPARQL, params={"query": q, "format": "application/sparql-results+json"})
            if r.status_code != 200:
                logger.warning("[gen-pub] SPARQL HTTP %s at offset %d", r.status_code, offset)
                break
            binds = r.json().get("results", {}).get("bindings", [])
            if not binds:
                break
            for b in binds:
                w = (b.get("w") or {}).get("value")
                title = (b.get("title") or {}).get("value")
                if not w or not title:
                    continue
                uuid = w.rstrip("/").split("/")[-1]
                if uuid in seen:
                    continue
                seen.add(uuid)
                d = _date((b.get("date") or {}).get("value"))
                row = {
                    "publication_id": uuid, "cellar_uri": w, "title": title.strip()[:1000],
                    "publication_date": d, "public_url": DETAIL.format(uuid=uuid),
                    "source_url": w,
                }
                row["body_txt"], row["body_html"] = _body(row)
                rows.append(row)
            logger.info("[gen-pub] offset %d -> %d total", offset, len(rows))
            offset += page
    return rows


def _body(r: dict) -> tuple:
    lines = [r["title"], "EU general publication (Publications Office of the European Union)."]
    if r.get("publication_date"):
        lines.append(f"Date: {r['publication_date'].isoformat()}")
    lines.append(f"Read / download: {r['public_url']}")
    txt = "\n".join(lines)
    html = (f"<article><h2>{_html.escape(r['title'])}</h2>"
            f"<p>EU general publication (Publications Office of the European Union).</p>"
            + (f"<p><strong>Date:</strong> {r['publication_date'].isoformat()}</p>" if r.get("publication_date") else "")
            + f'<p><a href="{_html.escape(r["public_url"])}">Read / download</a></p></article>')
    return txt, html

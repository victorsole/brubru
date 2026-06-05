"""data.europa.eu open-data ingest.

The EU Publications Office's open-data portal (data.europa.eu) exposes an OPEN
JSON search API — no auth, no WAF. The search endpoint returns full DCAT records
(multilingual title/description, publisher, catalog, country, keywords,
distributions with download URLs, and the `is_hvd` High-Value-Dataset flag), so
one search call yields complete dataset rows; no per-dataset detail call needed.

    GET /api/hub/search/search?q={kw}&limit={n}&page={p}  -> {result:{count,results:[...]}}
    GET /api/hub/search/catalogues                         -> [catalogue_id, ...]

Verified live 5 June 2026. Feeds ``open_data_datasets`` + ``open_data_catalogues``
(migration 112).
"""

from __future__ import annotations

import html as _html
import logging
import re
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)

BASE = "https://data.europa.eu/api/hub/search"
DATASET_PAGE = "https://data.europa.eu/data/datasets/{id}"
CATALOGUE_PAGE = "https://data.europa.eu/data/catalogues/{id}"
_HEADERS = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 (compatible; BrubruBot/1.0)"}

_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def _client(timeout: int = 40):
    import httpx
    return httpx.Client(timeout=timeout, headers=_HEADERS, follow_redirects=True)


def search(c, query: str, limit: int = 100, page: int = 0) -> tuple:
    """Return (records, total) for a search query."""
    try:
        r = c.get(f"{BASE}/search", params={"q": query, "limit": limit, "page": page})
        if r.status_code != 200:
            return [], 0
        res = r.json().get("result", {})
        return res.get("results", []) or [], res.get("count", 0)
    except Exception as exc:
        logger.warning("[open-data] search '%s' p%d error: %s", query, page, exc)
        return [], 0


def list_catalogues(c) -> list:
    try:
        r = c.get(f"{BASE}/catalogues")
        if r.status_code != 200:
            return []
        data = r.json()
        return [x for x in (data if isinstance(data, list) else data.get("result", [])) if isinstance(x, str)]
    except Exception as exc:
        logger.warning("[open-data] catalogues error: %s", exc)
        return []


# --------------------------------------------------------------------------- #
# Normalisation                                                               #
# --------------------------------------------------------------------------- #

def _pick(value, prefer="en") -> Optional[str]:
    """Multilingual dict {lang: text} -> EN (or first); pass strings through."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        if prefer in value and value[prefer]:
            return str(value[prefer]).strip() or None
        for v in value.values():
            if v:
                return str(v).strip() or None
    if isinstance(value, list) and value:
        return _pick(value[0], prefer)
    return None


def _parse_date(s) -> Optional[date]:
    if not isinstance(s, str):
        return None
    m = _ISO_DATE.match(s)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _labels(items) -> list:
    """Extract string labels from a keyword/category list (strings or dicts)."""
    out = []
    for it in items or []:
        if isinstance(it, str):
            out.append(it)
        elif isinstance(it, dict):
            lab = _pick(it.get("label") or it.get("title")) or it.get("id")
            if lab:
                out.append(str(lab))
    # dedupe preserve order
    seen, res = set(), []
    for x in out:
        if x not in seen:
            seen.add(x); res.append(x)
    return res[:30]


def _distributions(dists) -> tuple:
    """Return (simplified_list, formats[]) from distribution records."""
    out, formats = [], []
    for d in dists or []:
        if not isinstance(d, dict):
            continue
        fmt = _pick(d.get("format")) or d.get("format_label")
        url = (d.get("access_url") or d.get("download_url") or d.get("accessUrl")
               or d.get("downloadUrl") or _pick(d.get("access_url")))
        if isinstance(url, list):
            url = url[0] if url else None
        title = _pick(d.get("title"))
        if fmt:
            formats.append(str(fmt).upper())
        if url or fmt or title:
            out.append({"format": (str(fmt).upper() if fmt else None), "url": url, "title": title})
    # dedupe formats
    formats = list(dict.fromkeys(formats))[:20]
    return out[:50], formats


def normalise(rec: dict) -> Optional[dict]:
    did = rec.get("id")
    if not did:
        return None
    title = _pick(rec.get("title")) or did
    desc = _pick(rec.get("description"))
    publisher = None
    pub = rec.get("publisher")
    if isinstance(pub, dict):
        publisher = _pick(pub.get("name")) or pub.get("homepage") or _pick(pub.get("label"))
    elif isinstance(pub, str):
        publisher = pub
    catalog = rec.get("catalog")
    cat_id = catalog.get("id") if isinstance(catalog, dict) else (catalog if isinstance(catalog, str) else None)
    country = rec.get("country") if isinstance(rec.get("country"), dict) else {}
    keywords = _labels(rec.get("keywords"))
    themes = _labels(rec.get("categories")) or _labels(rec.get("theme"))
    distributions, formats = _distributions(rec.get("distributions"))
    modified = _parse_date(rec.get("modified"))
    issued = _parse_date(rec.get("issued"))
    public_url = DATASET_PAGE.format(id=did)

    row = {
        "dataset_id": did,
        "title": title[:1000],
        "description": desc,
        "publisher": publisher,
        "catalogue": cat_id,
        "country": country.get("label"),
        "country_code": country.get("id"),
        "themes": themes,
        "keywords": keywords,
        "formats": formats,
        "is_hvd": bool(rec.get("is_hvd")),
        "distributions": distributions,
        "public_url": public_url,
        "issued": issued,
        "modified": modified,
        "source_url": f"{BASE}/search?q={did}",
    }
    row["body_txt"], row["body_html"] = _compose_body(row, desc)
    return row


def _compose_body(row: dict, desc: Optional[str]) -> tuple:
    lines = [row["title"]]
    if desc:
        lines.append(desc)
    meta = [
        ("Publisher", row.get("publisher")),
        ("Catalogue", row.get("catalogue")),
        ("Country", row.get("country")),
        ("Themes", ", ".join(row["themes"]) or None),
        ("Keywords", ", ".join(row["keywords"][:12]) or None),
        ("Formats", ", ".join(row["formats"]) or None),
        ("High-value dataset", "yes" if row["is_hvd"] else None),
        ("Last modified", row["modified"].isoformat() if row.get("modified") else None),
    ]
    for k, v in meta:
        if v:
            lines.append(f"{k}: {v}")
    dl = [d for d in row["distributions"] if d.get("url")]
    if dl:
        lines.append("Downloads:")
        lines.extend(f"  - {(d['format'] or 'file')}: {d['url']}" for d in dl[:15])
    txt = "\n".join(lines)

    parts = [f"<h2>{_html.escape(row['title'])}</h2>"]
    if desc:
        parts.append(f"<p>{_html.escape(desc)}</p>")
    li = "".join(f"<li><strong>{_html.escape(k)}:</strong> {_html.escape(str(v))}</li>" for k, v in meta if v)
    if li:
        parts.append(f"<ul>{li}</ul>")
    if dl:
        parts.append("<h3>Downloads</h3><ul>" + "".join(
            f'<li>{_html.escape(d["format"] or "file")}: <a href="{_html.escape(d["url"])}">{_html.escape(d["url"])}</a></li>'
            for d in dl[:15]) + "</ul>")
    parts.append(f'<p><a href="{_html.escape(row["public_url"])}">View on data.europa.eu</a></p>')
    return txt, "<article>" + "".join(parts) + "</article>"


# --------------------------------------------------------------------------- #
# Orchestration                                                               #
# --------------------------------------------------------------------------- #

# Broad EU policy keyword sweep — captures a representative dataset corpus across
# themes (incl. is_hvd datasets) for the search / high-value / by-publisher endpoints.
SWEEP_KEYWORDS = [
    "energy", "climate", "environment", "health", "agriculture", "transport",
    "economy", "finance", "education", "employment", "justice", "migration",
    "trade", "digital", "research", "fisheries", "mobility", "geospatial",
    "statistics", "company", "meteorological", "earth observation", "budget",
    "taxation", "security", "biodiversity", "water", "air quality",
]


def fetch_datasets(per_keyword: int = 200, pages: int = 1, keywords: Optional[list] = None) -> list:
    """Sweep the catalogue across policy keywords; return deduped normalised rows."""
    kws = keywords or SWEEP_KEYWORDS
    seen = set()
    rows = []
    with _client() as c:
        for kw in kws:
            for p in range(pages):
                recs, total = search(c, kw, limit=per_keyword, page=p)
                got = 0
                for rec in recs:
                    row = normalise(rec)
                    if not row or row["dataset_id"] in seen:
                        continue
                    seen.add(row["dataset_id"])
                    rows.append(row)
                    got += 1
                logger.info("[open-data] '%s' p%d -> +%d (total catalogue=%d)", kw, p, got, total)
                if not recs:
                    break
    return rows


def fetch_catalogues() -> list:
    """All catalogue ids -> normalised catalogue rows."""
    with _client() as c:
        ids = list_catalogues(c)
    rows = []
    for cid in ids:
        title = cid.replace("-", " ").replace("_", " ").title()
        url = CATALOGUE_PAGE.format(id=cid)
        rows.append({
            "catalogue_id": cid,
            "title": title,
            "country": None,
            "dataset_count": None,
            "public_url": url,
            "body_txt": f"{title}\nData catalogue on data.europa.eu.\nURL: {url}",
            "body_html": f'<article><h2>{_html.escape(title)}</h2><p>Data catalogue on data.europa.eu.</p>'
                         f'<p><a href="{_html.escape(url)}">Browse catalogue</a></p></article>',
        })
    return rows

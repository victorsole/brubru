"""
Accredited Parliamentary Assistants register - the database behind
/api/v2/parliament/mep-assistants.

The Parliament publishes each MEP's assistants (accredited parliamentary
assistants, local assistants, trainees, paying agents, service providers) on
that MEP's profile. There is no single bulk feed, so this register is built by
walking every current MEP's assistants page. One row per MEP, listing their
accredited and local assistants, linking to the assistants page.

Current MEPs come from the EP Open Data Portal; the per-MEP detail gives the name
slug and country. Assistant names are the `erpl_assistant` spans, grouped under
the category headings on the page. Row IS the content.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone

import requests

from services.scrapers.economy_common import Item, clean

_API = "https://data.europarl.europa.eu/api/v2/meps"
# Currently-sitting MEPs only. `?parliamentary-term=10` returns the whole-term
# superset (741: current + MEPs who left mid-term and were replaced), so the
# assistants register would carry stale former-MEP pages. `show-current` is the
# canonical currently-sitting set (718).
_CURRENT = "https://data.europarl.europa.eu/api/v2/meps/show-current"
_ASSIST = "https://www.europarl.europa.eu/meps/en/{mid}/{slug}/assistants"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
_CATS = ["Accredited assistants", "Local assistants", "Trainees",
         "Paying agents", "Service providers"]
_SPAN = re.compile(r'erpl_assistant[^>]*>(.*?)</span>', re.S)


def _country(detail: dict) -> str:
    mem = detail.get("hasMembership")
    mem = mem if isinstance(mem, list) else ([mem] if mem else [])
    for m in mem:
        rep = m.get("represents")
        if not rep:
            continue
        for r in (rep if isinstance(rep, list) else [rep]):
            if "authority/country/" in str(r):
                return str(r).rsplit("/", 1)[-1]
    return ""


def _names(segment: str) -> list[str]:
    out = []
    for raw in _SPAN.findall(segment):
        nm = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw)).strip()
        if nm and nm not in out:
            out.append(nm)
    return out


def _parse_assistants(html: str) -> dict[str, list[str]]:
    """Split the page by category headings and pull the assistant names in each."""
    pat = re.compile(r"(" + "|".join(re.escape(c) for c in _CATS) + r")")
    parts = pat.split(html)
    result: dict[str, list[str]] = {}
    # parts = [pre, cat, seg, cat, seg, ...]
    for i in range(1, len(parts) - 1, 2):
        cat = parts[i]
        seg = parts[i + 1]
        # cut the segment at the next category boundary (already split) — seg is bounded
        names = _names(seg)
        if names:
            result.setdefault(cat, [])
            for n in names:
                if n not in result[cat]:
                    result[cat].append(n)
    return result


def ingest_mep_assistants(*, fetch_bodies: bool = True, **_) -> list[Item]:
    s = requests.Session()
    s.headers.update({"User-Agent": _UA})
    meps = s.get(_CURRENT, params={"limit": 2000},
                 headers={"Accept": "application/ld+json"}, timeout=40).json().get("data") or []
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    seen: set[str] = set()
    for m in meps:
        mid = str(m.get("identifier") or "").strip()
        if not mid or mid in seen:
            continue
        seen.add(mid)
        label = clean(m.get("label") or "")
        slug = None
        country = ""
        try:
            detail = (s.get(f"{_API}/{mid}", headers={"Accept": "application/ld+json"},
                            timeout=30).json().get("data") or [{}])[0]
            gv = (detail.get("upperGivenName") or "").strip()
            fm = (detail.get("upperFamilyName") or "").strip()
            slug = f"{gv} {fm}".strip().replace(" ", "_")
            country = _country(detail)
            if not label:
                label = clean(detail.get("label") or "")
        except Exception:
            slug = (label or mid).upper().replace(" ", "_")
        url = _ASSIST.format(mid=mid, slug=slug)
        cats: dict[str, list[str]] = {}
        for attempt in range(2):
            try:
                resp = s.get(url, headers={"User-Agent": _UA}, timeout=30)
                if resp.status_code == 200:
                    cats = _parse_assistants(resp.text)
                break
            except requests.RequestException:
                if attempt == 1:
                    cats = {}
                time.sleep(1.0)
        accredited = cats.get("Accredited assistants", [])
        local = cats.get("Local assistants", [])
        total = sum(len(v) for v in cats.values())
        lines = [
            f"Member of the European Parliament: {label}" if label else "",
            f"Country: {country}" if country else "",
            f"Accredited assistants ({len(accredited)}): {', '.join(accredited)}" if accredited else "",
            f"Local assistants ({len(local)}): {', '.join(local)}" if local else "",
        ]
        for cat, names in cats.items():
            if cat not in ("Accredited assistants", "Local assistants") and names:
                lines.append(f"{cat} ({len(names)}): {', '.join(names)}")
        lines = [l for l in lines if l]
        items.append(Item(
            body_code="parliament", item_type="mep_assistant_register",
            title=clean(f"{label} - parliamentary assistants")[:120] if label else f"MEP {mid} assistants",
            public_url=url,
            summary=clean(" | ".join(x for x in [label, country,
                          f"{len(accredited)} accredited, {len(local)} local"] if x)),
            body_txt=clean("\n".join(lines)),
            body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
            document_date=None, creation_date=now, source_kind="ep_meps", guid=mid))
        time.sleep(0.3)  # europarl WAF rate-limits sustained sequential fetches
    return items

"""
MEP lobby-meetings collectors (Parliament side of MEUB Lobby Meetings).

Two autonomous sources, deduped into mep_lobby_meetings:
  1. OEIL Transparency section (per procedure) - static HTML, httpx. Each row:
     MEP (+ id from the profile link), role, committee, date, organisation. Always
     carries the procedure_ref.
  2. MEP profile "/meetings/past" (per MEP) - JS-rendered, so Playwright. Each block:
     organisation, date, capacity, the related procedure_ref, committee.

Org names are matched to the EU Transparency Register for the website hyperlink +
profile. NO Anthropic. Date formats differ: OEIL DD/MM/YYYY, profile DD-MM-YYYY.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0 Safari/537.36")
_OEIL = "https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference={ref}"
_MEP_ID_RE = re.compile(r"/meps/en/(\d+)")
_PROC_RE = re.compile(r"\d{4}/\d{4}\([A-Z]{2,4}\)")


def _to_iso(s: str) -> Optional[str]:
    """Parse DD/MM/YYYY or DD-MM-YYYY -> ISO date string."""
    if not s:
        return None
    m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", s)
    if not m:
        return None
    d, mo, y = (int(x) for x in m.groups())
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def norm_org(name: str) -> str:
    """Normalise an organisation name for matching/dedup (lowercase, strip legal
    forms + parenthetical acronyms + punctuation)."""
    s = (name or "").lower().strip()
    s = re.sub(r"\([^)]*\)", " ", s)              # drop "(acronym)"
    s = re.sub(r"\b(aisbl|asbl|gmbh|s\.a\.|sa|ag|ltd|llp|inc|e\.v\.|ev|sarl|bv|nv|plc|se)\b", " ", s)
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------------------
# 1. OEIL Transparency section (httpx, static HTML)
# ---------------------------------------------------------------------------

def fetch_oeil(procedure_ref: str) -> Optional[str]:
    try:
        r = httpx.get(_OEIL.format(ref=procedure_ref), headers={"User-Agent": _UA},
                      follow_redirects=True, timeout=40)
        if r.status_code == 200:
            return r.text
        logger.info("[mep-meetings] OEIL %s -> HTTP %s", procedure_ref, r.status_code)
    except Exception as e:
        logger.warning("[mep-meetings] OEIL fetch failed %s: %s", procedure_ref, e)
    return None


def parse_oeil_transparency(procedure_ref: str, html: str) -> List[Dict]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    hdr = soup.find(string=re.compile("Meetings with interest representatives", re.I))
    if not hdr:
        return []
    tbl = None
    node = hdr
    for _ in range(8):
        node = node.parent if node else None
        if node and node.find("table"):
            tbl = node.find("table")
            break
    if not tbl:
        for t in soup.find_all("table"):
            if "interest representative" in t.get_text(" ", strip=True).lower():
                tbl = t
                break
    if not tbl:
        return []
    out = []
    for tr in tbl.find_all("tr")[1:]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 5:
            continue
        name, role, committee, dt, org = cells[0], cells[1], cells[2], cells[3], cells[4]
        mid = None
        for a in tr.find_all("a", href=True):
            m = _MEP_ID_RE.search(a["href"])
            if m:
                mid = m.group(1)
                break
        out.append({
            "procedure_ref": procedure_ref, "mep_id": mid, "mep_name": name,
            "role": role, "committee": (committee or None), "meeting_date": _to_iso(dt),
            "organisation": org, "source": "oeil",
            "source_url": _OEIL.format(ref=procedure_ref),
        })
    return out


# ---------------------------------------------------------------------------
# 2. MEP profile /meetings/past (Playwright, JS-rendered)
# ---------------------------------------------------------------------------

def scrape_mep_profile(mep_id: str, max_scrolls: int = 6) -> List[Dict]:
    """Render an MEP's past-meetings page and parse the meeting blocks."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return []
    rows: List[Dict] = []
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try:
                pg = b.new_page(user_agent=_UA)
                pg.goto(f"https://www.europarl.europa.eu/meps/en/{mep_id}",
                        wait_until="domcontentloaded", timeout=40000)
                home = pg.url
                mtg = home.replace("/home", "/meetings/past") if "/home" in home \
                    else home.rstrip("/") + "/meetings/past"
                pg.goto(mtg, wait_until="networkidle", timeout=45000)
                pg.wait_for_timeout(2500)
                for _ in range(max_scrolls):  # trigger lazy "load more"
                    pg.mouse.wheel(0, 4000)
                    pg.wait_for_timeout(900)
                html = pg.content()
                mep_name = (pg.title() or "").split("|")[0].strip()
            finally:
                b.close()
    except Exception as e:
        logger.warning("[mep-meetings] profile render failed %s: %s", mep_id, e)
        return []

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup
    txt = re.sub(r"\s+", " ", main.get_text(" ", strip=True))
    # Split on the date marker; each segment carries one meeting's fields.
    segs = re.split(r"Date, Place:", txt)
    for seg in segs[1:]:
        dm = re.search(r"(\d{2}-\d{2}-\d{4})", seg[:40])
        if not dm:
            continue
        cap = re.search(r"Capacity:\s*(.*?)\s*(?:Meeting related to procedure|Code of associated|Meeting with|$)", seg)
        proc = _PROC_RE.search(seg[:400])
        com = re.search(r"Code of associated committee or delegation\s*([A-Z]{2,6})", seg[:400])
        org = re.search(r"Meeting with:\s*(.*?)(?=\s*Meeting with\b|\s*Date, Place|$)", seg)
        rows.append({
            "procedure_ref": proc.group(0) if proc else None,
            "mep_id": str(mep_id), "mep_name": mep_name or None,
            "role": (cap.group(1).strip() if cap else None),
            "committee": (com.group(1) if com else None),
            "meeting_date": _to_iso(dm.group(1)),
            "organisation": (org.group(1).strip() if org else None),
            "source": "profile",
            "source_url": mtg,
        })
    return [r for r in rows if r["organisation"] and r["meeting_date"]]

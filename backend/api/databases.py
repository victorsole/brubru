"""
Brubru Databases API (MEUB Section 4.2 - Analysis & Strategy).

Powers the "Brubru Databases" tab: the knowledge libraries (EU Canon, Knowledge
Guides, Deep Dives, Catalan law) and the Policy Areas Explorer ("who does what"
across the EU institutions, through the shared PI crosswalk). Read: authenticated.
No Anthropic. All URLs are verified-real (filesystem / committed manifest).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from knowledge_base.eu_calendar_institutions import (
    COMMISSION_DG_NAME, COUNCIL_CONFIGURATIONS, EP_COMMITTEES,
)
from services.tracking.tracked_files_seeder import _interest_list
from services.tracking.pi_committee_crosswalk import (
    PI_TO_COMMITTEES, committees_for_interests, dgs_for_interests,
    council_configs_for_interests, policy_areas_for_interests,
)
from services.partners import beresol_monitors_service as beresol
from services.research import research_sources, document_summariser
from .auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/databases", tags=["Brubru Databases"])

# Anchor on the backend/ dir, NOT the repo root: on Railway the deploy app-root
# IS backend/ (Dockerfile lives there), so a repo-root assumption overshoots and
# the canon manifest + guides resolve to a non-existent path -> 0 counts. Same
# pattern as services/ai/context_builder.py. (frontend/public only exists in dev;
# on Railway _PUBLIC simply won't resolve and the disk-based "featured items"
# degrade to empty, which the callers already guard with .is_dir().)
_BACKEND = Path(__file__).resolve().parents[1]
_REPO = _BACKEND.parent
_PUBLIC = _REPO / "frontend" / "public"
_MANIFEST = _BACKEND / "knowledge_base" / "canon_reports.json"
_GUIDES = _BACKEND / "knowledge_base" / "guides"

# Friendly titles for the (few) Catalan translations that exist on disk.
_CATALAN_TITLES = {
    "32016R0679": "RGPD (Reglament general de protecció de dades)",
    "32019D1194": "Decisió (UE) 2019/1194",
    "32019D1194-softcatala": "Decisió (UE) 2019/1194 (Softcatalà)",
    "eu-andorra": "Acord UE-Andorra",
}


def _rel(url: Optional[str]) -> Optional[str]:
    """Relative path so links work in dev + prod (strip the production host)."""
    if not url:
        return None
    return url.replace("https://brubru.beresol.eu", "").replace("http://brubru.beresol.eu", "") or url


def _manifest() -> List[dict]:
    try:
        return (json.loads(_MANIFEST.read_text(encoding="utf-8")) or {}).get("reports", [])
    except Exception as e:
        logger.warning("[databases] canon manifest unreadable: %s", e)
        return []


def _clean_title(title: Optional[str]) -> str:
    """Drop the SEO suffix some canon titles carry (" | Brubru EU Canon")."""
    if not title:
        return ""
    return re.split(r"\s*\|\s*Brubru", title)[0].strip()


_FAMILY_LABELS = {
    "eu_pharmaceutical": "Pharmaceutical",
    "banking_prudential_basel": "Banking / Basel III",
    "eu_animal_health_sps": "Animal health / SPS",
    "eu_financial_supervision_architecture": "Financial supervision",
    "anti_subsidy_trade_remedies": "Anti-subsidy",
    "anti_dumping_trade_remedies": "Anti-dumping",
    "eu_crypto_digital_finance": "Crypto / digital finance",
    "eu_artificial_intelligence": "Artificial intelligence",
}


def _family_label(family: Optional[str]) -> Optional[str]:
    if not family:
        return None
    return _FAMILY_LABELS.get(family) or family.replace("_", " ").strip().capitalize()


def _eucanon_index_cards() -> Dict[str, dict]:
    """Parse the published eucanon/index.html to enrich canon cards with the
    chips and article/title stats the manifest does not carry. Keyed by CELEX
    and by 'slug:<slug>'. Degrades to {} if the file is missing or changes shape."""
    out: Dict[str, dict] = {}
    idx = _PUBLIC / "eucanon" / "index.html"
    try:
        html = idx.read_text(encoding="utf-8")
    except Exception:
        return out
    for m in re.finditer(r'<article class="canon-card">(.*?)</article>', html, re.S):
        block = m.group(1)
        celex_m = re.search(r'canon-card__celex">\s*CELEX:\s*([0-9A-Za-z]+)', block)
        href_m = re.search(r'href="([^"]+?)/?(?:index\.html)?"\s+class="canon-card__cta"', block)
        chips = [c.strip() for c in re.findall(r'class="chip[^"]*">([^<]+)</span>', block)]
        stats: Dict[str, int] = {}
        for sm in re.finditer(
            r'stat-mini__value">.*?(\d[\d,]*)\s*</div>\s*<div class="stat-mini__label">([^<]+)</div>',
            block, re.S,
        ):
            try:
                stats[sm.group(2).strip().lower()] = int(sm.group(1).replace(",", ""))
            except ValueError:
                continue
        rec = {"chips": chips, "articles": stats.get("articles"), "titles": stats.get("titles")}
        if celex_m:
            out[celex_m.group(1)] = rec
        if href_m:
            out.setdefault("slug:" + href_m.group(1).rstrip("/").split("/")[-1], rec)
    return out


@router.get("/library-stats", summary="Knowledge-library counts + featured items (verified URLs)")
def library_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Counts and a few featured, real-URL items for each Brubru knowledge library:
    EU Canon, Deep Dives, Knowledge Guides, Catalan EU law."""
    reports = _manifest()
    canon = [r for r in reports if r.get("report_type") == "canon"]
    deep = [r for r in reports if r.get("report_type") == "deep_dive"]

    def _items(rows, n=6):
        return [{
            "slug": r.get("slug"), "title": r.get("title"),
            "url": _rel(r.get("public_url")), "languages": r.get("languages") or ["en"],
            "celex": r.get("celex"),
        } for r in rows[:n]]

    # Catalan: featured items = the pages that actually exist on disk (no 404s);
    # the COUNT is the authoritative DB total (matches the public landing page).
    catalan = []
    cat_dir = _PUBLIC / "legislacio-ue-catala"
    if cat_dir.is_dir():
        for d in sorted(cat_dir.iterdir()):
            if d.is_dir() and (d / "index.html").exists():
                catalan.append({"name": d.name,
                                "title": _CATALAN_TITLES.get(d.name, d.name),
                                "url": f"https://brubru.beresol.eu/legislacio-ue-catala/{d.name}/index.html"})
    catalan_count = len(catalan)
    try:
        from models.catalan_translation import CatalanTranslation
        catalan_count = db.query(CatalanTranslation).count() or catalan_count
    except Exception:
        db.rollback()

    guides_count = len(list(_GUIDES.glob("*.md"))) if _GUIDES.is_dir() else 0

    return {
        "canon": {"count": len(canon), "url": "/eucanon/index.html", "items": _items(canon)},
        "deep_dive": {"count": len(deep), "url": "/eucanon/index.html", "items": _items(deep)},
        "guides": {"count": guides_count, "url": "/guides/index.html"},
        "catalan": {"count": catalan_count, "url": "https://brubru.beresol.eu/legislacio-ue-catala/", "items": catalan},
    }


@router.get("/policy-areas", summary="Policy Areas Explorer: who does what across the EU institutions")
def policy_areas(
    my_interests: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """For each EU policy domain, the responsible EP committees, Commission DGs and
    Council configurations (via the shared PI crosswalk + institutional name maps).
    my_interests flags the domains that match the user's policy interests."""
    pi = set(_interest_list(current_user)) if my_interests else set()
    pi_active = bool(pi)

    areas = []
    for domain in PI_TO_COMMITTEES.keys():
        coms = sorted(committees_for_interests([domain]))
        dgs = sorted(dgs_for_interests([domain]))
        cfgs = sorted(council_configs_for_interests([domain]))
        tags = sorted(policy_areas_for_interests([domain]))
        areas.append({
            "name": domain,
            "is_pi_match": domain in pi,
            "committees": [{"code": c, "name": EP_COMMITTEES.get(c, c)} for c in coms],
            "dgs": [{"code": d, "name": COMMISSION_DG_NAME.get(d, d)} for d in dgs],
            "council_configs": [{"code": c, "name": COUNCIL_CONFIGURATIONS.get(c, c)} for c in cfgs],
            "policy_tags": tags,
            "body_count": len(coms) + len(dgs) + len(cfgs),
        })
    # PI matches first, then by breadth of institutional footprint.
    areas.sort(key=lambda a: (a["is_pi_match"], a["body_count"]), reverse=True)
    return {"pi_active": pi_active, "areas": areas}


@router.get("/canon", summary="EU Canon library: the binding-law explainers, newest first")
def canon(current_user: User = Depends(get_current_user)):
    """All EU Canon entries (binding-law explainers) from the committed manifest,
    enriched with the category chips and article/title counts parsed from the
    published index. Each item deep-links to its own explainer page; per-language
    URLs are included where translations exist."""
    reports = [r for r in _manifest() if r.get("report_type") == "canon"]
    enrich = _eucanon_index_cards()
    items = []
    langs_seen = set()
    for r in reports:
        celex = r.get("celex")
        ex = enrich.get(celex or "") or enrich.get("slug:" + (r.get("slug") or "")) or {}
        langs = r.get("languages") or ["en"]
        langs_seen.update(langs)
        items.append({
            "slug": r.get("slug"),
            "title": _clean_title(r.get("title")),
            "celex": celex,
            "doc_type": r.get("doc_type"),
            "year": (r.get("publication_date") or "")[:4] or None,
            "family_label": _family_label(r.get("legal_family")),
            "languages": langs,
            "url": _rel(r.get("public_url")),
            "lang_urls": {k: _rel(v) for k, v in (r.get("lang_urls") or {}).items()},
            "chips": ex.get("chips") or [],
            "articles": ex.get("articles"),
            "titles": ex.get("titles"),
        })
    items.sort(key=lambda x: (x.get("year") or "", x.get("title") or ""), reverse=True)
    return {
        "count": len(items),
        "site_url": "/eucanon/",
        "languages": len(langs_seen),
        "items": items,
    }


@router.get("/guides", summary="Knowledge Guides library: counts by category")
def guides(current_user: User = Depends(get_current_user)):
    """The knowledge guides that ground Brubru's answers, grouped by category with
    each category's icon, brand colour and guide count parsed from the published
    guides index (kept in sync whenever the index is regenerated)."""
    categories: List[dict] = []
    total = 0
    idx = _PUBLIC / "guides" / "index.html"
    try:
        html = idx.read_text(encoding="utf-8")
        for m in re.finditer(
            r'section__icon" style="background:\s*(#[0-9a-fA-F]{6})[^>]*>\s*'
            r'<span class="mdi (mdi-[a-z0-9-]+)"[^>]*></span>.*?'
            r'section__title">([^<]+)</h2>.*?'
            r'section__subtitle">\s*(\d+)\s*guide',
            html, re.S,
        ):
            count = int(m.group(4))
            categories.append({
                "title": m.group(3).strip(),
                "count": count,
                "color": m.group(1),
                "icon": m.group(2),
            })
            total += count
    except Exception as e:
        logger.warning("[databases] guides index unreadable: %s", e)
    file_count = len(list(_GUIDES.glob("*.md"))) if _GUIDES.is_dir() else 0
    return {
        "count": total or file_count,
        "file_count": file_count,
        "categories": categories,
        "url": "/guides/index.html",
    }


@router.get("/catalan", summary="Dret europeu en català: EU law translated into Catalan")
def catalan(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Catalan translations of EU law. The KPI count is the AUTHORITATIVE total
    from the `catalan_translations` DB (the same source the public landing page
    uses) — NOT a count of the few HTML deep-dives committed to disk. Featured
    items are the on-disk pages that render in-app (no 404s); the CTA opens the
    full public catalogue."""
    # Authoritative count: every translated text in the DB (matches the landing
    # page's total_translations, ~14.9k). Fail-soft to 0 if the table is absent.
    count = 0
    try:
        from models.catalan_translation import CatalanTranslation
        count = db.query(CatalanTranslation).count()
    except Exception:
        db.rollback()

    # Featured items = the verified on-disk deep-dive pages (no dead links).
    items = []
    cat_dir = _PUBLIC / "legislacio-ue-catala"
    if cat_dir.is_dir():
        for d in sorted(cat_dir.iterdir()):
            if d.is_dir() and (d / "index.html").exists():
                items.append({
                    "name": d.name,
                    "title": _CATALAN_TITLES.get(d.name, d.name),
                    "url": f"https://brubru.beresol.eu/legislacio-ue-catala/{d.name}/index.html",
                })
    # Absolute URL so the "Obre les traduccions" CTA always lands on the public
    # static catalogue (a relative path can fall back to the SPA root).
    return {"count": count, "url": "https://brubru.beresol.eu/legislacio-ue-catala/", "items": items}


@router.get("/beresol-monitors", summary="Beresol Monitors: the partner policy-intelligence feed index")
def beresol_monitors(current_user: User = Depends(get_current_user)):
    """The list of Beresol policy-intelligence monitors (defence, capital markets,
    tariffs, AI, quantum, startups, gold...). Each links to its public dashboard
    and, via /beresol-monitors/{slug}, to a full digest. Live from the Beresol
    Monitor API (Bearer auth). Returns available:false when the key is unset or the
    upstream is unreachable, so the UI can show an honest state."""
    if not beresol.has_key():
        return {"available": False, "reason": "no_key", "monitors": []}
    try:
        data = beresol.list_monitors()
        return {"available": True, "source_url": "https://beresol.eu",
                "count": len(data["monitors"]), **data}
    except Exception as e:  # noqa: BLE001 - degrade gracefully for the UI
        logger.warning("[databases] beresol index failed: %s", e)
        return {"available": False, "reason": "unreachable", "monitors": []}


@router.get("/beresol-monitors/{slug}", summary="Beresol Monitors: one monitor's digest")
def beresol_monitor_detail(slug: str, current_user: User = Depends(get_current_user)):
    """A single Beresol monitor's digest: title, dashboard URL, scrape date and the
    sanitised HTML/plain-text body. available:false when missing or unreachable."""
    if not beresol.has_key():
        return {"available": False, "reason": "no_key"}
    if not re.fullmatch(r"[a-z0-9-]{1,40}", slug or ""):
        return {"available": False, "reason": "bad_slug"}
    try:
        data = beresol.get_monitor(slug)
    except Exception as e:  # noqa: BLE001
        logger.warning("[databases] beresol monitor %s failed: %s", slug, e)
        return {"available": False, "reason": "unreachable"}
    if data is None:
        return {"available": False, "reason": "not_found"}
    return {"available": True, **data}


@router.get("/research-sources", summary="Research & Evidence: curated, PI-aware source launchpad")
def research_sources_catalogue(
    my_interests: bool = Query(False),
    current_user: User = Depends(get_current_user),
):
    """The curated Tier-1 catalogue of EU research/evidence publishers (foresight
    anchors + CORDIS, JRC Knowledge Centres, the Publications Office catalogue and
    flagship DG publishers). Each card is PI-tagged and its search link PI-seeded."""
    pi = _interest_list(current_user) if my_interests else []
    return research_sources.build_catalogue(pi)


@router.get("/research-feed/{source_id}", summary="Research & Evidence: recent documents from one source (read-through)")
def research_feed(source_id: str, current_user: User = Depends(get_current_user)):
    """Live read-through of a source's publications RSS feed (no storage). Returns
    recent documents the user can open or summarise. Empty for deep-link-only sources."""
    if not re.fullmatch(r"[a-z0-9_-]{1,40}", source_id or ""):
        return {"items": []}
    return {"items": research_sources.read_through(source_id)}


class _SummaryRequest(BaseModel):
    url: str


@router.post("/research-summary", summary="Research & Evidence: full-document AI summary (non-Anthropic)")
async def research_summary(
    req: _SummaryRequest,
    current_user: User = Depends(get_current_user),
):
    """Fetch a publication (HTML or PDF), summarise the whole document in plain
    language, and add a personalised 'how this is useful to you' tied to the user's
    policy interests. Mistral -> GPT-4 -> Gemini (no Anthropic); cached per URL."""
    if not re.match(r"^https?://", req.url or ""):
        return {"available": False, "reason": "bad_url"}
    pi = _interest_list(current_user)
    try:
        return {"available": True, **(await document_summariser.summarise(req.url, pi))}
    except Exception as e:  # noqa: BLE001 - honest UI state on any failure
        logger.warning("[databases] research summary failed for %s: %s", req.url, e)
        return {"available": False, "reason": "failed"}

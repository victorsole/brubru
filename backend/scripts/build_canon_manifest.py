#!/usr/bin/env python3.12
"""
Build the committed canon/deep-dive manifest read by
/api/v2/proprietary/canon/* at runtime.

WHY A MANIFEST (not a DB table / not the CSV / not the HTML dirs):
The canon + deep-dive HTML reports live as static files under
frontend/public/ on SiteGround, and their source-of-truth metadata lives in
data/canon/brubru_binding_laws.csv. Neither of those travels with the backend
deploy on Railway (frontend/public is the frontend build; the CSV is
gitignored). So we snapshot the small (~25-entry) catalogue into a git-tracked
JSON manifest that the backend can always read.

Re-run this whenever a new canon deep-dive ships (the /canon skill), then
commit the regenerated JSON.

    python3.12 -m scripts.build_canon_manifest

Output: backend/knowledge_base/canon_reports.json
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "frontend" / "public"
EUCANON_DIR = PUBLIC / "eucanon"
CSV_PATH = ROOT / "data" / "canon" / "brubru_binding_laws.csv"
OUT_PATH = ROOT / "backend" / "knowledge_base" / "canon_reports.json"

SITE = "https://brubru.beresol.eu"
LANG_FILES = {"en": "index.html", "es": "es.html", "ca": "ca.html", "fr": "fr.html", "it": "it.html", "nl": "nl.html"}

# Pharma canon batch (May 2026): built from Cellar, not the binding-laws CSV,
# so they have no eucanon_url row to match on. CELEX + legal_family are known
# and stable (see CLAUDE.md / memory canon.md). All five are Regulations.
PHARMA_OVERRIDE = {
    "2000-141_orphan":     {"celex": "32000R0141", "doc_type": "Regulation", "publication_date": "2000-01-22", "legal_family": "eu_pharmaceutical"},
    "2004-726_ema":        {"celex": "32004R0726", "doc_type": "Regulation", "publication_date": "2004-04-30", "legal_family": "eu_pharmaceutical"},
    "2006-1901_paediatric":{"celex": "32006R1901", "doc_type": "Regulation", "publication_date": "2006-12-27", "legal_family": "eu_pharmaceutical"},
    "2007-1394_atmp":      {"celex": "32007R1394", "doc_type": "Regulation", "publication_date": "2007-12-10", "legal_family": "eu_pharmaceutical"},
    "2014-536_ctr":        {"celex": "32014R0536", "doc_type": "Regulation", "publication_date": "2014-05-27", "legal_family": "eu_pharmaceutical"},
}

# Law-explainer deep-dive slugs under frontend/public/<slug>/ (NOT eucanon).
# Explicit allowlist so we never sweep in clientpitch / data-architecture /
# europa-2026 / guides etc., which are other HTML surfaces, not legal reports.
DEEP_DIVE_SLUGS = [
    "biotech-act",
    "critical-medicines-act",
    "csam-regulation",
    "digital-networks-act",
    "eu-inc",
    "industrial-accelerator-act",
    "late-payments",
    "passenger-mobility-package-2026",
    "pharma-laws",
]


def _strip_title(raw: str) -> str:
    t = re.sub(r"\s*\|\s*Brubru\s*$", "", raw.strip())
    return t.strip()


def _parse_head(html_path: Path) -> tuple[str | None, str | None]:
    """Return (title, description) from an HTML file's <head>."""
    try:
        head = html_path.read_text(encoding="utf-8", errors="replace")[:8000]
    except OSError:
        return None, None
    title = None
    m = re.search(r"<title>(.*?)</title>", head, re.IGNORECASE | re.DOTALL)
    if m:
        title = _strip_title(re.sub(r"\s+", " ", m.group(1)))
    desc = None
    m = re.search(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', head, re.IGNORECASE | re.DOTALL)
    if m:
        desc = re.sub(r"\s+", " ", m.group(1)).strip()
    return title, desc


def _languages(report_dir: Path) -> list[str]:
    return [lang for lang, fname in LANG_FILES.items() if (report_dir / fname).is_file()]


def _lang_urls(base_url: str, langs: list[str]) -> dict[str, str]:
    return {lang: f"{base_url}/{LANG_FILES[lang]}" for lang in langs}


def _load_csv_by_slug() -> dict[str, dict]:
    """Index CSV rows by their eucanon_url slug — the authoritative match
    (carries the exact CELEX + legal_family). R/L/D collisions on a bare
    (year, number) key make that approach unsafe, so we key on the slug."""
    idx: dict[str, dict] = {}
    if not CSV_PATH.is_file():
        return idx
    for r in csv.DictReader(CSV_PATH.open(encoding="utf-8")):
        mm = re.search(r"/eucanon/([^/]+)/", r.get("eucanon_url", "") or "")
        if mm:
            idx[mm.group(1)] = r
    return idx


def build() -> list[dict]:
    csv_by_slug = _load_csv_by_slug()
    reports: list[dict] = []

    # ---- Canon (eucanon) --------------------------------------------------
    for d in sorted(EUCANON_DIR.iterdir()):
        if not d.is_dir() or not (d / "index.html").is_file():
            continue
        slug = d.name
        csv_row = csv_by_slug.get(slug)
        override = PHARMA_OVERRIDE.get(slug, {})
        title, desc = _parse_head(d / "index.html")
        langs = _languages(d)
        base_url = f"{SITE}/eucanon/{slug}"
        celex = (csv_row.get("celex") if csv_row else None) or override.get("celex")
        reports.append({
            "slug": slug,
            "report_type": "canon",
            "title": title or (csv_row.get("title_en") if csv_row else slug),
            "summary": desc,
            "celex": celex,
            "doc_type": (csv_row.get("doc_type") if csv_row else None) or override.get("doc_type"),
            "publication_date": ((csv_row.get("publication_date") or None) if csv_row else None) or override.get("publication_date"),
            "legal_family": ((csv_row.get("legal_family") or None) if csv_row else None) or override.get("legal_family"),
            "languages": langs,
            "public_url": f"{base_url}/index.html",
            "lang_urls": _lang_urls(base_url, langs),
            "eurlex_url": ((csv_row.get("eurlex_url") or None) if csv_row else None)
                          or (f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}" if celex else None),
        })

    # ---- Deep-dives -------------------------------------------------------
    for slug in DEEP_DIVE_SLUGS:
        d = PUBLIC / slug
        if not d.is_dir() or not (d / "index.html").is_file():
            continue
        title, desc = _parse_head(d / "index.html")
        langs = _languages(d)
        base_url = f"{SITE}/{slug}"
        reports.append({
            "slug": slug,
            "report_type": "deep_dive",
            "title": title or slug.replace("-", " ").title(),
            "summary": desc,
            "celex": None,
            "doc_type": None,
            "publication_date": None,
            "legal_family": None,
            "languages": langs,
            "public_url": f"{base_url}/index.html",
            "lang_urls": _lang_urls(base_url, langs),
            "eurlex_url": None,
        })

    return reports


def main() -> None:
    reports = build()
    payload = {
        "schema": "brubru-canon-reports/1",
        "site": SITE,
        "count": len(reports),
        "reports": reports,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    canon = sum(1 for r in reports if r["report_type"] == "canon")
    deep = sum(1 for r in reports if r["report_type"] == "deep_dive")
    print(f"[OK] wrote {OUT_PATH.relative_to(ROOT)} -> {len(reports)} reports ({canon} canon, {deep} deep-dive)")
    for r in reports:
        print(f"  {r['report_type']:9s} {r['slug']:42s} celex={r['celex'] or '-':12s} langs={len(r['languages'])}")


if __name__ == "__main__":
    main()

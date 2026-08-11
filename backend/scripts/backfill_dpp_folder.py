"""Backfill the /api/v2/dpp folder into economy_items.

Every item is written with the canonical five datapoints and a COMPOSED BODY. The
contract is explicit that structured data is not exempt from carrying body_txt and
body_html (memory/feedback_api_endpoint_pattern_contract.md), and for the
legal-framework resource the body is the FULL TEXT of the act, not a summary, so a
passport platform can read the obligation itself rather than a paraphrase of it.

Sources:
  * law        -> backend/data/dpp_corpus/<CELEX>_*.txt, fetched from EUR-Lex, with
                  the site chrome stripped. Metadata joined from eu_laws.
  * standard   -> Commission Implementing Decision (EU) 2026/1736, Annex.
  * sector     -> Commission DPP sector pages + ESPR Art. 18(5) working-plan priorities.
  * registry   -> Commission DPP registry pages + Reg. (EU) 2026/1778.
  * audience   -> the four Commission DPP audience pages.
  * guidance   -> Commission-published DPP guidance documents.

Idempotent: economy_items has UNIQUE (body_code, item_type, public_url), so every write
is an upsert on that key.

Usage:
    python3.12 -m backend.scripts.backfill_dpp_folder --dry-run
    python3.12 -m backend.scripts.backfill_dpp_folder --apply
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

from sqlalchemy import text

from core.database import SessionLocal

BODY = "dpp"
CORPUS = project_root / "backend/data/dpp_corpus"
EURLEX = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"
COMMISSION = "https://single-market-economy.ec.europa.eu/single-market/digital-product-passport"

# --------------------------------------------------------------------------- #
# text cleaning
# --------------------------------------------------------------------------- #

# The act begins at one of these; everything before is EUR-Lex site chrome.
_START_ANCHORS = (
    "THE EUROPEAN PARLIAMENT AND THE COUNCIL OF THE EUROPEAN UNION",
    "THE EUROPEAN COMMISSION",
    "THE COUNCIL OF THE EUROPEAN UNION",
)
# The act ends at the OJ ISSN block or the site footer, whichever comes first.
_END_ANCHORS = ("ISSN 1977", "Top\nThis site is managed by", "This site is managed by")


# Nav/footer fragments that must never survive into a body. The language selector is
# the dangerous one: the act title also appears in the page header above it, so naively
# starting at the first title match drags the whole selector into the body.
_CHROME_MARKERS = (
    "Accept all cookies",
    "Skip to main content",
    "This site is managed by",
    "Quick search",
    "Multilingual display",
    "Languages, formats and authentic version",
)


def strip_chrome(raw: str, title: Optional[str]) -> str:
    """Remove EUR-Lex navigation and footer, keeping the act itself."""
    txt = raw

    # Anchor on the enacting institution: that line is unique to the act body.
    anchor = -1
    for a in _START_ANCHORS:
        i = txt.find(a)
        if i >= 0:
            anchor = i
            break

    # Cut at the enacting formula. It is the first line that belongs to the act and it
    # sits below every piece of page furniture, including the language selector, which
    # is why anchoring on the title does not work: the title is printed in the page
    # header above the selector too. The composed header already carries the official
    # title, so nothing is lost by starting here; the preamble and recitals follow it.
    start = anchor
    if start < 0 and title:
        start = txt.find(" ".join(title.split()[:8]))
    if start > 0:
        txt = txt[start:]

    ends = [txt.find(a) for a in _END_ANCHORS]
    ends = [i for i in ends if i > 0]
    if ends:
        txt = txt[: min(ends)]

    txt = re.sub(r"\n{3,}", "\n\n", txt)
    txt = re.sub(r"[ \t]+\n", "\n", txt)
    return txt.strip()


def to_html(txt: str) -> str:
    """Plain text to simple, safe HTML paragraphs."""
    blocks = [b.strip() for b in txt.split("\n\n") if b.strip()]
    out: List[str] = []
    for b in blocks:
        esc = html.escape(b).replace("\n", "<br>")
        if re.match(r"^(Article \d+|CHAPTER |ANNEX|SECTION )", b):
            out.append(f"<h3>{esc}</h3>")
        else:
            out.append(f"<p>{esc}</p>")
    return "\n".join(out)


def compose(title: str, lead: str, facts: Dict[str, Any], detail: str = "") -> tuple:
    """Compose body_txt + body_html for a structured (non-act) row."""
    lines = [title, "", lead, ""]
    for k, v in facts.items():
        if v:
            lines.append(f"{k}: {v}")
    if detail:
        lines += ["", detail]
    txt = "\n".join(lines).strip()

    fact_html = "".join(
        f"<tr><th align='left'>{html.escape(str(k))}</th>"
        f"<td>{html.escape(str(v))}</td></tr>"
        for k, v in facts.items() if v
    )
    parts = [f"<h2>{html.escape(title)}</h2>", f"<p>{html.escape(lead)}</p>"]
    if fact_html:
        parts.append(f"<table>{fact_html}</table>")
    if detail:
        parts.append(f"<p>{html.escape(detail)}</p>")
    return txt, "\n".join(parts)


# --------------------------------------------------------------------------- #
# seeds
# --------------------------------------------------------------------------- #

# celex -> (corpus file stem, role in the regime, registry hook)
LAWS = {
    "32024R1781": ("32024R1781_espr", "The framework act. Creates the digital product "
                   "passport (Articles 9 to 15), the registry (Article 13), the public "
                   "web portal (Article 14) and the customs check (Article 15). Sets no "
                   "product requirement itself: those arrive by delegated act under "
                   "Article 4.", "Article 4 (delegated acts)"),
    "32026R1778": ("32026R1778_dpp_registry", "The implementing act for the registry. "
                   "Its Article 1 is the authoritative list of which legislation obliges "
                   "registration.", "sets up the registry itself"),
    "32026D1736": ("32026D1736_dpp_standards", "Publishes the references of the "
                   "harmonised standards for digital product passports, giving a "
                   "presumption of conformity.", None),
    "32023R1542": ("32023R1542_batteries", "The battery passport: the first passport "
                   "with a hard deadline, 18 February 2027.", "Article 77"),
    "32024R3110": ("32024R3110_construction_products", "Requires a passport for "
                   "construction products.", "Article 76"),
    "32025R2509": ("32025R2509_toys", "Requires a passport for toys.", "Article 19"),
    "32026R0405": ("32026R0405_detergents", "Requires a passport for detergents and "
                   "end-user surfactants.", "Article 21"),
    "32025R0040": ("32025R0040_ppwr_packaging", "Packaging and packaging waste. Carries "
                   "its own passport-style obligations but is NOT named in Implementing "
                   "Regulation (EU) 2026/1778 Article 1, so it does not feed the central "
                   "registry on that basis.", None),
    "32024R1252": ("32024R1252_critical_raw_materials", "Critical raw materials: "
                   "supply-chain and circularity duties that the passport information "
                   "layer draws on.", None),
    "32025L1892": ("32025L1892_textile_epr_wfd", "Extended producer responsibility for "
                   "textiles and footwear. The financial and collection regime that sits "
                   "alongside the textile passport.", None),
    "32011R1007": ("32011R1007_textile_labelling", "Textile fibre names and labelling. "
                   "The existing baseline for fibre composition information that the "
                   "textile passport inherits.", None),
    "32026R0002": ("32026R0002_dpp_impl_2026_2", "Implementing regulation in the "
                   "ecodesign series.", None),
    "32026R0296": ("32026R0296_unsold_textiles_delegated", "Delegated regulation in the "
                   "ecodesign series on unsold consumer products.", None),
}

STANDARDS = [
    ("EN 18216:2026", "Data exchange protocols"),
    ("EN 18219:2026", "Unique identifiers"),
    ("EN 18220:2026", "Data carriers"),
    ("EN 18221:2026", "Data storage, archiving, and persistence"),
    ("EN 18222:2026", "Application Programming Interfaces (APIs) for product passport "
                      "lifecycle management and searchability"),
    ("EN 18223:2026", "System interoperability"),
]

SECTORS = [
    ("batteries", "Batteries", "18 February 2027", "Regulation (EU) 2023/1542, Art. 77",
     "The first product group with a binding passport deadline. Applies to certain "
     "large batteries: industrial, light means of transport and electric vehicle."),
    ("textile-apparel", "Textiles and apparel", "Q3-Q4 2027 (indicative)",
     "ESPR delegated act under Reg. (EU) 2024/1781 Art. 4",
     "Garments and footwear. Named as a statutory priority in ESPR Article 18(5)(c). "
     "The delegated act is in preparation; the JRC preparatory study runs under product "
     "group 467 and the Have Your Say initiative is 16116."),
    ("iron-steel", "Iron and steel", "Q4 2026 (indicative)", "ESPR delegated act",
     "Statutory priority under ESPR Article 18(5)(a)."),
    ("aluminium", "Aluminium", "Q3-Q4 2027 (indicative)", "ESPR delegated act",
     "Statutory priority under ESPR Article 18(5)(b)."),
    ("tyres", "Tyres", "Q3-Q4 2027 (indicative)", "ESPR delegated act",
     "Statutory priority under ESPR Article 18(5)(e)."),
    ("construction-products", "Construction products", "Q2 2027 (indicative)",
     "Regulation (EU) 2024/3110, Art. 76",
     "Passport obligations arrive through the Construction Products Regulation rather "
     "than an ESPR delegated act."),
    ("furniture", "Furniture", "2028 (indicative)", "ESPR delegated act",
     "Statutory priority under ESPR Article 18(5)(d)."),
    ("mattresses", "Mattresses", "2029 (indicative)", "ESPR delegated act",
     "Covered within the furniture priority in ESPR Article 18(5)(d)."),
    ("toys", "Toys", "per Regulation (EU) 2025/2509", "Regulation (EU) 2025/2509, Art. 19",
     "Passport obligations arrive through the Toy Safety Regulation."),
    ("detergents", "Detergents and surfactants", "per Regulation (EU) 2026/405",
     "Regulation (EU) 2026/405, Art. 21",
     "Covers detergents and end-user surfactants."),
    ("ict", "ICT products and electronics", "not yet scheduled", "ESPR delegated act",
     "Statutory priority under ESPR Article 18(5)(k)."),
]

REGISTRY_FACTS = [
    ("registry-production", "DPP Registry: production environment",
     "https://registry.product-passport.ec.europa.eu/",
     "The live registry where economic operators register each digital product "
     "passport.",
     {"Legal basis": "Reg. (EU) 2024/1781 Art. 13; Reg. (EU) 2026/1778",
      "Live since": "20 July 2026",
      "Legal deadline to establish": "19 July 2026 (ESPR Art. 13(1))",
      "Registration pathways": "secure user interface, or API",
      "Who must register": "the economic operator placing the product on the market "
                           "or putting it into service (Art. 13(4))"}),
    ("registry-acceptance", "DPP Registry: acceptance and testing environment",
     "https://registry.acc.product-passport.ec.europa.eu/",
     "The testing environment operators use to integrate before going live.",
     {"Purpose": "integration testing without writing to the production registry",
      "Available since": "20 July 2026"}),
    # Distinct fragment anchors are deliberate: economy_items is UNIQUE on
    # (body_code, item_type, public_url), so two facts sharing the registry page URL
    # would silently overwrite each other on upsert.
    ("unique-registration-identifier", "The unique registration identifier",
     f"{COMMISSION}/dpp-registry_en#unique-registration-identifier",
     "What the registry returns once an operator uploads the required data, and what "
     "it does not mean.",
     {"Created by": "ESPR Article 13(5)",
      "Returned": "automatically on upload of the Art. 13(1) and 13(2) data",
      "Not proof of compliance": "Art. 13(5) states the communication is not proof of "
                                 "compliance with the ESPR or other Union law",
      "Customs use": "must be provided to customs for release for free circulation "
                     "(Art. 15(1))"}),
    ("registry-scope", "Which products the registry covers",
     f"{COMMISSION}/dpp-registry_en#scope",
     "Implementing Regulation (EU) 2026/1778 Article 1 is the authoritative scope list.",
     {"ESPR delegated acts": "Reg. (EU) 2024/1781 Art. 4",
      "Batteries": "Reg. (EU) 2023/1542 Art. 77",
      "Construction products": "Reg. (EU) 2024/3110 Art. 76",
      "Toys": "Reg. (EU) 2025/2509 Art. 19",
      "Detergents and end-user surfactants": "Reg. (EU) 2026/405 Art. 21",
      "Catch-all": "any other Union law requiring a passport and its registration "
                   "(Art. 1(1)(f))"}),
    ("customs-csw-certex", "Customs controls and the Single Window",
     f"{COMMISSION}_en",
     "How the passport becomes a border condition rather than a documentation exercise.",
     {"Legal basis": "ESPR Article 15",
      "Requirement": "provide the unique registration identifier to customs for "
                     "release for free circulation",
      "Customs check": "identifier and commodity code must match the registry",
      "Interconnection": "EU CSW-CERTEX under Reg. (EU) 2022/2399",
      "Deadline for interconnection": "within four years of the entry into force of "
                                      "Implementing Regulation (EU) 2026/1778"}),
]

AUDIENCES = [
    ("economic-operators", "Economic operators", "economic-operators_en",
     "What the passport requires of manufacturers, importers and distributors: create "
     "the passport, register it, keep the data accurate, complete and up to date "
     "(ESPR Art. 9(1)), and give customs the registration identifier."),
    ("consumers", "Consumers", "consumers_en",
     "What consumers can read from a passport before buying: composition, circularity, "
     "environmental impact, repair and end-of-life information, accessible before the "
     "buyer is bound by a contract (ESPR Art. 9(2)(e))."),
    ("repairers-and-recyclers", "Repairers and recyclers", "repairers-and-recyclers_en",
     "What the passport gives the people who keep a product alive or take it apart: "
     "material composition, disassembly and repair information, and end-of-life routes."),
    ("public-authorities", "Public authorities", "public-authorities_en",
     "How market surveillance and customs authorities use the registry: direct access "
     "under ESPR Art. 13(6) and verification at release for free circulation."),
]

GUIDANCE = [
    ("dpp-registry-user-guide", "DPP Registry: user guide for economic operators",
     "https://single-market-economy.ec.europa.eu/document/download/"
     "079a45e2-469f-4eec-b1e5-32e8e05d1357_en?filename=dpp_registry_user_guide_for_"
     "economic_operators.pdf",
     date(2026, 7, 1),
     "Commission user guide walking an economic operator through registration in the "
     "DPP registry, including access management, verification and the registration "
     "pathways."),
    ("battery-passport-data-points", "Digital Batteries Passport: data points by category",
     "https://single-market-economy.ec.europa.eu/document/download/"
     "cd1e5e6c-4a4a-4b99-995a-49eb6916187e_en?filename=Digital%20Batteries%20Passport"
     "%20-%20data%20point%20by%20category.pdf",
     date(2026, 7, 1),
     "Commission guidance listing the data points a battery passport must carry, "
     "grouped by category. The concrete schema reference for the first mandatory "
     "passport."),
    ("dpp-faqs", "Digital Product Passport: frequently asked questions",
     "https://single-market-economy.ec.europa.eu/explore-our-faqs_en",
     None,
     "Commission FAQ covering scope, timing, registration and the relationship between "
     "the passport and existing product legislation."),
]

_UPSERT = text(
    """
    INSERT INTO economy_items (
        body_code, item_type, title, summary, public_url,
        body_txt, body_html, document_date, creation_date, source_kind, guid
    ) VALUES (
        :body_code, :item_type, :title, :summary, :public_url,
        :body_txt, :body_html, :document_date, :creation_date, :source_kind, :guid
    )
    ON CONFLICT (body_code, item_type, public_url) DO UPDATE SET
        title = EXCLUDED.title,
        summary = EXCLUDED.summary,
        body_txt = EXCLUDED.body_txt,
        body_html = EXCLUDED.body_html,
        document_date = EXCLUDED.document_date,
        source_kind = EXCLUDED.source_kind
    """
)


def build_rows(db) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    rows: List[Dict[str, Any]] = []

    # ---- laws: full text bodies -------------------------------------------
    for celex, (stem, role, hook) in LAWS.items():
        meta = db.execute(
            text("SELECT title, date, extra_metadata FROM eu_laws WHERE celex = :c"),
            {"c": celex},
        ).fetchone()
        if not meta:
            print(f"  [WARN] {celex}: not in eu_laws, skipped")
            continue
        f = CORPUS / f"{stem}.txt"
        if not f.exists():
            print(f"  [WARN] {celex}: no corpus file {f.name}, skipped")
            continue

        act = strip_chrome(f.read_text(encoding="utf-8"), meta.title)
        if len(act) < 2000:
            print(f"  [WARN] {celex}: cleaned text only {len(act)} chars, skipped")
            continue

        eli = (meta.extra_metadata or {}).get("eli")
        header = [meta.title, ""]
        header.append(f"CELEX: {celex}")
        if eli:
            header.append(f"ELI: {eli}")
        if meta.date:
            header.append(f"Document date: {meta.date}")
        header.append(f"Role in the DPP regime: {role}")
        if hook:
            header.append(f"Registry hook: {hook}")
        header += ["", "FULL TEXT", ""]
        body_txt = "\n".join(header) + act

        rows.append({
            "item_type": "law",
            "title": meta.title,
            "summary": role,
            "public_url": EURLEX.format(celex=celex),
            "body_txt": body_txt,
            "body_html": to_html(body_txt),
            "document_date": meta.date,
            "source_kind": "cellar",
            "guid": f"dpp-law-{celex}",
        })

    # ---- harmonised standards ---------------------------------------------
    for ref, subject in STANDARDS:
        title = f"{ref} — Digital product passport: {subject}"
        txt, htm = compose(
            title,
            "A harmonised standard whose reference is published in the Official Journal "
            "and which therefore carries a presumption of conformity for the digital "
            "product passport requirements it covers.",
            {"Standard reference": ref,
             "Subject": subject,
             "Published by": "Commission Implementing Decision (EU) 2026/1736 of 14 July 2026",
             "CELEX of the publishing decision": "32026D1736",
             "Effect": "presumption of conformity with ESPR Articles 10 and 11 to the "
                       "extent covered (ESPR Art. 12(2))"},
        )
        rows.append({
            "item_type": "standard", "title": title,
            "summary": f"Harmonised standard for digital product passports: {subject}.",
            "public_url": f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32026D1736#{ref.replace(' ', '-').replace(':', '-')}",
            "body_txt": txt, "body_html": htm,
            "document_date": date(2026, 7, 14), "source_kind": "cellar",
            "guid": f"dpp-standard-{ref.replace(' ', '').replace(':', '-')}",
        })

    # ---- sectors ------------------------------------------------------------
    for slug, name, when, basis, note in SECTORS:
        title = f"Digital product passport: {name}"
        txt, htm = compose(
            title,
            f"When the digital product passport becomes mandatory for {name.lower()}, "
            f"and under which act.",
            {"Sector": name,
             "Passport mandatory from": when,
             "Legal basis": basis,
             "Registry": "central DPP registry under ESPR Art. 13"},
            note,
        )
        rows.append({
            "item_type": "sector", "title": title,
            "summary": f"{name}: passport mandatory from {when}.",
            "public_url": f"{COMMISSION}/{slug}_en",
            "body_txt": txt, "body_html": htm,
            "document_date": None, "source_kind": "html",
            "guid": f"dpp-sector-{slug}",
        })

    # ---- registry -----------------------------------------------------------
    for slug, title, url, lead, facts in REGISTRY_FACTS:
        txt, htm = compose(title, lead, facts)
        rows.append({
            "item_type": "registry", "title": title, "summary": lead,
            "public_url": url, "body_txt": txt, "body_html": htm,
            "document_date": None, "source_kind": "html",
            "guid": f"dpp-registry-{slug}",
        })

    # ---- audiences ----------------------------------------------------------
    for slug, name, page, lead in AUDIENCES:
        title = f"Digital product passport for {name.lower()}"
        txt, htm = compose(title, lead,
                           {"Audience": name,
                            "Regime": "Digital Product Passport under ESPR",
                            "Source": "Commission DPP audience page"})
        rows.append({
            "item_type": "audience", "title": title, "summary": lead,
            "public_url": f"{COMMISSION}/{page}",
            "body_txt": txt, "body_html": htm,
            "document_date": None, "source_kind": "html",
            "guid": f"dpp-audience-{slug}",
        })

    # ---- guidance -----------------------------------------------------------
    for slug, title, url, doc_date, lead in GUIDANCE:
        txt, htm = compose(title, lead,
                           {"Publisher": "European Commission (DG GROW)",
                            "Document type": "guidance",
                            "Contact": "GROW-DIGITAL-PRODUCT-PASSPORT@ec.europa.eu"})
        rows.append({
            "item_type": "guidance", "title": title, "summary": lead,
            "public_url": url, "body_txt": txt, "body_html": htm,
            "document_date": doc_date, "source_kind": "pdf",
            "guid": f"dpp-guidance-{slug}",
        })

    # ---- battery passport data points -------------------------------------
    dp_file = CORPUS / "_battery_data_points.json"
    if dp_file.exists():
        import json as _json

        for dp in _json.loads(dp_file.read_text(encoding="utf-8")):
            title = f"Battery passport data point {dp['number']}: {dp['name']}"
            facts = {
                "Data point number": dp["number"],
                "Legal source": dp["source"] or "not stated in the guidance",
                "Electric vehicle batteries": dp["ev"],
                "Light means of transport batteries": dp["lmt"],
                "Industrial batteries": dp["industrial"],
                "Applicability confidence": dp.get("applicability_confidence", "clean"),
            }
            txt, htm = compose(
                title,
                "A field the battery digital product passport must carry, with its "
                "legal source and its applicability by battery type. Mandatory from "
                "18 February 2027 for the battery types indicated.",
                facts,
                dp.get("parse_note", ""),
            )
            rows.append({
                "item_type": "data_point", "title": title,
                "summary": f"{dp['name'][:150]} ({dp['source'] or 'source not stated'}).",
                "public_url": (
                    "https://single-market-economy.ec.europa.eu/document/download/"
                    "cd1e5e6c-4a4a-4b99-995a-49eb6916187e_en#data-point-"
                    f"{dp['number']}"
                ),
                "body_txt": txt, "body_html": htm,
                "document_date": date(2026, 7, 28), "source_kind": "pdf",
                "guid": f"dpp-datapoint-battery-{dp['number']}",
            })
    else:
        print(f"  [WARN] {dp_file.name} missing, no data points ingested")

    # ---- Commission news + events -------------------------------------------
    # The listing renders dates as '07 JUL 2026' across three lines, which is fragile
    # to parse. The URL slug ends in the publication date, so take it from there.
    _SLUG_DATE = re.compile(r"-(\d{4})-(\d{2})-(\d{2})_en/?$")

    def _date_from_url(url: str) -> Optional[date]:
        m = _SLUG_DATE.search(url)
        if not m:
            return None
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    for fname, item_type, noun in (
        ("_dpp_news.json", "news", "Commission news item"),
        ("_dpp_events.json", "event", "Commission event"),
    ):
        f = CORPUS / fname
        if not f.exists():
            print(f"  [WARN] {fname} missing, no {item_type} ingested")
            continue
        import json as _json

        for it in _json.loads(f.read_text(encoding="utf-8")):
            d = _date_from_url(it["url"])
            txt, htm = compose(
                it["title"],
                f"{noun} on the Digital Product Passport.",
                {"Published": d.isoformat() if d else "date not stated",
                 "Source": "European Commission, single market newsroom",
                 "Link": it["url"]},
            )
            rows.append({
                "item_type": item_type, "title": it["title"],
                "summary": f"{noun} on the Digital Product Passport.",
                "public_url": it["url"],
                "body_txt": txt, "body_html": htm,
                "document_date": d, "source_kind": "html",
                "guid": f"dpp-{item_type}-{it['url'].rstrip('/').rsplit('/', 1)[-1][:60]}",
            })

    for r in rows:
        r["body_code"] = BODY
        r["creation_date"] = now
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        print("=== building rows ===")
        rows = build_rows(db)

        by_type: Dict[str, int] = {}
        empty_bodies = []
        for r in rows:
            by_type[r["item_type"]] = by_type.get(r["item_type"], 0) + 1
            if not r["body_txt"] or not r["body_html"]:
                empty_bodies.append(r["title"])

        print("\n=== composition ===")
        for t, n in sorted(by_type.items()):
            sizes = [len(r["body_txt"]) for r in rows if r["item_type"] == t]
            print(f"  {t:<10} {n:>3} rows   body_txt min={min(sizes):>7} max={max(sizes):>7}")
        print(f"  TOTAL      {len(rows):>3} rows")

        if empty_bodies:
            print(f"\n[FAIL] {len(empty_bodies)} rows have an empty body: {empty_bodies[:5]}")
            return 1
        print("\n[OK] every row carries a non-empty body_txt and body_html")

        # A body that still holds site chrome is a silently corrupt body: it reads as
        # legal text to anything downstream. Fail loudly rather than store it.
        dirty = [
            (r["guid"], m)
            for r in rows
            for m in _CHROME_MARKERS
            if m in r["body_txt"]
        ]
        if dirty:
            print(f"\n[FAIL] {len(dirty)} bodies still contain site chrome:")
            for guid, m in dirty[:8]:
                print(f"    {guid}: {m!r}")
            return 1
        print("[OK] no EUR-Lex navigation or footer text survives in any body")

        # economy_items is UNIQUE on (body_code, item_type, public_url). Two rows
        # sharing that key silently overwrite each other on upsert, so the loss shows
        # up only as a row count that is lower than what was built. Catch it here,
        # before the write, rather than reading it off the verification block.
        keys = [(r["item_type"], r["public_url"]) for r in rows]
        dupes = {k for k in keys if keys.count(k) > 1}
        if dupes:
            print(f"\n[FAIL] {len(dupes)} duplicate (item_type, public_url) keys would "
                  f"collapse rows on upsert:")
            for it, url in sorted(dupes):
                titles = [r["title"] for r in rows
                          if r["item_type"] == it and r["public_url"] == url]
                print(f"    {it} {url}")
                for t in titles:
                    print(f"        - {t}")
            return 1
        print(f"[OK] all {len(rows)} rows have a distinct (item_type, public_url) key")

        if args.dry_run:
            print("\n[DRY-RUN] nothing written")
            return 0

        for r in rows:
            db.execute(_UPSERT, r)
        db.commit()
        print(f"\n[OK] upserted {len(rows)} rows into economy_items (body_code='{BODY}')")

        # Reconcile: a row whose public_url changed between runs is re-inserted under
        # the new key and the old row is left behind as an orphan, so the folder would
        # serve a stale duplicate for ever. Delete anything under this body that the
        # current build did not produce. Keyed on guid, which the build always sets.
        # Prune on public_url, not on guid: when a row's URL changes, the new row is
        # written under the new URL while the old one survives carrying the SAME guid,
        # so a guid-based prune cannot tell them apart and silently keeps both.
        live_urls = [r["public_url"] for r in rows]
        orphans = db.execute(
            text("SELECT id, item_type, public_url, title FROM economy_items "
                 "WHERE body_code = :b AND NOT (public_url = ANY(:urls))"),
            {"b": BODY, "urls": live_urls},
        ).fetchall()
        if orphans:
            print(f"\n[INFO] pruning {len(orphans)} orphaned row(s) left by an earlier run:")
            for o in orphans:
                print(f"    {o.item_type}: {o.title[:52]}")
                print(f"        stale url {o.public_url}")
            db.execute(
                text("DELETE FROM economy_items "
                     "WHERE body_code = :b AND NOT (public_url = ANY(:urls))"),
                {"b": BODY, "urls": live_urls},
            )
            db.commit()

        # ---- verification ----
        print("\n=== verification ===")
        total = db.execute(
            text("SELECT count(*) FROM economy_items WHERE body_code = :b"), {"b": BODY}
        ).scalar()
        nulls = db.execute(
            text("SELECT count(*) FROM economy_items WHERE body_code = :b "
                 "AND (body_txt IS NULL OR body_txt = '' OR body_html IS NULL OR body_html = '')"),
            {"b": BODY},
        ).scalar()
        no_url = db.execute(
            text("SELECT count(*) FROM economy_items WHERE body_code = :b AND public_url IS NULL"),
            {"b": BODY},
        ).scalar()
        print(f"  rows built               : {len(rows)}")
        print(f"  rows stored              : {total}   "
              f"{'OK' if total == len(rows) else 'FAIL: stored count does not match what was built'}")
        print(f"  rows with an empty body  : {nulls}   {'OK' if nulls == 0 else 'FAIL'}")
        print(f"  rows without a public_url: {no_url}   {'OK' if no_url == 0 else 'FAIL'}")
        for t, n, mn in db.execute(
            text("SELECT item_type, count(*), min(length(body_txt)) FROM economy_items "
                 "WHERE body_code = :b GROUP BY item_type ORDER BY item_type"), {"b": BODY}
        ).fetchall():
            print(f"    {t:<10} {n:>3} rows, smallest body {mn} chars")
        return 0 if (nulls == 0 and no_url == 0 and total == len(rows)) else 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3.12
"""
Backfill the 10 pharma canon entries into data/canon/brubru_binding_laws.csv.

WHY
The pharma canon batch (May 2026) shipped 10 eucanon deep-dive pages
(orphan / community code / herbal / EMA / paediatric / ATMP /
pharmacovigilance / falsified medicines / PV amendment / CTR) without
updating the CSV register, because those base acts are absent from the
LEG_2025-11 bulk-export corpus the CSV was scanned from. The pharma team
worked around it via a PHARMA_OVERRIDE block in build_canon_manifest.py
but never folded the fix back into the register.

Effect: the CSV was missing 7 of the 10 pharma rows outright, carried the
wrong act (Commission Decision) under CELEX 32010L0084, and left the two
real Directive rows (32011L0062, 32012L0026) unmarked. A future /canon
"pick the next law" query could re-process a live page and overwrite it.

WHAT THIS SCRIPT DOES
- INSERT 7 new rows for pharma acts absent from the register.
- REPLACE 1 row: CELEX 32010L0084's current Commission-Decision row (wrong
  act under a Directive-form CELEX) with the true pharmacovigilance
  Directive metadata.
- UPDATE 2 existing rows: mark 32011L0062 and 32012L0026 canon_completed.
- Leave CELEX 32014L0536 alone (Commission Decision, unrelated to CTR).
  CTR (32014R0536) is added via the insert path.

Timestamps: canon_completed_at set to 2026-06-05T12:55:51+02:00, the
Git first-added timestamp for these eucanon pages (commit 1890fc78).

Backup: writes brubru_binding_laws.csv.bak.before_pharma_backfill first.

Run: python3.12 backend/scripts/backfill_pharma_canon_register.py
"""
from __future__ import annotations

import csv
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT / "data" / "canon" / "brubru_binding_laws.csv"
BACKUP_PATH = CSV_PATH.with_suffix(".csv.bak.before_pharma_backfill")

CANON_COMPLETED_AT = "2026-06-05T12:55:51+02:00"
SITE = "https://brubru.beresol.eu"
LEGAL_FAMILY = "eu_pharmaceutical"


def _eurlex(celex: str) -> str:
    return f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"


def _url(slug: str) -> str:
    return f"{SITE}/eucanon/{slug}/index.html"


# Canonical pharma-canon metadata (title, dates, OJ ref: Publications Office).
PHARMA_ROWS: list[dict] = [
    {
        "celex": "32000R0141",
        "doc_type": "Regulation (EC) No",
        "publication_date": "2000-01-22",
        "title_en": "Regulation (EC) No 141/2000 of the European Parliament and of the Council of 16 December 1999 on orphan medicinal products",
        "oj_reference": "L 018/1",
        "policy_area": "Health",
        "slug": "2000-141_orphan",
        "action": "insert",
    },
    {
        "celex": "32001L0083",
        "doc_type": "Directive",
        "publication_date": "2001-11-28",
        "title_en": "Directive 2001/83/EC of the European Parliament and of the Council of 6 November 2001 on the Community code relating to medicinal products for human use",
        "oj_reference": "L 311/67",
        "policy_area": "Health",
        "slug": "2001-83_community_code",
        "action": "insert",
    },
    {
        "celex": "32004L0024",
        "doc_type": "Directive",
        "publication_date": "2004-04-30",
        "title_en": "Directive 2004/24/EC of the European Parliament and of the Council of 31 March 2004 amending, as regards traditional herbal medicinal products, Directive 2001/83/EC on the Community code relating to medicinal products for human use",
        "oj_reference": "L 136/85",
        "policy_area": "Health",
        "slug": "2004-24_herbal",
        "action": "insert",
    },
    {
        "celex": "32004R0726",
        "doc_type": "Regulation (EC) No",
        "publication_date": "2004-04-30",
        "title_en": "Regulation (EC) No 726/2004 of the European Parliament and of the Council of 31 March 2004 laying down Community procedures for the authorisation and supervision of medicinal products for human and veterinary use and establishing a European Medicines Agency",
        "oj_reference": "L 136/1",
        "policy_area": "Health",
        "slug": "2004-726_ema",
        "action": "insert",
    },
    {
        "celex": "32006R1901",
        "doc_type": "Regulation (EC) No",
        "publication_date": "2006-12-27",
        "title_en": "Regulation (EC) No 1901/2006 of the European Parliament and of the Council of 12 December 2006 on medicinal products for paediatric use and amending Regulation (EEC) No 1768/92, Directive 2001/20/EC, Directive 2001/83/EC and Regulation (EC) No 726/2004",
        "oj_reference": "L 378/1",
        "policy_area": "Health",
        "slug": "2006-1901_paediatric",
        "action": "insert",
    },
    {
        "celex": "32007R1394",
        "doc_type": "Regulation (EC) No",
        "publication_date": "2007-12-10",
        "title_en": "Regulation (EC) No 1394/2007 of the European Parliament and of the Council of 13 November 2007 on advanced therapy medicinal products and amending Directive 2001/83/EC and Regulation (EC) No 726/2004",
        "oj_reference": "L 324/121",
        "policy_area": "Health",
        "slug": "2007-1394_atmp",
        "action": "insert",
    },
    {
        "celex": "32010L0084",
        "doc_type": "Directive",
        "publication_date": "2010-12-31",
        "title_en": "Directive 2010/84/EU of the European Parliament and of the Council of 15 December 2010 amending, as regards pharmacovigilance, Directive 2001/83/EC on the Community code relating to medicinal products for human use",
        "oj_reference": "L 348/74",
        "policy_area": "Health",
        "slug": "2010-84_pharmacovigilance",
        "action": "replace",
    },
    {
        "celex": "32011L0062",
        "doc_type": "Directive",
        "publication_date": "2011-07-01",
        "title_en": "Directive 2011/62/EU of the European Parliament and of the Council of 8 June 2011 amending Directive 2001/83/EC on the Community code relating to medicinal products for human use, as regards the prevention of the entry into the legal supply chain of falsified medicinal products",
        "oj_reference": "L 174/74",
        "policy_area": "Health",
        "slug": "2011-62_falsified_medicines",
        "action": "update",
    },
    {
        "celex": "32012L0026",
        "doc_type": "Directive",
        "publication_date": "2012-10-27",
        "title_en": "Directive 2012/26/EU of the European Parliament and of the Council of 25 October 2012 amending Directive 2001/83/EC as regards pharmacovigilance",
        "oj_reference": "L 299/1",
        "policy_area": "Health",
        "slug": "2012-26_pv_amend",
        "action": "update",
    },
    {
        "celex": "32014R0536",
        "doc_type": "Regulation (EU) No",
        "publication_date": "2014-05-27",
        "title_en": "Regulation (EU) No 536/2014 of the European Parliament and of the Council of 16 April 2014 on clinical trials on medicinal products for human use, and repealing Directive 2001/20/EC",
        "oj_reference": "L 158/1",
        "policy_area": "Health",
        "slug": "2014-536_ctr",
        "action": "insert",
    },
]


def build_row(spec: dict, header: list[str], existing: dict | None) -> dict:
    """Build a full CSV row honouring the current header order."""
    base = {k: "" for k in header}
    if existing:
        base.update(existing)
    celex = spec["celex"]
    year = celex[1:5]
    number = celex[6:]
    slug = spec["slug"]
    override = {
        "celex": celex,
        "celex_form": celex[5],
        "celex_year": year,
        "celex_number": number,
        "doc_type_normalized": ("regulation" if celex[5] == "R" else "directive" if celex[5] == "L" else base.get("doc_type_normalized", "")),
        "doc_type": spec["doc_type"],
        "publication_date": spec["publication_date"],
        "title_en": spec["title_en"],
        "oj_reference": spec["oj_reference"],
        "policy_area": spec["policy_area"],
        "xml_path": "",
        "eurlex_url": _eurlex(celex),
        "canon_completed": "True",
        "canon_completed_at": CANON_COMPLETED_AT,
        "eucanon_url": _url(slug),
        "legal_family": LEGAL_FAMILY,
    }
    for k, v in override.items():
        if k in base:
            base[k] = v
    return base


def main() -> None:
    if not CSV_PATH.is_file():
        raise SystemExit(f"CSV not found: {CSV_PATH}")

    # Backup once.
    if not BACKUP_PATH.exists():
        shutil.copy2(CSV_PATH, BACKUP_PATH)
        print(f"[OK] backup -> {BACKUP_PATH.relative_to(ROOT)}")
    else:
        print(f"[SKIP] backup already exists: {BACKUP_PATH.relative_to(ROOT)}")

    # Load rows.
    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        header = list(reader.fieldnames or [])
        rows = list(reader)

    by_celex: dict[str, int] = {}
    for i, row in enumerate(rows):
        c = row.get("celex", "")
        if c and c not in by_celex:
            by_celex[c] = i

    inserted = replaced = updated = 0
    for spec in PHARMA_ROWS:
        celex = spec["celex"]
        action = spec["action"]
        idx = by_celex.get(celex)

        if action == "insert":
            if idx is not None:
                print(f"[WARN] {celex} spec=insert but row exists; skipping (use replace/update in spec).")
                continue
            rows.append(build_row(spec, header, existing=None))
            inserted += 1
            print(f"[INSERT] {celex} :: {spec['slug']}")

        elif action == "replace":
            if idx is None:
                print(f"[WARN] {celex} spec=replace but row absent; inserting instead.")
                rows.append(build_row(spec, header, existing=None))
                inserted += 1
                continue
            old = rows[idx]
            rows[idx] = build_row(spec, header, existing=None)
            replaced += 1
            print(f"[REPLACE] {celex} :: old title '{(old.get('title_en') or '')[:60]}...' -> pharma Directive")

        elif action == "update":
            if idx is None:
                print(f"[WARN] {celex} spec=update but row absent; inserting instead.")
                rows.append(build_row(spec, header, existing=None))
                inserted += 1
                continue
            row = rows[idx]
            row["canon_completed"] = "True"
            row["canon_completed_at"] = CANON_COMPLETED_AT
            row["eucanon_url"] = _url(spec["slug"])
            row["legal_family"] = LEGAL_FAMILY
            rows[idx] = row
            updated += 1
            print(f"[UPDATE] {celex} :: marked complete ({spec['slug']})")

    # Write out.
    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)

    print()
    print(f"[DONE] inserted={inserted} replaced={replaced} updated={updated} total_rows={len(rows)}")


if __name__ == "__main__":
    main()

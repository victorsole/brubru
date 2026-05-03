"""
Backfill title / dg_responsible / procedure_ref on commission_documents
rows by reading the Cellar RDF metadata for each CELEX.

Sources used (no fabrication):
  - title           → <cdm:title xml:lang="en">…</cdm:title>
  - dg_responsible  → <cdm:resource_legal_service_responsible>…</…>
  - procedure_ref   → resolve cdm:work_related_to_work target CELEX
                      against legislative_carriages.celex_numbers
                      → oeil_procedure_ref

Run:
    python3.12 backend/scripts/backfill_commission_documents_metadata.py            # dry-run, 5 rows
    python3.12 backend/scripts/backfill_commission_documents_metadata.py --apply
    python3.12 backend/scripts/backfill_commission_documents_metadata.py --apply --limit 200
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
USER_AGENT = "Mozilla/5.0 (compatible; BrubruIngest/1.0)"

CDM = "{http://publications.europa.eu/ontology/cdm#}"
RDF = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
XML = "{http://www.w3.org/XML/1998/namespace}"


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


def fetch_cellar_rdf(celex: str, timeout: int = 20) -> Optional[bytes]:
    url = f"http://publications.europa.eu/resource/celex/{celex}"
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/rdf+xml", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception:
        return None


def parse_metadata(xml_bytes: bytes) -> Dict[str, Optional[object]]:
    """Return dict with title_en, dg, related_celex (list of CELEX strings)."""
    out: Dict[str, Optional[object]] = {"title_en": None, "dg": None, "related_celex": []}
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return out

    titles_long_en: List[str] = []
    titles_long_any: List[str] = []
    related: List[str] = []

    for desc in root.findall(RDF + "Description"):
        # Iterate every child element under each Description
        for child in desc:
            tag = child.tag

            if tag == CDM + "title":
                # The 'subtitle' / short form is "SWD/2026/119 final"; the
                # long form has no slash and is at least 30 chars.
                text = (child.text or "").strip()
                if not text or len(text) < 20 or "/" in text and len(text) < 80:
                    continue
                lang = child.get(XML + "lang") or ""
                if lang.lower() == "en":
                    titles_long_en.append(text)
                else:
                    titles_long_any.append(text)
            elif tag == CDM + "expression_title":
                text = (child.text or "").strip()
                lang = child.get(XML + "lang") or ""
                if text and len(text) >= 20 and lang.lower() == "en":
                    titles_long_en.append(text)
            elif tag == CDM + "resource_legal_service_responsible":
                text = (child.text or "").strip()
                if text and not out["dg"]:
                    out["dg"] = text
            elif tag == CDM + "work_related_to_work":
                resource = child.get(RDF + "resource") or ""
                m = re.search(r"/resource/celex/(\d{5}[A-Z]{1,2}\d{4,5})$", resource)
                if m:
                    related.append(m.group(1))

    if titles_long_en:
        # Prefer the longest distinct English title.
        out["title_en"] = max(set(titles_long_en), key=len)
    elif titles_long_any:
        out["title_en"] = max(set(titles_long_any), key=len)

    out["related_celex"] = list({c for c in related})
    return out


def is_placeholder(title: Optional[str]) -> bool:
    if not title:
        return True
    return bool(re.match(r"^(SWD|COM|JOIN|C|JOIN)\s*document\s+\d", title))


def lookup_proc_ref_for_celex(cur, com_celex: str) -> Optional[str]:
    """legislative_carriages.celex_numbers is a String[] — match the COM CELEX."""
    cur.execute(
        "SELECT oeil_procedure_ref FROM legislative_carriages WHERE %s = ANY(celex_numbers) LIMIT 1",
        (com_celex,),
    )
    row = cur.fetchone()
    return row[0] if row else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()

    db_url = get_env("DATABASE_URL")
    if not db_url:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id::text, celex, title, dg_responsible, procedure_ref
          FROM commission_documents
         WHERE celex IS NOT NULL
           AND (
                title ~ '^(SWD|COM|JOIN|C)\\s+document\\s+\\d'
             OR dg_responsible IS NULL
             OR procedure_ref IS NULL
           )
         ORDER BY publication_date DESC NULLS LAST
         LIMIT %s
        """,
        (args.limit,),
    )
    rows = cur.fetchall()
    cur.close()
    print(f"[INFO] {len(rows)} rows queued (apply={args.apply})")

    updated = unchanged = failed = 0
    for row_id, celex, title, dg, proc_ref in rows:
        xml_bytes = fetch_cellar_rdf(celex)
        if not xml_bytes:
            print(f"  [ERR] {celex}: Cellar fetch failed")
            failed += 1
            continue

        meta = parse_metadata(xml_bytes)
        new_title: Optional[str] = None
        if is_placeholder(title) and meta["title_en"]:
            new_title = meta["title_en"][:1000]

        new_dg = meta["dg"] if (not dg and meta["dg"]) else None

        new_proc_ref: Optional[str] = None
        if not proc_ref and meta["related_celex"]:
            cur2 = conn.cursor()
            for rel_celex in meta["related_celex"]:
                resolved = lookup_proc_ref_for_celex(cur2, rel_celex)
                if resolved:
                    new_proc_ref = resolved
                    break
            cur2.close()

        if not (new_title or new_dg or new_proc_ref):
            unchanged += 1
            print(f"  [.] {celex}: nothing to update")
            continue

        changes = []
        if new_title:
            changes.append(f"title({len(new_title)}c)")
        if new_dg:
            changes.append(f"dg={new_dg}")
        if new_proc_ref:
            changes.append(f"proc={new_proc_ref}")
        print(f"  [OK] {celex}: {', '.join(changes)}")
        updated += 1

        if args.apply:
            sets = []
            params: List[object] = []
            if new_title:
                sets.append("title = %s")
                params.append(new_title)
            if new_dg:
                sets.append("dg_responsible = %s")
                params.append(new_dg)
            if new_proc_ref:
                sets.append("procedure_ref = %s")
                params.append(new_proc_ref)
            sets.append("last_updated = NOW()")
            params.append(row_id)
            cur3 = conn.cursor()
            cur3.execute(
                f"UPDATE commission_documents SET {', '.join(sets)} WHERE id = %s",
                params,
            )
            conn.commit()
            cur3.close()

        time.sleep(0.2)  # be polite to Cellar

    conn.close()
    print(f"[DONE] updated={updated} unchanged={unchanged} failed={failed}{' (applied)' if args.apply else ' (dry-run)'}")


if __name__ == "__main__":
    main()

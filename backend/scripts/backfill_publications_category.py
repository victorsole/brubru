"""
Derive `category` for institutional_publications rows that don't have one,
based on the source_slug.

Rule of thumb (no fabrication):
  *_press / *_press_release / EUI agencies' news feeds → press_release
  *_news / *_caselaw → news
  *_careers / epso / eu_careers / *_jobs → job_posting
  *_data / *_indicators → data_release
  *_guidelines / *_recommendations → guidance
  *_research / ec_jrc_* / eprs / stoa / jrc / iss → research_publication
  Everything else → news (the safest default for institutional sites).

Run:
    python3.12 backend/scripts/backfill_publications_category.py            # dry-run
    python3.12 backend/scripts/backfill_publications_category.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


def derive_category(source_slug: str, institution_slug: str = "") -> str:
    """Map a Brubru source slug to a Brubru-canonical category."""
    s = (source_slug or "").lower()
    if "press" in s or s in ("ecb_press", "fra_news", "consilium_press"):
        return "press_release"
    if s in ("epso", "eu_careers") or "career" in s or "_jobs" in s:
        return "job_posting"
    if "_data" in s or "_indicators" in s or "_stats" in s:
        return "data_release"
    if "guideline" in s or "recommendation" in s or s in ("edpb",):
        return "guidance"
    if (
        s.startswith("ec_jrc_")
        or "jrc" in s
        or s in ("eprs", "stoa", "iss")
        or "research" in s
        or "publication" in s
    ):
        return "research_publication"
    if "_news" in s or s in ("frontex", "cepol", "eige", "era", "berec", "esma", "acer", "srb",
                              "eesc", "cor_pes", "ec_education", "ec_culture"):
        return "news"
    if "caselaw" in s or "_caselaw" in s:
        return "case_law"
    return "news"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=2000)
    args = ap.parse_args()

    db_url = get_env("DATABASE_URL")
    if not db_url:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id::text, source_slug, institution_slug, category
          FROM institutional_publications
         WHERE category IS NULL
         LIMIT %s
        """,
        (args.limit,),
    )
    rows = cur.fetchall()
    cur.close()
    print(f"[INFO] {len(rows)} rows queued (apply={args.apply})")

    by_cat = {}
    for row_id, src, inst, cat in rows:
        new_cat = derive_category(src, inst or "")
        by_cat[new_cat] = by_cat.get(new_cat, 0) + 1
        if args.apply:
            cur2 = conn.cursor()
            cur2.execute(
                "UPDATE institutional_publications SET category = %s WHERE id = %s",
                (new_cat, row_id),
            )
            cur2.close()

    if args.apply:
        conn.commit()

    conn.close()
    print(f"[DONE] {sum(by_cat.values())} rows categorised:")
    for c, n in sorted(by_cat.items(), key=lambda kv: -kv[1]):
        print(f"  {c}: {n}")


if __name__ == "__main__":
    main()

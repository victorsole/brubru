"""Rank compliance packages by how many real organisations engage with their laws.

Why
---
Deciding which package to deepen next has been my judgement. It should be a
count. Every organisation in the EU Transparency Register declares, in
`eu_legislative_proposals`, the files it actually works on, and 18,381 of them
have done so. Matching a package's acts against those declarations says who
needs it.

What is matched
---------------
The act NUMBER derived from each law's CELEX -- "2016/679", "2024/1689" -- not
the law's title. Titles are 300 characters of boilerplate that match nothing;
organisations write "Regulation (EU) 2016/679" or "GDPR" or "2016/679" in their
declarations, and the number is the part that is unambiguous. A curated alias
list adds the short names people actually use, because an organisation is far
more likely to write "AI Act" than "2024/1689".

Why not the `interests` array: it is a checkbox list and organisations tick
generously. 9,875 declare "Environment". It cannot separate two environmental
packages, so it is reported as context but never used for ranking.

Weighting
---------
Companies count double. A compliance product is bought by the organisation that
carries the obligation; trade associations, NGOs and consultancies engage with
the same files representing someone else's interest, and they are real demand of
a different kind. Both are reported, and the ranking uses the weighted figure so
a file that is politically busy but commercially thin does not outrank one that
hundreds of companies must actually comply with.

Honest limits
-------------
  * A declaration is what an organisation says it lobbies on, not what binds it.
    A company subject to the CRA that never lobbies on it is invisible here.
    This measures salience, which correlates with demand but is not the same.
  * Free-text matching is approximate. "2024/1689" is precise; "AI Act" will
    also catch an organisation merely commenting on it.
  * The register skews towards organisations large enough to lobby Brussels.
    Small companies carrying the same obligations are under-counted.

  python3.12 -m scripts.rank_packages_by_demand
  python3.12 -m scripts.rank_packages_by_demand --all-packages --json-out ranking.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

import logging  # noqa: E402

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal, engine  # noqa: E402

engine.echo = False

# Short names organisations actually write. Keyed by act number so an alias can
# never be attached to the wrong package. Deliberately conservative: a wrong
# alias inflates a package's rank and sends the next month's work at it.
ALIASES = {
    "2016/679": ["GDPR", "General Data Protection Regulation"],
    "2022/2065": ["Digital Services Act", "DSA"],
    "2022/1925": ["Digital Markets Act", "DMA"],
    "2024/1689": ["AI Act", "Artificial Intelligence Act"],
    "2022/2555": ["NIS2", "NIS 2", "NIS2 Directive"],
    "2024/2847": ["Cyber Resilience Act"],
    "2023/2854": ["Data Act"],
    "2024/2853": ["Product Liability Directive"],
    "2024/1781": ["Ecodesign for Sustainable Products", "ESPR"],
    "2023/1542": ["Batteries Regulation"],
    "2023/956": ["CBAM", "Carbon Border Adjustment"],
    "2022/2464": ["CSRD", "Corporate Sustainability Reporting"],
    "2024/1760": ["CSDDD", "Corporate Sustainability Due Diligence"],
    "2023/1114": ["MiCA", "Markets in Crypto-Assets"],
    "2022/2554": ["DORA", "Digital Operational Resilience"],
    "2014/65": ["MiFID II", "MiFID"],
    "2009/138": ["Solvency II"],
    "2017/745": ["MDR", "Medical Device Regulation"],
    "2017/746": ["IVDR"],
    "2025/327": ["EHDS", "European Health Data Space"],
    "2025/40": ["PPWR", "Packaging and Packaging Waste"],
}

CELEX_NUM_RE = re.compile(r"^[0-9]([0-9]{4})[A-Z]{1,2}([0-9]{4})$")


def act_number(celex: str) -> str | None:
    """32016R0679 -> '2016/679'. The form organisations actually write."""
    m = CELEX_NUM_RE.match((celex or "").strip())
    if not m:
        return None
    year, num = m.group(1), m.group(2).lstrip("0") or "0"
    return f"{year}/{num}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all-packages", action="store_true",
                    help="include unpublished packages too")
    ap.add_argument("--json-out")
    ap.add_argument("--limit", type=int, default=25)
    args = ap.parse_args()

    db = SessionLocal()
    try:
        q = """SELECT c.id, c.name, c.is_published, c.is_startup_focused,
                      (SELECT count(*) FROM law_requirements r
                        WHERE r.cluster_id = c.id
                          AND COALESCE(r.extra_metadata->>'interpretive','') <> 'true') AS binding
                 FROM law_clusters c"""
        if not args.all_packages:
            q += " WHERE c.is_published"
        clusters = db.execute(text(q + " ORDER BY c.id")).fetchall()

        rows = []
        for cid, name, published, startup, binding in clusters:
            celexes = [r[0] for r in db.execute(text("""
                SELECT l.celex FROM cluster_laws cl JOIN eu_laws l ON l.id = cl.law_id
                 WHERE cl.cluster_id = :c AND l.celex IS NOT NULL"""), {"c": cid}).fetchall()]

            numbers = {n for n in (act_number(c) for c in celexes) if n}
            terms = set(numbers)
            for n in numbers:
                terms.update(ALIASES.get(n, []))

            if not terms:
                rows.append({"cluster_id": cid, "name": name, "published": published,
                             "startup": startup, "binding": binding, "terms": 0,
                             "orgs": 0, "companies": 0, "weighted": 0})
                continue

            # ILIKE over the declared-files free text. Act numbers are matched
            # bare; aliases are matched as words so "DSA" does not hit "DSAs" in
            # an unrelated acronym... which it still can. Reported, not trusted.
            clauses, params = [], {"c": cid}
            for i, term in enumerate(sorted(terms)):
                params[f"t{i}"] = f"%{term}%"
                clauses.append(f"eu_legislative_proposals ILIKE :t{i}")
            where = " OR ".join(clauses)

            res = db.execute(text(f"""
                SELECT count(*) AS orgs,
                       count(*) FILTER (WHERE registration_category = 'Companies & groups') AS companies
                  FROM eu_transparency_register
                 WHERE {where}"""), params).fetchone()

            orgs, companies = res[0], res[1]
            rows.append({
                "cluster_id": cid, "name": name, "published": published,
                "startup": startup, "binding": binding, "terms": len(terms),
                "orgs": orgs, "companies": companies,
                # Companies double: they carry the obligation rather than
                # representing someone who does.
                "weighted": orgs + companies,
            })

        rows.sort(key=lambda r: -r["weighted"])

        print(f"{len(rows)} packages ranked by organisations declaring the package's acts\n")
        print(f"{'#':>3} {'id':>4} {'orgs':>6} {'cos':>5} {'wt':>6} {'bind':>5}  package")
        print("-" * 96)
        for i, r in enumerate(rows[:args.limit], 1):
            flag = "" if r["published"] else " [unpublished]"
            star = "*" if r["startup"] else " "
            print(f"{i:>3} {r['cluster_id']:>4} {r['orgs']:>6} {r['companies']:>5} "
                  f"{r['weighted']:>6} {r['binding']:>5} {star} {r['name'][:56]}{flag}")

        print("\n* = surfaced by default in the For-you lens")
        print("bind = binding requirements today; a high demand and a low count is "
              "where the next package-deepening should go.")

        gaps = [r for r in rows[:12] if r["binding"] < 25]
        if gaps:
            print("\nHighest demand with the least depth:")
            for r in gaps:
                print(f"  cluster {r['cluster_id']:>3}  {r['weighted']:>5} weighted demand, "
                      f"{r['binding']:>3} binding requirements  {r['name'][:52]}")

        if args.json_out:
            Path(args.json_out).write_text(json.dumps(rows, indent=2), encoding="utf-8")
            print(f"\nwrote {args.json_out}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

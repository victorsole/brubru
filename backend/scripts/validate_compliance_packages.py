"""Audit every compliance package against the rules in package_spec.py.

The three packages rebuilt on 10 August 2026 had each been broken since they
were seeded, and were found by a person reading rows. The rules they violated
are all mechanical: a law advertised with no requirements attached, every
requirement marked critical, obligations that bind a supervisory authority put
to a company. This runs those rules over the whole catalogue in a few seconds.

  python3.12 -m scripts.validate_compliance_packages --all
  python3.12 -m scripts.validate_compliance_packages --cluster 17 --verbose
  python3.12 -m scripts.validate_compliance_packages --all --export data/compliance_packages
  python3.12 -m scripts.validate_compliance_packages --all --strict     # exit 1 on any error

`--export` writes one YAML file per package, so a package becomes a reviewable
artefact in version control rather than a set of rows nobody has read. That is
the other half of the fix: the validator catches what is checkable, and a diff
catches what is not.

Exit codes: 0 clean (or warnings only), 1 errors found under --strict, 2 the
run itself failed.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

import logging  # noqa: E402

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

import yaml  # noqa: E402
from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal, engine  # noqa: E402

# `echo=True` sets engine._echo, which SQLAlchemy checks as `_echo OR
# logger.isEnabledFor(INFO)`, so it bypasses logger levels entirely and the
# level set above does nothing (the same trap core/database.py documents for
# Railway). This is an audit tool whose output is meant to be read; clear the
# instance flag so 58 packages of SELECT statements do not bury the findings.
engine.echo = False
from services.compliance.package_spec import (  # noqa: E402
    Package, is_publishable, to_dict, validate,
)


def load_package(db, cluster_id: int) -> Package | None:
    row = db.execute(text("""
        SELECT id, name, policy_area, description, applicability,
               is_startup_focused, is_published
          FROM law_clusters WHERE id = :c"""), {"c": cluster_id}).fetchone()
    if not row:
        return None

    laws = [
        {"celex": r[0], "title": r[1]}
        for r in db.execute(text("""
            SELECT l.celex, l.title
              FROM cluster_laws cl JOIN eu_laws l ON l.id = cl.law_id
             WHERE cl.cluster_id = :c
             ORDER BY l.celex NULLS LAST"""), {"c": cluster_id}).fetchall()
    ]

    reqs = []
    for r in db.execute(text("""
            SELECT r.article, l.celex, r.criticality, r.applicable_entity,
                   r.deadline, r.requirement_text, r.extra_metadata
              FROM law_requirements r
              LEFT JOIN eu_laws l ON l.id = r.law_id
             WHERE r.cluster_id = :c
             ORDER BY r.id"""), {"c": cluster_id}).fetchall():
        meta = r[6] or {}
        reqs.append({
            "article": r[0],
            "law_celex": r[1],
            "criticality": r[2],
            "applicable_entity": r[3],
            "deadline": r[4].isoformat() if r[4] else None,
            "requirement_text": r[5],
            "addressee": meta.get("addressee") or "economic_operator",
            "interpretive": meta.get("interpretive"),
        })

    return Package(
        id=row[0], name=row[1], policy_area=row[2], description=row[3],
        applicability=row[4], is_startup_focused=bool(row[5]),
        is_published=bool(row[6]), laws=laws, requirements=reqs,
    )


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s[:70] or "package"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="validate every package")
    ap.add_argument("--cluster", type=int, help="validate one package")
    ap.add_argument("--published-only", action="store_true",
                    help="skip packages already unpublished")
    ap.add_argument("--export", help="directory to write one YAML file per package")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any error is found")
    ap.add_argument("--verbose", action="store_true", help="list every finding")
    args = ap.parse_args()

    if not args.all and not args.cluster:
        ap.error("pass --all or --cluster N")

    db = SessionLocal()
    try:
        if args.cluster:
            ids = [args.cluster]
        else:
            q = "SELECT id FROM law_clusters"
            if args.published_only:
                q += " WHERE is_published"
            ids = [r[0] for r in db.execute(text(q + " ORDER BY id")).fetchall()]

        export_dir = Path(args.export) if args.export else None
        if export_dir:
            export_dir.mkdir(parents=True, exist_ok=True)

        total_errors = total_warnings = 0
        by_code: Counter = Counter()
        broken: list[tuple[int, str, int, int]] = []

        for cid in ids:
            pkg = load_package(db, cid)
            if not pkg:
                print(f"  cluster {cid}: not found")
                continue

            findings = validate(pkg)
            errs = [f for f in findings if f.severity == "error"]
            warns = [f for f in findings if f.severity == "warning"]
            total_errors += len(errs)
            total_warnings += len(warns)
            for f in findings:
                by_code[f.code] += 1

            if errs or warns:
                broken.append((cid, pkg.name, len(errs), len(warns)))

            if args.verbose or errs or args.cluster:
                flag = "" if is_publishable(findings) else "  <- NOT PUBLISHABLE"
                state = "published" if pkg.is_published else "unpublished"
                print(f"\ncluster {cid:>3} [{state}] {pkg.name[:62]}{flag}")
                print(f"  {len(pkg.laws)} laws, {len(pkg.requirements)} requirements, "
                      f"{len(pkg.binding())} binding, {len(pkg.not_yours())} bind someone else")
                for f in findings:
                    print(f"  {f}")

            if export_dir:
                path = export_dir / f"{cid:03d}_{slugify(pkg.name)}.yaml"
                path.write_text(
                    yaml.safe_dump(to_dict(pkg), sort_keys=False, allow_unicode=True,
                                   width=88, default_flow_style=False),
                    encoding="utf-8")

        print("\n" + "=" * 72)
        print(f"{len(ids)} packages checked: {total_errors} errors, {total_warnings} warnings")
        if by_code:
            print("\nby rule:")
            for code, n in by_code.most_common():
                print(f"  {n:>4}  {code}")
        if broken:
            print(f"\n{len(broken)} packages with findings (errors first):")
            for cid, name, e, w in sorted(broken, key=lambda x: (-x[2], -x[3])):
                if e or w:
                    print(f"  cluster {cid:>3}  {e:>2}E {w:>2}W  {name[:58]}")
        if export_dir:
            print(f"\nexported {len(ids)} package files to {export_dir}")

        if args.strict and total_errors:
            return 1
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

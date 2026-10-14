"""Repair the secondary_acts rows the 14 Oct 2026 delegated-acts audit found wrong. One-off.

Each value is read from its authority (the Publications Office's Cellar, the act's own
Official Journal header, or Cellar's title), never derived:

  1. 676 acts inserted on 10 Aug 2026 by backfill_regulatory_cascade.py, outside the RegDel
     register, said 'adopted' though each has a CELEX and an Official Journal date: Cellar
     holds all 676, so they are published.
  2. Two of them sat under delegated acts but are implementing regulations (Cellar
     resource type REG_IMPL): 2021/637 and 2026/1228.
  3. Two delegated acts held a corrigendum's CELEX as their own, because the register
     exports it so (C(2014)5033 -> 32014R1014R(03)); and C(2014)5033 also held the
     corrigendum's dates. They get the act's CELEX and the act's dates.
  4. Regulation 2025/1190 was held twice: as C(2025)885 from the register (which still
     lists it as 'scrutiny finished', without a CELEX) and as a CELEX-keyed row holding the
     Official Journal text. The register row keeps its id and takes the CELEX, the status
     and the text; the other row is recorded in its merged_from and removed.
  5. Published acts still titled as drafts ("(EU) …/...") take the final title the
     Publications Office gives the CELEX.

Not here, because the feed now does them on every run: policy areas kept whole, a CELEX
used as a reference replaced by the C-number, planned rows the register no longer lists.

Only a row still holding the value that was checked is written. `--rehearse` (the default)
prints and writes nothing; `--apply` saves the rows' previous values first.

    python3.12 scripts/repair_secondary_acts.py
    python3.12 scripts/repair_secondary_acts.py --apply
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine, text  # noqa: E402

SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"
DRAFT = r"(…|\.\.\.)\s*/\s*(…|\.\.\.)"
DELEGATED_TYPES = {"REG_DEL", "DIR_DEL", "DEC_DEL"}
IMPLEMENTING_TYPES = {"REG_IMPL", "DIR_IMPL", "DEC_IMPL"}

# Fix 3: read from Cellar (work_date_document) and the Official Journal header on 14 Oct
# 2026: 32014R1014 adopted 22.7.2014, OJ 27.9.2014; 32024R1261 adopted 11.3.2024, OJ L
# series 2024/1261 of 8.5.2024.
CORRIGENDUM_CELEX = {
    "C(2014)5033": ("32014R1014R(03)", "32014R1014", date(2014, 7, 22), date(2014, 9, 27)),
    "C(2024)1454": ("32024R1261R(01)", "32024R1261", date(2024, 3, 11), date(2024, 5, 8)),
}
# Fix 4: the register row and the duplicate holding the CELEX.
DUPLICATE = ("C(2025)885", "32025R1190")


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        m = re.search(r"^DATABASE_URL=(.*)$", (BACKEND / ".env").read_text(), re.M)
        url = m.group(1).strip() if m else ""
    return url


def cellar_types(celexes: list[str]) -> dict[str, set[str]]:
    """Each CELEX's Cellar resource types (REG_DEL, REG_IMPL, ...)."""
    out: dict[str, set[str]] = {}
    for i in range(0, len(celexes), 150):
        values = " ".join(f'"{c}"^^<http://www.w3.org/2001/XMLSchema#string>' for c in celexes[i:i + 150])
        q = ("PREFIX cdm: <http://publications.europa.eu/ontology/cdm#> SELECT ?celex ?t WHERE { "
             f"VALUES ?celex {{ {values} }} ?w cdm:resource_legal_id_celex ?celex . "
             "?w cdm:work_has_resource-type ?t . }")
        req = urllib.request.Request(SPARQL, data=urllib.parse.urlencode({"query": q}).encode(),
                                     headers={"Accept": "application/sparql-results+json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            for b in json.loads(r.read())["results"]["bindings"]:
                out.setdefault(b["celex"]["value"], set()).add(b["t"]["value"].rsplit("/", 1)[1])
    return out


def plan(conn) -> list[dict]:
    """Every change, with the value it replaces."""
    changes: list[dict] = []
    outside = conn.execute(text("""
        SELECT id, reference, celex, act_type::text AS act_type, status::text AS status
          FROM secondary_acts
         WHERE reference ~ '^3' AND regdel_id IS NULL AND act_type IN ('delegated', 'implementing')
           AND status = 'adopted' AND coalesce(celex, '') <> '' AND publication_date IS NOT NULL
           AND reference <> :dup""").bindparams(dup=DUPLICATE[1])).fetchall()
    types = cellar_types([r.celex for r in outside])
    for r in outside:
        t = types.get(r.celex, set())
        if not t:
            continue                       # not in Cellar: nothing to state
        changes.append({"fix": 1, "id": r.id, "ref": r.reference, "col": "status",
                        "old": r.status, "new": "published"})
        if r.act_type == "delegated" and t & IMPLEMENTING_TYPES and not t & DELEGATED_TYPES:
            changes.append({"fix": 2, "id": r.id, "ref": r.reference, "col": "act_type",
                            "old": "delegated", "new": "implementing"})
    for ref, (bad, good, adopted, published) in CORRIGENDUM_CELEX.items():
        row = conn.execute(text("SELECT id, celex, adoption_date, publication_date FROM secondary_acts "
                                "WHERE reference = :r"), {"r": ref}).first()
        if row and row.celex == bad:
            for col, old, new in (("celex", row.celex, good), ("adoption_date", row.adoption_date, adopted),
                                  ("publication_date", row.publication_date, published)):
                if old != new:
                    changes.append({"fix": 3, "id": row.id, "ref": ref, "col": col, "old": old, "new": new})
    keep = conn.execute(text("SELECT id, celex FROM secondary_acts WHERE reference = :r"),
                        {"r": DUPLICATE[0]}).first()
    gone = conn.execute(text("SELECT id FROM secondary_acts WHERE reference = :r AND celex = :r"),
                        {"r": DUPLICATE[1]}).first()
    if keep and gone and not keep.celex:
        changes.append({"fix": 4, "id": keep.id, "ref": DUPLICATE[0], "col": "merge",
                        "old": str(gone.id), "new": DUPLICATE[1]})
    titles = conn.execute(text(f"""
        SELECT s.id, s.reference, s.title AS old, l.title AS new
          FROM secondary_acts s JOIN eu_laws l ON l.celex = s.celex
         WHERE s.status = 'published' AND s.title ~ '{DRAFT}' AND l.title !~ '{DRAFT}'
           AND l.title ~* '^\\s*Commission (Delegated|Implementing) '""")).fetchall()
    for r in titles:
        changes.append({"fix": 5, "id": r.id, "ref": r.reference, "col": "title", "old": r.old,
                        "new": re.sub(r"\s+", " ", r.new).strip()})
    return changes


def apply(engine, changes: list[dict]) -> int:
    written = 0
    with engine.begin() as conn:
        for c in changes:
            if c["fix"] == 4:
                gone_id = c["old"]
                src = conn.execute(text("SELECT reference, first_seen, text_body, body_html FROM secondary_acts "
                                        "WHERE id = :g"), {"g": gone_id}).one()
                conn.execute(text("UPDATE secondary_acts SET celex = NULL WHERE id = :g"), {"g": gone_id})
                entry = json.dumps([{"id": gone_id, "reference": src.reference, "first_seen": str(src.first_seen),
                                     "source": "regulatory_cascade_duplicate", "merged": "2026-10-14"}])
                n = conn.execute(text("""
                    UPDATE secondary_acts
                       SET celex = :celex, status = 'published', text_body = :txt, body_html = :html,
                           body_source = 'official_journal',
                           merged_from = coalesce(merged_from, '[]'::jsonb) || CAST(:entry AS jsonb)
                     WHERE id = :id AND coalesce(celex, '') = ''"""),
                                 {"celex": c["new"], "txt": src.text_body, "html": src.body_html,
                                  "entry": entry, "id": c["id"]}).rowcount
                if n:
                    conn.execute(text("DELETE FROM secondary_acts WHERE id = :g"), {"g": gone_id})
                written += n
                continue
            col = c["col"]
            cast = "::secondary_act_status_enum" if col == "status" else (
                "::secondary_act_type_enum" if col == "act_type" else "")
            old_match = (f"{col}::text = :old" if col in ("status", "act_type")
                         else f"{col} IS NOT DISTINCT FROM :old")
            extra = ", body_fetched_at = NULL" if col == "celex" else ""   # fetch the act's own text
            written += conn.execute(text(
                f"UPDATE secondary_acts SET {col} = CAST(:new AS text){cast}{extra} WHERE id = :id AND {old_match}"
                if cast else
                f"UPDATE secondary_acts SET {col} = :new{extra} WHERE id = :id AND {old_match}"),
                {"new": c["new"], "old": c["old"], "id": c["id"]}).rowcount
    return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    engine = create_engine(database_url())
    with engine.connect() as conn:
        changes = plan(conn)
    by_fix: dict[int, int] = {}
    for c in changes:
        by_fix[c["fix"]] = by_fix.get(c["fix"], 0) + 1
    for c in changes:
        if c["fix"] != 1:
            print(f"  fix {c['fix']} {c['ref']}: {c['col']} {str(c['old'])[:60]!r} -> {str(c['new'])[:80]!r}")
    print(f"[repair] changes by fix: {dict(sorted(by_fix.items()))}")
    if not args.apply:
        print("[repair] rehearsal: nothing written")
        return 0
    backup = BACKEND / "data" / "backups" / f"secondary_acts_before_repair_{date.today().isoformat()}.csv"
    backup.parent.mkdir(parents=True, exist_ok=True)
    with backup.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["fix", "id", "reference", "column", "old", "new"])
        for c in changes:
            w.writerow([c["fix"], c["id"], c["ref"], c["col"], c["old"], c["new"]])
    written = apply(engine, changes)
    print(f"[repair] written {written} of {len(changes)}; previous values in {backup}")
    return 0 if written == len(changes) else 1


if __name__ == "__main__":
    sys.exit(main())

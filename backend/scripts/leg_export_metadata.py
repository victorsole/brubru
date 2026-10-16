"""The LEG_2026-10 export's metadata for one law, as eu_laws stores it (migration 293). No database imports.

One shaping for both writers of the columns: fill_eu_laws_export_metadata.py reads the tables built from the export
(backend/data/leg_2026-10_table/), import_corpus_update.py reads a folder's RDF through the very functions that built
those tables. A test compares the two.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
TABLES = ROOT / "backend/data/leg_2026-10_table"
COLS = ("alias", "acronym", "authors", "in_force", "eli", "entry_into_force", "procedures")


def procedure_numbers(cell: str) -> list:
    """'procedure:2019_145|internal_proc:ABC...' -> ['2019/0145'] (the OEIL reference without its type)."""
    out = []
    for p in (cell or "").split("|"):
        m = re.fullmatch(r"procedure:(\d{4})_0*(\d{1,4})", p.strip())
        if m:
            out.append(f"{m[1]}/{int(m[2]):04d}")
    return sorted(set(out))


def sources():
    table = {r["CELEX"]: r for r in csv.DictReader((TABLES / "leg_2026-10_table.csv").open(encoding="utf-8-sig"))}
    folders = {r["celex"]: r for r in csv.DictReader((TABLES / "leg_2026-10_folders.csv").open(encoding="utf-8-sig")) if r["celex"]}
    aliases = {r["celex"]: r for r in csv.DictReader((TABLES / "aliases.csv").open(encoding="utf-8-sig"))}
    return table, folders, aliases


def wanted(celex, status, table, folders, aliases) -> dict:
    """The values the export states for one law; None where it states nothing."""
    t, f, a = table.get(celex), folders.get(celex), aliases.get(celex)
    v = dict.fromkeys(COLS)
    if a:
        v["alias"], v["acronym"] = (a.get("alias") or "").strip() or None, (a.get("acronym") or "").strip() or None
    if t:
        v["authors"] = [x for x in (t.get("author") or "").split("|") if x] or None
        v["in_force"] = {"true": True, "false": False}.get((t.get("in_force") or "").strip())
        v["eli"] = (t.get("eli") or "").strip() or None
    elif status == "repealed":
        v["in_force"] = False  # marked repealed by the importer only when Cellar's in-force flag is 0
    if f:
        v["entry_into_force"] = sorted({d for d in (f.get("entry_into_force") or "").split("|") if d}) or None
        v["procedures"] = procedure_numbers(f.get("procedures")) or None
    return v


def export_metadata(corpus_path: Path, uuid: str, celex: Optional[str]) -> dict:
    """authors, in_force, eli, entry_into_force and procedures as one folder's metadata states them, read by
    build_leg_table.parse_folder and pick_eli and build_leg_folder_index.one. alias and acronym are not here:
    aliases.csv is their only source."""
    from backend.scripts.build_leg_folder_index import one
    from backend.scripts.build_leg_table import parse_folder, pick_eli
    rec, idx = parse_folder((str(corpus_path), uuid)), one((str(corpus_path), uuid))
    try:
        eli = pick_eli(rec, celex or rec["celex"] or "")
    except (TypeError, ValueError):  # no year or number in the metadata
        eli = ""
    t = {"author": rec["author"], "in_force": rec["in_force"] or "unknown", "eli": eli}
    w = wanted(celex, None, {celex: t}, {celex: idx}, {})
    return {k: v for k, v in w.items() if k not in ("alias", "acronym")}

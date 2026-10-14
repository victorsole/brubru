#!/usr/bin/env python3.12
"""Build the LEG_2026-10 links table: every act-to-act link stated in the export's metadata.

One row = "source act --link--> target act", exactly as the source's `tree_non_inferred.rdf` states it
(the metadata only states links outward, from the act that does the amending, citing, correcting...).
Nothing is inferred and no text is read. ALL 59,010 folders of the export are read: 30,246 hold Formex
text (`source_has_text` = yes) and 28,764 hold metadata only (scans were not extracted: mostly acts
before about 2005, and corrigenda). Reading only the first group missed 65,274 links. Families (groups of acts that belong together) are computed
from this table later; this script only records the links.

Outputs in --out (CSV UTF-8 with BOM):
  leg_2026-10_links.csv        source_celex, link_type, target_celex, link_group, source_has_text,
                               target_in_export, target_has_text, target_kind, source_base_celex,
                               target_base_celex
  leg_2026-10_procedures.csv   celex, procedure_id, procedure_kind (the dossier an act belongs to)
  links_qa.json                the counts behind the table, including what was dropped and why

link_group:  family  = the source changes, corrects, completes, implements or repeals the target
             context = the source cites, is based on, or is related to the target
             origin  = the source adopts (part of) a Commission proposal
base_celex = the CELEX without a corrigendum suffix `R(NN)`; a consolidated text (sector 0, `-YYYYMMDD`)
maps to its sector-3 act. A plain `(NN)` suffix is a DIFFERENT act and is kept.
based_on: toward a legal act (sector 3) it is `based_on_act`, group family (the empowering act of an
implementing or delegated act); toward a treaty or anything else it stays `based_on`, group context.

Usage (from the repo root):  python3.12 backend/scripts/build_leg_links.py
"""
from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import pathlib
import re
import urllib.parse
from collections import Counter

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])

# predicate (CDM) -> (link_type, link_group). Every predicate that links an act to another
# CELEX in the export, found by listing all predicates with a /resource/celex/ target (13 Oct 2026).
LINKS = {
    "work_cites_work": ("cites", "context"),
    "resource_legal_based_on_resource_legal": ("based_on", "context"),
    "work_related_to_work": ("related_to", "context"),
    "resource_legal_related_to_resource_legal": ("related_to", "context"),
    "resource_legal_influences_resource_legal": ("influences", "context"),
    "resource_legal_associates_agreement_international": ("associates_agreement", "context"),
    "work_contains_work": ("contains", "context"),
    "resource_legal_interpretes_authoritatively_resource_legal": ("interprets_authoritatively", "context"),
    "resource_legal_related_question_to_resource_legal": ("related_question", "context"),
    "resource_legal_amends_resource_legal": ("amends", "family"),
    "legislation_secondary_modifies_legislation_secondary": ("modifies", "family"),
    "resource_legal_does_replacement_of_resource_legal": ("replaces_provision_of", "family"),
    "resource_legal_does_insertion_of_resource_legal": ("inserts_provision_in", "family"),
    "resource_legal_does_deletion_of_resource_legal": ("deletes_provision_of", "family"),
    "resource_legal_adds_to_resource_legal": ("adds_to", "family"),
    "resource_legal_corrects_resource_legal": ("corrects", "family"),
    "resource_legal_completes_resource_legal": ("completes", "family"),
    "resource_legal_implements_resource_legal": ("implements", "family"),
    "resource_legal_repeals_resource_legal": ("repeals", "family"),
    "resource_legal_implicitly_repeals_resource_legal": ("implicitly_repeals", "family"),
    "resource_legal_does_repeal_of_resource_legal": ("repeals_provision_of", "family"),
    "resource_legal_replaces_resource_legal": ("replaces", "family"),
    "resource_legal_derogates_resource_legal": ("derogates_from", "family"),
    "resource_legal_extends_validity_of_resource_legal": ("extends_validity_of", "family"),
    "resource_legal_extends_application_resource_legal": ("extends_application_of", "family"),
    "resource_legal_suspends_resource_legal": ("suspends", "family"),
    "resource_legal_partially_suspends_resource_legal": ("partially_suspends", "family"),
    "resource_legal_defers_application_of_resource_legal": ("defers_application_of", "family"),
    "resource_legal_reestablishes_resource_legal": ("reestablishes", "family"),
    "resource_legal_incorporates_resource_legal": ("incorporates", "family"),
    "resource_legal_consolidated_by_act_consolidated": ("consolidated_by", "family"),
    "resource_legal_adopts_resource_legal": ("adopts_proposal", "origin"),
    "resource_legal_partially_adopts_resource_legal": ("partially_adopts_proposal", "origin"),
    "resource_legal_proposes_to_amend_resource_legal": ("proposes_to_amend", "origin"),
}
PRED = re.compile(r'<j\.0:(' + "|".join(map(re.escape, LINKS)) + r') rdf:resource="http://publications\.europa\.eu/resource/celex/([^"]+)"')
PROC = re.compile(r'<j\.0:work_part_of_dossier rdf:resource="http://publications\.europa\.eu/resource/([a-z_]+)/([^"]+)"')
OWN = re.compile(r"<j\.0:resource_legal_id_celex[^>]*>([^<]+)<")
CORR_RE = re.compile(r"(?:R\(\d{2}\))+$")
PADDED = re.compile(r"^(\d{5}[A-Z]{1,3})0(\d{4})$")


def base_of(c):
    if c.startswith("0"):
        c = "3" + c[1:]
    c = re.sub(r"-\d{8}$", "", c)
    return CORR_RE.sub("", c)
SECTOR_KIND = {"1": "treaty", "2": "international agreement", "3": "legal act", "4": "complementary legislation",
               "5": "preparatory document", "6": "EU case-law", "7": "national transposition measure",
               "8": "national case-law", "9": "parliamentary question", "0": "consolidated text", "C": "OJ C notice",
               "E": "EFTA document"}


def one(args):
    dump, folder = args
    s = (pathlib.Path(dump) / folder / "tree_non_inferred.rdf").read_text(encoding="utf-8", errors="replace")
    own = sorted({c.strip() for c in OWN.findall(s)})
    links = [(p, urllib.parse.unquote(t).strip()) for p, t in PRED.findall(s)]
    procs = sorted(set(PROC.findall(s)))
    has_text = (pathlib.Path(dump) / folder / "fmx4").is_dir()
    return folder, own, links, procs, has_text


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dump", default="docs/LEG_2026-10")
    ap.add_argument("--out", default="backend/data/leg_2026-10_table")
    a = ap.parse_args()
    root = pathlib.Path(_REPO_ROOT)
    dump = pathlib.Path(a.dump) if pathlib.Path(a.dump).is_absolute() else root / a.dump
    out = pathlib.Path(a.out) if pathlib.Path(a.out).is_absolute() else root / a.out
    out.mkdir(parents=True, exist_ok=True)

    all_dirs = sorted(p.name for p in dump.iterdir() if p.is_dir())
    folders = [f for f in all_dirs if (dump / f / "tree_non_inferred.rdf").exists()]
    with mp.Pool(8) as pool:
        res = pool.map(one, [(str(dump), f) for f in folders], chunksize=60)

    qa = {"folders_in_export": len(all_dirs), "folders_read": len(folders),
          "folders_without_metadata_file": len(all_dirs) - len(folders),
          "folders_with_text": sum(1 for r in res if r[4]), "folders_metadata_only": sum(1 for r in res if not r[4])}
    qa["folders_without_exactly_one_own_celex"] = sum(1 for r in res if len(r[1]) != 1)
    res = [r for r in res if len(r[1]) == 1]
    has_text = {r[1][0]: r[4] for r in res}
    qa["acts"] = len(has_text)
    qa["duplicate_own_celex_across_folders"] = len(res) - len(has_text)
    in_export = set(has_text)

    raw = Counter()
    rows, seen = [], set()
    dropped, normalised = Counter(), []
    rows_from_text = rows_from_meta = 0
    for _, own, links, _, _ in res:
        src = own[0]
        for pred, tgt in links:
            ltype, group = LINKS[pred]
            raw[pred] += 1
            m = PADDED.match(tgt)  # a padded spelling (31993R02454) may be a typo for 31993R2454 or a real CELEX:
            if m and (m.group(1) + m.group(2)) in in_export and tgt not in in_export:  # never merged, only reported
                normalised.append(tgt)
            if tgt == src:
                dropped["self_link"] += 1
                continue
            if ltype == "based_on" and tgt[:1] == "3":
                ltype, group = "based_on_act", "family"
            key = (src, ltype, tgt)
            if key in seen:
                dropped["duplicate"] += 1
                continue
            seen.add(key)
            kind = SECTOR_KIND.get(tgt[:1], "other")
            rows.append([src, ltype, tgt, group, "yes" if has_text[src] else "no",
                         "yes" if tgt in in_export else "no", "yes" if has_text.get(tgt) else "no", kind,
                         base_of(src), base_of(tgt)])
    rows.sort(key=lambda r: (r[0], r[3], r[1], r[2]))
    qa["links_found_in_metadata"] = sum(raw.values())
    qa["links_by_predicate_in_metadata"] = dict(raw)
    qa["dropped"] = dict(dropped)
    qa["padded_targets_with_an_unpadded_twin_in_export_NOT_merged"] = {"links": len(normalised), "targets": sorted(set(normalised))}
    qa["rows_written"] = len(rows)
    assert qa["links_found_in_metadata"] == len(rows) + sum(dropped.values()), "rows do not add up"
    qa["rows_by_source_has_text"] = dict(Counter(r[4] for r in rows))
    qa["rows_by_link_type"] = dict(Counter(r[1] for r in rows).most_common())
    qa["rows_by_group"] = dict(Counter(r[3] for r in rows))
    qa["target_in_export"] = dict(Counter(r[5] for r in rows))
    qa["target_has_text"] = dict(Counter(r[6] for r in rows))
    qa["target_in_export_by_group"] = {g: dict(Counter(r[5] for r in rows if r[3] == g)) for g in ("family", "context", "origin")}
    qa["target_kind"] = dict(Counter(r[7] for r in rows).most_common())
    qa["acts_with_an_outgoing_link"] = len({r[0] for r in rows})
    qa["acts_with_an_outgoing_family_link"] = len({r[0] for r in rows if r[3] == "family"})
    qa["acts_targeted_by_a_family_link"] = len({r[2] for r in rows if r[3] == "family" and r[5] == "yes"})

    with (out / "leg_2026-10_links.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["source_celex", "link_type", "target_celex", "link_group", "source_has_text", "target_in_export",
                    "target_has_text", "target_kind", "source_base_celex", "target_base_celex"])
        w.writerows(rows)

    procs = sorted((own[0], p[1], p[0]) for _, own, _, ps, _ in res for p in ps)
    with (out / "leg_2026-10_procedures.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["celex", "procedure_id", "procedure_kind"])
        w.writerows(procs)
    qa["procedure_rows_by_kind"] = dict(Counter(k for _, _, k in procs))
    qa["acts_with_a_procedure"] = len({c for c, _, _ in procs})
    qa["distinct_procedure_ids"] = len({(p, k) for _, p, k in procs})

    (out / "links_qa.json").write_text(json.dumps(qa, indent=1, ensure_ascii=False))
    print(json.dumps(qa, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()

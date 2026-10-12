#!/usr/bin/env python3.12
"""Deterministic trigger matrix: does a NATURAL question in each language reach the guide?

Why this exists (12 Oct 2026): `audit_guide_triggers.py` proved the 16,482 trigger keys were
well-formed, 0 duplicates and 0 orphans, while 27 of 90 natural questions matched NO trigger and
production told Italian, French and Spanish users "no sanctions were adopted on 12 October". A
structure audit cannot say whether anything fires. This calls the real production matcher,
`KnowledgeLoader.search_guides` (the offline language bridge plus Pass 1, no model, no network),
for every question in a data file and exits 1 on any MISS or negative LEAK.

Usage:  python3.12 scripts/check_trigger_matrix.py data/trigger_matrix/2026_10_12.json
Data:   {"languages": [...6...], "topics": {"<guide_id>[#label]": [6 questions]}, "negatives": [...]}
Run it before every push of guides and again after any trigger edit. Prints its denominators.
"""
import argparse
import json
import logging
import pathlib
import sys

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
sys.path.insert(0, f"{_REPO_ROOT}/backend")


def _trigger_ids(loader, question):
    """Guide ids matched by a keyword trigger, in the order the chat would use them."""
    return [m["id"] for m in loader.search_guides(question, "titles_only") if m.get("trigger_matched")]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("data", help="JSON file, relative to backend/ or absolute")
    args = ap.parse_args()
    path = pathlib.Path(args.data)
    if not path.is_absolute():
        path = pathlib.Path(_REPO_ROOT) / "backend" / path
    spec = json.loads(path.read_text(encoding="utf-8"))
    langs, topics, negatives = spec["languages"], spec["topics"], spec.get("negatives", [])

    logging.disable(logging.WARNING)
    from knowledge_base.knowledge_loader import KnowledgeLoader

    loader = KnowledgeLoader()
    loader.load_all()

    misses, asked = [], 0
    for key, questions in topics.items():
        gid = key.split("#")[0]
        if gid not in loader.guides:
            print(f"[ERROR] {key}: guide {gid} is not loaded")
            return 2
        if len(questions) != len(langs):
            print(f"[ERROR] {key}: {len(questions)} questions for {len(langs)} languages")
            return 2
        row = []
        for lang, q in zip(langs, questions):
            asked += 1
            ids = _trigger_ids(loader, q)
            pos = ids.index(gid) + 1 if gid in ids else 0
            row.append(f"{lang}:{pos or 'MISS'}")
            if not pos:
                misses.append((key, lang, q))
        print(f"{key[:58]:<58} " + " ".join(row))

    targets = {k.split("#")[0] for k in topics}
    leaks = []
    for q in negatives:
        hit = [g for g in _trigger_ids(loader, q) if g in targets]
        if hit:
            leaks.append((q, hit))

    print(f"\nExamined: {len(topics)} topics x {len(langs)} languages = {asked} questions; {len(negatives)} negatives.")
    print(f"MISSES: {len(misses)} of {asked}   LEAKS: {len(leaks)} of {len(negatives)}")
    for key, lang, q in misses:
        print(f"  MISS {key} [{lang}] {q}")
    for q, hit in leaks:
        print(f"  LEAK {q} -> {hit}")
    return 1 if misses or leaks else 0


if __name__ == "__main__":
    raise SystemExit(main())

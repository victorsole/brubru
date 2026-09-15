"""Repair social_accounts rows whose entity_name is a bare Wikidata QID.

Cause (found 15 Sep 2026): `services/social/wikidata_mep_loader.py` asked the WDQS label
service for "en" only. For people whose name lives only in the language-neutral `mul` label
(Bernd Lange, Peter Liese, ...) WDQS returns the QID itself as the label, and the loader
stored it. 18 rows / 8 MEPs were affected.

For each distinct bare-QID name: resolve the label from Wikidata EntityData (en, mul, the
MEP's own language, other EU languages), cross-check it against the EP Open Data current-MEP
directory via P1186 (MEP directory ID), and UPDATE only rows still carrying the bare QID.
Idempotent. No fabrication: a QID with no label anywhere, or a Wikidata label that
contradicts the EP directory, is left untouched and reported.

Usage:
  python3.12 scripts/repair_social_qid_names.py          # dry-run
  python3.12 scripts/repair_social_qid_names.py --apply
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
logging.disable(logging.WARNING)

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal, engine  # noqa: E402
engine.echo = False
from services.social.ep_mep_reconcile import _norm_name  # noqa: E402
from services.social.wikidata_mep_loader import (  # noqa: E402
    COUNTRY_LANG, ep_display_name, entity_ep_ids, fetch_ep_current, fetch_entity,
    is_bare_qid, pick_label)

_SELECT = text("SELECT id, entity_name, entity_key, platform, account_url, entity_type "
               "FROM social_accounts WHERE entity_name ~ '^Q[0-9]+$' ORDER BY entity_name, platform")


def resolve(qid: str, ep_dir: dict) -> dict:
    """{'name', 'source', 'ep_id', 'ep_name', 'note'}; name None means leave the rows alone."""
    out = {"name": None, "source": None, "ep_id": None, "ep_name": None, "note": ""}
    try:
        ent = fetch_entity(qid)
    except Exception as exc:  # noqa: BLE001
        out["note"] = f"Wikidata fetch failed ({type(exc).__name__})"
        return out
    ep_ids = entity_ep_ids(ent)
    ep_rec = next((ep_dir[e] for e in ep_ids if e in ep_dir), None)
    out["ep_id"] = ",".join(ep_ids) or None
    own_lang = COUNTRY_LANG.get((ep_rec or {}).get("api:country-of-representation"))
    wd_name, lang = pick_label(ent.get("labels", {}), own_lang)
    ep_name = ep_display_name(ep_rec) if ep_rec else None
    out["ep_name"] = ep_name
    if wd_name and ep_name:
        if _norm_name(wd_name) != _norm_name(ep_name) and not (
                set(_norm_name(ep_name).split()) <= set(_norm_name(wd_name).split())):
            out["note"] = f"Wikidata '{wd_name}' contradicts EP '{ep_name}' -- left for a human"
            return out
        out.update(name=wd_name, source=f"wikidata:{lang}", note="EP directory agrees")
    elif wd_name:
        out.update(name=wd_name, source=f"wikidata:{lang}",
                   note=("not in EP current-MEP list (P1186 " + (out["ep_id"] or "absent") + ")"))
    elif ep_name:
        out.update(name=ep_name, source="ep_directory", note="no Wikidata label; EP name used")
    else:
        out["note"] = "no label in any language and no EP directory match"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    ep_dir = fetch_ep_current()
    print(f"EP current-MEP directory: {len(ep_dir)} records")
    db = SessionLocal()
    try:
        before = db.execute(_SELECT).mappings().all()
        print(f"\nBEFORE: {len(before)} row(s) with a bare-QID entity_name")
        for r in before:
            print(f"  {r['id']:>6}  {r['entity_name']:<12} {r['platform']:<10} {r['account_url']}")

        qids = sorted({r["entity_name"] for r in before if is_bare_qid(r["entity_name"])})
        unresolved = []
        print("\nRESOLUTION")
        for q in qids:
            res = resolve(q, ep_dir)
            time.sleep(0.5)
            print(f"  {q:<12} -> {res['name'] or '(unresolved)':<30} [{res['source'] or '-'}] "
                  f"EP {res['ep_id'] or '-'} {res['ep_name'] or ''} | {res['note']}")
            if not res["name"]:
                unresolved.append(q)
                continue
            if args.apply:
                n = db.execute(text(
                    "UPDATE social_accounts SET entity_name=:n, updated_at=now() "
                    "WHERE entity_name=:q AND entity_name ~ '^Q[0-9]+$'"),
                    {"n": res["name"], "q": q}).rowcount
                print(f"               updated {n} row(s)")
        if args.apply:
            db.commit()

        ids = [r["id"] for r in before]
        if ids:
            after = db.execute(text(
                "SELECT id, entity_name, entity_key, platform FROM social_accounts "
                "WHERE id = ANY(:ids) ORDER BY entity_key, platform"), {"ids": ids}).mappings().all()
            print(f"\nAFTER ({'APPLIED' if args.apply else 'DRY-RUN, unchanged'}):")
            for r in after:
                print(f"  {r['id']:>6}  {r['entity_key']:<12} {r['platform']:<10} {r['entity_name']}")
        left = db.execute(text(
            "SELECT count(*) FROM social_accounts WHERE entity_name ~ '^Q[0-9]+$'")).scalar()
        print(f"\nremaining bare-QID names: {left}")
        if unresolved:
            print(f"[ERROR] unresolved, left untouched: {', '.join(unresolved)}")
    finally:
        db.close()
    return 1 if unresolved else 0


if __name__ == "__main__":
    raise SystemExit(main())

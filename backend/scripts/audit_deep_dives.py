#!/usr/bin/env python3.12
"""Which deep-dives are behind their own legislative file, and on WHICH fact.

WHY (22 September 2026)
----------------------
Thirteen deep-dives, 49 pages. Only EU Inc. and the EU-Andorra page were current;
the rest had stopped somewhere between May and July. Nothing was broken, there
was simply no trigger: deep-dives are in no cron, no sync registry and no
`/morning` phase, and they are not in the canonical feature tree, so the
feature-by-feature walk in `/news` never reaches them. On the day the Union
Customs Code became law and the EU Kids Act was published, `/news` produced
fourteen proposals and not one touched a deep-dive.

The worst case found by hand: the Cloud and AI Development Act page said the
parliamentary stage was pending while OEIL had shown two co-rapporteurs since
24 June 2026, three months earlier.

WHAT THIS DOES
--------------
Joins each deep-dive to its procedure and asks two sources, which are the two
that actually move:

  * OEIL, via `legislative_carriages` (rapporteur, committee, opinion
    committees, status), and
  * eMeeting, via `ep_emeeting_documents` (draft reports, amendments, voting
    lists, committee agenda items).

Then it checks whether each fact appears in the page text, FOR EVERY LANGUAGE.
That last part is not decoration: the first hand-update of CADA and the Chips Act
touched `index.html` only and left the Catalan, Spanish, French, Italian and
Dutch pages saying the opposite, 2 pages of 12.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not rewrite pages. It reports which page is missing which fact, so the
edit is a human decision and the diff is reviewable. A detector that also
writes would have shipped my own two layout bugs unseen.

Matching notes, both learned the hard way:
  * Rapporteurs are matched on SURNAME only. The carriage stores "SCHENK Oliver"
    and the pages write "Oliver Schenk"; a full-string match finds neither.
  * Text is accent-folded before comparison, because "ABADIA" and "ABADÍA" and
    "Sinkevicius" and "Sinkevičius" are the same person and a plain substring
    test says they are not.

USAGE
    python3.12 backend/scripts/audit_deep_dives.py            # report, exit 1 if behind
    python3.12 backend/scripts/audit_deep_dives.py --json
    python3.12 backend/scripts/audit_deep_dives.py --slug /chips-act-2
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import unicodedata
from typing import Dict, List, Optional

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "backend"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(_REPO_ROOT / ".env")

import os  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from services.comparator.deep_dives import DEEP_DIVES  # noqa: E402

PUBLIC = _REPO_ROOT / "frontend" / "public"
_META_RE = re.compile(r'<meta\s+name="brubru:last-reviewed"\s+content="(\d{4}-\d{2}-\d{2})"')
_TAG_RE = re.compile(r"<[^>]+>")


def fold(s: str) -> str:
    """Lowercase and strip accents, so ABADÍA == abadia and Sinkevičius == sinkevicius."""
    if not s:
        return ""
    n = unicodedata.normalize("NFKD", s)
    return "".join(c for c in n if not unicodedata.combining(c)).lower()


def page_text(p: pathlib.Path) -> str:
    raw = p.read_text(encoding="utf-8", errors="replace")
    return fold(_TAG_RE.sub(" ", raw))


def pages_for(base_path: str) -> List[pathlib.Path]:
    d = PUBLIC / base_path.lstrip("/")
    return sorted(d.glob("*.html")) if d.is_dir() else []


def surname(rapporteur: Optional[str]) -> Optional[str]:
    """'SCHENK Oliver' -> 'schenk'. OEIL prints SURNAME first, in caps."""
    if not rapporteur:
        return None
    parts = [w for w in rapporteur.split() if w]
    caps = [w for w in parts if w.isupper() and len(w) > 2]
    return fold(caps[0] if caps else parts[0])


def fetch_facts(engine, refs: List[str]) -> Dict[str, dict]:
    """Everything OEIL and eMeeting currently say about these procedures."""
    out: Dict[str, dict] = {}
    with engine.connect() as c:
        for row in c.execute(text("""
            SELECT oeil_procedure_ref, lead_committee, rapporteur_name,
                   rapporteur_appointed, opinion_committees, current_status::text AS st,
                   last_updated
              FROM legislative_carriages
             WHERE oeil_procedure_ref = ANY(:refs)
        """), {"refs": refs}).mappings():
            out[row["oeil_procedure_ref"]] = {
                "lead_committee": row["lead_committee"],
                "rapporteur": row["rapporteur_name"],
                "rapporteur_appointed": str(row["rapporteur_appointed"] or "") or None,
                "opinion_committees": list(row["opinion_committees"] or []),
                "status": row["st"],
                "carriage_updated": str(row["last_updated"] or "")[:10] or None,
                "emeeting": [],
            }
        # eMeeting is the second source and the one that moves first once a
        # committee starts work: a draft report or a voting list appears there
        # days before anything else says so.
        for row in c.execute(text("""
            SELECT procedure_ref, doc_kind, committee_code,
                   coalesce(reference,'') AS ref, max(meeting_date) AS d
              FROM ep_emeeting_documents
             WHERE procedure_ref = ANY(:refs)
               AND doc_kind IN ('draft_report','amendment','compromise_amendments',
                                'draft_opinion','opinion','voting_list')
             GROUP BY 1,2,3,4 ORDER BY 5 DESC
        """), {"refs": refs}).mappings():
            if row["procedure_ref"] in out:
                out[row["procedure_ref"]]["emeeting"].append(
                    {"kind": row["doc_kind"], "committee": row["committee_code"],
                     "ref": row["ref"], "date": str(row["d"])})
    return out


def audit_one(dd: dict, facts: Optional[dict]) -> dict:
    base = dd["base_path"]
    pages = pages_for(base)
    res = {"base_path": base, "title": dd.get("short_title") or dd.get("title"),
           "procedure_ref": dd.get("procedure_ref"), "pages": len(pages),
           "reviewed": None, "missing": {}, "notes": []}
    if not pages:
        res["notes"].append("NO PAGES FOUND on disk")
        return res

    raw0 = pages[0].read_text(encoding="utf-8", errors="replace")
    m = _META_RE.search(raw0)
    res["reviewed"] = m.group(1) if m else None

    if facts is None:
        res["notes"].append("no carriage for this procedure ref, nothing to compare against")
        return res

    # Build the checks. Each is (label, needle) where needle is already folded.
    checks: List[tuple] = []
    sn = surname(facts["rapporteur"])
    if sn:
        checks.append((f"rapporteur {facts['rapporteur']}", sn))
    if facts["lead_committee"]:
        checks.append((f"committee {facts['lead_committee']}", fold(facts["lead_committee"])))

    # THE EU INC. STANDARD (set by Victor, 22 September 2026).
    #
    # A deep dive is not current because it names a rapporteur. The reference
    # page, /eu-inc, carries the committee debates, an analysis of the
    # rapporteur's draft report and an analysis of the MEPs' amendments, and it
    # cites each by its PE reference: "rapporteur Rene Repasi tabled the lead
    # JURI draft report (PE790.143, 246 amendments)".
    #
    # eMeeting stores those PE references, so coverage is checkable rather than
    # a matter of opinion: if a draft report exists for this procedure and its
    # PE number appears nowhere on the page, the analysis is missing.
    pe_refs = {e["ref"]: e for e in facts["emeeting"]
               if e.get("ref", "").upper().startswith("PE")}
    res["owed"] = []
    if pe_refs:
        first_txt = page_text(pages[0])
        for ref, e in sorted(pe_refs.items(), key=lambda kv: kv[1]["date"], reverse=True):
            if fold(ref) not in first_txt:
                res["owed"].append(
                    f"{e['kind'].replace('_',' ')} {e['committee']} {ref} ({e['date']})")

    if not checks:
        res["notes"].append("carriage holds no rapporteur or committee yet, nothing to assert")
        return res

    for p in pages:
        txt = page_text(p)
        miss = [label for label, needle in checks if needle not in txt]
        if miss:
            res["missing"][p.name] = miss

    # eMeeting is checked by DATE, not by wording.
    #
    # The first version asked whether the page contained the phrase "draft
    # report" or "voting list". That is not a currency test: it fired on
    # /eu-inc, which is one of the two pages that ARE up to date, because the
    # English page happens to use the words and the translations do not. The
    # question worth asking is whether a committee document appeared AFTER the
    # page was last reviewed.
    newer = [e for e in facts["emeeting"]
             if res["reviewed"] and e["date"] > res["reviewed"]]
    if newer:
        newest = max(newer, key=lambda e: e["date"])
        res["emeeting_newer"] = newer
        res["notes"].append(
            f"eMeeting has {len(newer)} committee document(s) dated after the page was "
            f"reviewed; newest {newest['kind']} {newest['committee']} {newest['date']}")

    if facts["carriage_updated"] and res["reviewed"] \
       and facts["carriage_updated"] > res["reviewed"]:
        res["notes"].append(
            f"carriage row changed {facts['carriage_updated']} (may be our own re-parse, "
            f"not necessarily a legislative step)")
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--slug", help="only this base_path, e.g. /chips-act-2")
    a = ap.parse_args()

    dds = [d for d in DEEP_DIVES if not a.slug or d["base_path"] == a.slug]
    refs = [d["procedure_ref"] for d in dds if d.get("procedure_ref")]
    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    facts = fetch_facts(engine, refs)

    results = [audit_one(d, facts.get(d.get("procedure_ref"))) for d in dds]

    if a.json:
        print(json.dumps({"results": results, "facts": facts}, indent=1, default=str))
        return 1 if any(r["missing"] or r.get("emeeting_newer") or r.get("owed") for r in results) else 0

    behind = [r for r in results if r["missing"] or r.get("emeeting_newer") or r.get("owed")]
    print(f"DEEP-DIVE AUDIT  {len(results)} deep-dive(s), "
          f"{sum(r['pages'] for r in results)} page(s)")
    print("=" * 78)
    for r in sorted(results, key=lambda x: (not x["missing"], x["base_path"])):
        head = f"{r['base_path']:<34} {str(r['procedure_ref'] or '-'):<18} reviewed {r['reviewed'] or '-'}"
        if not r["missing"] and not r.get("emeeting_newer") and not r.get("owed"):
            print(f"[ok  ] {head}")
            continue
        flag = 'BEHIND' if (r['missing'] or r.get('emeeting_newer') or r.get('owed')) else 'note '
        print(f'[{flag:<6}] {head}')
        for note in r["notes"]:
            print(f"         note: {note}")
        # Report the SHAPE of the gap: the same fact missing from every language
        # page is one edit in six files, not six different problems.
        by_fact: Dict[str, List[str]] = {}
        for page, facts_missing in r["missing"].items():
            for f in facts_missing:
                by_fact.setdefault(f, []).append(page)
        for f, pgs in sorted(by_fact.items()):
            where = "ALL pages" if len(pgs) == r["pages"] else ", ".join(sorted(pgs))
            print(f"         missing: {f}   [{where}]")
        for owed in r.get("owed", []):
            print(f"         NOT ANALYSED: {owed}")
    print()
    print(f"{len(behind)} of {len(results)} deep-dive(s) are behind their own file.")
    return 1 if behind else 0


if __name__ == "__main__":
    sys.exit(main())

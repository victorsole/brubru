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
Joins each deep-dive to its procedure and asks three sources:

  * OEIL, via `legislative_carriages` (rapporteur, committee, opinion
    committees, status),
  * eMeeting, via `ep_emeeting_documents` (draft reports, amendments, voting
    lists, committee agenda items), and
  * OEIL's own Documentation gateway, live, with --oeil.

The third was added on 22 September 2026 because the first two missed a draft
report. This file said eMeeting "moves first once a committee starts work".
That is false for the tabling of a report: the Industrial Accelerator Act's
joint draft report PE792.067 was dated 9 September and entered the gateway on
11 September, while `ep_emeeting_documents` held nothing for that procedure
newer than 6 July, because a document only reaches eMeeting when it goes on a
committee agenda. All six pages were still asserting that no draft report had
been tabled, and the detector reported the file as current. Victor found it by
reading the gateway.

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
import html
import json
import pathlib
import re
from datetime import date
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


_MONTHS = {
    # Brubru's six languages. A page writes "2 September 2026" or "2 de setembre
    # de 2026"; eMeeting stores "2026-09-02". Comparing the ISO string against
    # page text reports every correctly-updated page as missing, which is what it
    # did to the Industrial Accelerator Act minutes after that page was updated.
    9: ["september", "setembre", "septiembre", "septembre", "settembre"],
    1: ["january", "gener", "enero", "janvier", "gennaio", "januari"],
    2: ["february", "febrer", "febrero", "fevrier", "febbraio", "februari"],
    3: ["march", "marc", "marzo", "mars", "maart"],
    4: ["april", "abril", "avril", "aprile"],
    5: ["may", "maig", "mayo", "mai", "maggio", "mei"],
    6: ["june", "juny", "junio", "juin", "giugno", "juni"],
    7: ["july", "juliol", "julio", "juillet", "luglio", "juli"],
    8: ["august", "agost", "agosto", "aout", "augustus"],
    10: ["october", "octubre", "ottobre", "octobre", "oktober"],
    11: ["november", "novembre", "noviembre", "novembre"],
    12: ["december", "desembre", "diciembre", "decembre", "dicembre"],
}


def date_is_on_page(iso: str, page: str) -> bool:
    """True if `page` mentions this date in ISO or in any of our six languages."""
    if not iso:
        return False
    if fold(iso) in page:
        return True
    try:
        y, mth, day = iso.split("-")
        d = str(int(day))
    except (ValueError, AttributeError):
        return False
    for name in _MONTHS.get(int(mth), []):
        # "2 september 2026" with anything short in between ("de", "di", ...).
        if re.search(rf"\b{d}\b[^0-9]{{0,12}}{name}[^0-9]{{0,12}}{y}", page):
            return True
    return False


def page_text(p: pathlib.Path) -> str:
    """Page text, tags stripped, entities decoded, accents folded.

    Decoding entities is not cosmetic. The deep-dive pages write non-ASCII names
    as HTML entities, so the pharma-laws page carries the rapporteur as
    `W&ouml;lken`. `fold()` normalises Unicode, which does nothing to an entity,
    so the detector looked for "wolken" in text that read "w&ouml;lken" and
    reported the rapporteur as missing from all pages of a file that named him
    correctly. Found 22 September 2026; the same shape as the accent bug, one
    layer further out.
    """
    raw = p.read_text(encoding="utf-8", errors="replace")
    return fold(html.unescape(_TAG_RE.sub(" ", raw)))


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


_GATEWAY_ROW = re.compile(
    r"(Committee draft report|Committee opinion|Amendments tabled in committee|"
    r"Committee report tabled for plenary[^A-Z]*|Committee recommendation[^A-Z]*|"
    r"Committee interim report[^A-Z]*)\s+([A-Z]{4}\s+)?(PE\d{3}\.\d{3}|A\d{1,2}-\d+/\d{4})"
    r"\s+(\d{2}/\d{2}/\d{4})")


def fetch_oeil_gateway(refs: List[str]) -> Dict[str, List[dict]]:
    """Parliament documents listed in OEIL's own Documentation gateway.

    Live fetch, one procedure page each, so it is opt-in: the pages are behind a
    JS challenge and take seconds apiece. It is the only source that sees a
    report the moment it is tabled, before any committee has put it on an
    agenda.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "wbf", str(_REPO_ROOT / "backend" / "services" / "scrapers" / "waf_browser_fetcher.py"))
    wbf = importlib.util.module_from_spec(spec)
    sys.modules["wbf"] = wbf
    spec.loader.exec_module(wbf)

    out: Dict[str, List[dict]] = {}
    for ref in refs:
        url = ("https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file"
               f"?reference={ref}")
        try:
            res = wbf.fetch_one(url, expand_accordions=True, strip_chrome=True)
        except Exception as exc:                                   # noqa: BLE001
            print(f"[WARN] OEIL fetch failed for {ref}: {exc}")
            continue
        flat = re.sub(r"\s+", " ", res.text or "")
        i = flat.find("Documentation gateway European Parliament")
        if i < 0:
            continue
        # stop before the Commission block, or its COM documents come through
        j = flat.find("European Commission Document type", i)
        block = flat[i:j if j > i else i + 3000]
        rows = []
        for m in _GATEWAY_ROW.finditer(block):
            rows.append({"kind": m.group(1).strip(),
                         "committee": (m.group(2) or "").strip() or None,
                         "ref": m.group(3), "date": m.group(4)})
        if rows:
            out[ref] = rows
    return out


def fetch_by_title(engine, dds: List[dict]) -> Dict[str, List[dict]]:
    """Committee documents found by TITLE, for rows with no procedure_ref.

    49% of ep_emeeting_documents rows carry no procedure_ref (8,135 of 16,603).
    For the kinds that matter the coverage is good -- draft reports 97.6%,
    amendments 96%, voting lists 91% -- but the remainder is not nothing, and
    the untagged rows include committee EVENTS that never carry a ref at all.

    The Industrial Accelerator Act is the case that proved it: a joint IMCO and
    INTA public-hearing programme on 2 September 2026 ("Final_programme_PH_IAA")
    has no procedure_ref, so a ref-only query reported no committee activity on
    a file that had just been through a public hearing.
    """
    out: Dict[str, List[dict]] = {}
    with engine.connect() as c:
        for d in dds:
            needle = (d.get("short_title") or d.get("title") or "").strip()
            if len(needle) < 6:
                continue
            rows = c.execute(text("""
                SELECT doc_kind, committee_code, coalesce(reference,'') AS ref,
                       meeting_date, left(coalesce(item_title, title), 90) AS t
                  FROM ep_emeeting_documents
                 WHERE procedure_ref IS NULL
                   AND coalesce(item_title,'') || coalesce(title,'') ILIKE :pat
                 ORDER BY meeting_date DESC LIMIT 25
            """), {"pat": f"%{needle}%"}).mappings().all()
            if rows:
                out[d["base_path"]] = [
                    {"kind": r["doc_kind"], "committee": r["committee_code"],
                     "ref": r["ref"], "date": str(r["meeting_date"]), "title": r["t"]}
                    for r in rows]
    return out


def audit_one(dd: dict, facts: Optional[dict], untagged: Optional[List[dict]] = None,
              gateway: Optional[List[dict]] = None) -> dict:
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

    # OEIL's Documentation gateway. This is the source that sees a tabled
    # report first; eMeeting only sees it once it reaches a committee agenda.
    if gateway:
        first = page_text(pages[0])
        unseen = [g for g in gateway if fold(g["ref"]) not in first]
        if unseen:
            res["gateway_unseen"] = unseen

    # Untagged committee activity found by title: report it whatever the
    # carriage says, because these rows never carry a procedure reference.
    _first = page_text(pages[0])
    for u in (untagged or []):
        covered = date_is_on_page(u["date"], _first) or (
            bool(u["ref"]) and fold(u["ref"]) in _first)
        if not covered:
            res.setdefault("untagged", []).append(
                f"{u['kind'].replace('_',' ')} {u['committee']} {u['date']} \"{u['title'][:52]}\"")

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
    #
    # Only meetings that have HAPPENED count (23 Sep 2026). `date` is the MEETING
    # date, so a document filed for a meeting next week made a page reviewed
    # today look stale, and no review could ever clear it until the meeting
    # passed. A document for a future meeting is still caught when the page does
    # not cite it: that is the NOT ANALYSED check below, which reads references.
    today = date.today().isoformat()
    newer = [e for e in facts["emeeting"]
             if res["reviewed"] and res["reviewed"] < e["date"] <= today]
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
    ap.add_argument("--no-oeil", action="store_true",
                    help="skip the live OEIL Documentation gateway check (faster, but "
                         "eMeeting alone misses a report until it reaches an agenda)")
    a = ap.parse_args()

    dds = [d for d in DEEP_DIVES if not a.slug or d["base_path"] == a.slug]
    refs = [d["procedure_ref"] for d in dds if d.get("procedure_ref")]
    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    facts = fetch_facts(engine, refs)

    untagged = fetch_by_title(engine, dds)
    # Both sources, every run. eMeeting sees committee agendas; the gateway sees
    # a report the day it is tabled. Neither alone is enough.
    gateway = {} if a.no_oeil else fetch_oeil_gateway(refs)
    results = [audit_one(d, facts.get(d.get("procedure_ref")),
                         untagged.get(d["base_path"], []),
                         gateway.get(d.get("procedure_ref"), [])) for d in dds]

    if a.json:
        print(json.dumps({"results": results, "facts": facts}, indent=1, default=str))
        return 1 if any(r["missing"] or r.get("emeeting_newer") or r.get("owed")
                        or r.get("gateway_unseen") for r in results) else 0

    behind = [r for r in results if any((r["missing"], r.get("emeeting_newer"), r.get("owed"),
                                        r.get("untagged"), r.get("gateway_unseen")))]
    print(f"DEEP-DIVE AUDIT  {len(results)} deep-dive(s), "
          f"{sum(r['pages'] for r in results)} page(s)")
    print("=" * 78)
    for r in sorted(results, key=lambda x: (not x["missing"], x["base_path"])):
        head = f"{r['base_path']:<34} {str(r['procedure_ref'] or '-'):<18} reviewed {r['reviewed'] or '-'}"
        if not any((r["missing"], r.get("emeeting_newer"), r.get("owed"), r.get("untagged"),
                    r.get("gateway_unseen"))):
            print(f"[ok  ] {head}")
            continue
        flag = 'BEHIND'
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
        for u in r.get("untagged", []):
            print(f"         NOT ANALYSED (no procedure ref, found by title): {u}")
        for g in r.get("gateway_unseen", []):
            cm = f" {g['committee']}" if g.get("committee") else ""
            print(f"         NOT ON THE PAGE, from OEIL's gateway: "
                  f"{g['kind']}{cm} {g['ref']} ({g['date']})")
    print()
    print(f"{len(behind)} of {len(results)} deep-dive(s) are behind their own file.")
    return 1 if behind else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3.12
"""Read the committee vote results printed in a Parliament report (A10-NNNN/YYYY).

Why (8 Oct 2026). The Legislative Observatory logs THAT a committee vote took place but never its
result, and the committee MINUTES that do carry results are published about five weeks later
(ENVI's June meetings reached an agenda on 5 October). The first place a result appears is the
final pages of the committee REPORT tabled for plenary: "INFORMATION ON ADOPTION BY THE COMMITTEE
RESPONSIBLE ... Date adopted ... Result of final vote". This reads those blocks, for the lead
committee and for any committee that gave an opinion.

Usage (from backend/):
    python3.12 scripts/read_committee_vote_result.py A10-0259/2026
    python3.12 scripts/read_committee_vote_result.py --procedure "2026/0074(COD)"   # lists reports tabled
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

logging.disable(logging.CRITICAL)

DASH = r"[–−-]"
# Two layouts exist: labels first ("+: -: 0: 38 1 4") and label-value pairs ("+ : 25 - : 6 0 : 0").
_LABELS_FIRST = re.compile(rf"\+\s*:\s*{DASH}\s*:\s*0\s*:\s*(\d+)\s+(\d+)\s+(\d+)")
_PAIRS = re.compile(rf"\+\s*:\s*(\d+)\s*{DASH}\s*:\s*(\d+)\s*0\s*:\s*(\d+)")


def parse_vote_blocks(text: str) -> list[dict]:
    """Every committee adoption block in a report's text: who, when, and the +/-/0 result.

    A block whose numbers cannot be read is returned with `result` None, never guessed.
    """
    flat = re.sub(r"\s+", " ", text)
    out = []
    for m in re.finditer(
        r"(INFORMATION ON ADOPTION (?:BY THE COMMITTEE RESPONSIBLE|IN COMMITTEE ASKED FOR OPINION|BY THE COMMITTEE ASKED FOR OPINION)).{0,2500}?"
        r"Date adopted\s+(\d{1,2}\.\d{1,2}\.\d{4})\s+Result of final vote\s*(.{0,70})",
        flat,
    ):
        label, date_adopted, tail = m.group(1), m.group(2), m.group(3)
        res = None
        m1 = _LABELS_FIRST.search(tail)
        m2 = _PAIRS.search(tail)
        if m1:
            res = tuple(int(x) for x in m1.groups())
        elif m2:
            res = tuple(int(x) for x in m2.groups())
        out.append({
            "committee_role": "lead (responsible)" if "RESPONSIBLE" in label else "opinion",
            "date_adopted": date_adopted,
            "result": res,  # (in favour, against, abstentions) or None
        })
    return out


def _fetch_text(url: str) -> str:
    from services.scrapers.waf_browser_fetcher import fetch_one
    html = fetch_one(url, expand_accordions=False, strip_chrome=True).html or ""
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t).replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", t)


def report_url(ref: str) -> str:
    m = re.fullmatch(r"A10-(\d{4})/(\d{4})", ref.strip())
    if not m:
        raise SystemExit(f"not a report reference: {ref!r} (expected A10-NNNN/YYYY)")
    return f"https://www.europarl.europa.eu/doceo/document/A-10-{m.group(2)}-{m.group(1)}_EN.html"


def reports_for_procedure(ref: str) -> list[str]:
    from services.scrapers.waf_browser_fetcher import fetch_one
    html = fetch_one(f"https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference={ref}",
                     expand_accordions=True, strip_chrome=True).html or ""
    return sorted(set(re.findall(r"A10-\d{4}/\d{4}", html)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("report", nargs="?", help="A10-NNNN/YYYY")
    ap.add_argument("--procedure", help="list the reports tabled for this procedure reference")
    a = ap.parse_args()
    if a.procedure:
        refs = reports_for_procedure(a.procedure)
        print(f"{a.procedure}: reports tabled: {refs or 'none yet'}")
        return 0 if refs else 2
    if not a.report:
        ap.error("give a report reference or --procedure")
    text = _fetch_text(report_url(a.report))
    title = re.search(r"(REPORT|SECOND REPORT|RECOMMENDATION FOR SECOND READING)[^|]{0,160}", text)
    print(a.report, "|", title.group(0)[:150] if title else "(title not found)")
    blocks = parse_vote_blocks(text)
    if not blocks:
        print("  no committee adoption block found: the report may not carry one yet")
        return 2
    for b in blocks:
        r = b["result"]
        shown = f"{r[0]} in favour, {r[1]} against, {r[2]} abstentions" if r else "UNREADABLE (read the report)"
        print(f"  {b['committee_role']:<20} adopted {b['date_adopted']}: {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

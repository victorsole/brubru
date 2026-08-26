#!/usr/bin/env python3.12
"""Recent EU Court case-law (judgments + AG opinions) from Cellar sector 6.

Why: ECJ judgments create/develop EU legal doctrine and are complementary to
legislation; AG opinions are the "trailer" to the judgment (usually aligned,
sometimes divergent). /news uses this to surface doctrine-shaping rulings and
flag which need a KB guide / deep-dive explanation.

Source: `cellar_news_helper.py --oj-today --sectors 6` (Cellar SPARQL, no WAF,
authoritative). Note: brand-new judgments can carry a null/partial title for
1-2 working days (Publications Office metadata lag) — expected, not a bug.

Usage:
    python3.12 scripts/ecj_caselaw_helper.py --days 3
    python3.12 scripts/ecj_caselaw_helper.py --days 7 --json
"""
import argparse, json, re, subprocess, sys, os, urllib.request
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PR_LIST_URL = "https://curia.europa.eu/jcms/upload/docs/application/pdf/../../../../site/jcms/d2_5158/en/press-releases"
PR_LIST_URL = "https://curia.europa.eu/site/jcms/d2_5158/en/press-releases"
PR_BASE = "https://curia.europa.eu/site/"


def fetch_press_releases(days):
    """CURIA press releases = the Court's OWN curated list of notable cases WITH
    plain-language summaries. A case with a PR is, by definition, one the Court
    considers important AND for which a ready-made summary exists (use it to seed
    a KB guide / deep-dive). Newest first."""
    req = urllib.request.Request(PR_LIST_URL, headers={"User-Agent": "Mozilla/5.0 Chrome/151"})
    try:
        html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    except Exception as e:
        return [], f"press-release fetch failed: {e}"
    items = re.findall(
        r'No\.\s*(\d{1,3}/\d{4}).*?datetime="(\d{2}/\d{2}/\d{4})".*?'
        r'href="(upload/[^"]+?/(cp\d{6})en\.pdf)"[^>]*>\s*<h3>(.*?)</h3>',
        html, re.S)
    cutoff = date.today().toordinal() - days
    out = []
    for no, dt, href, cp, title in items:
        try:
            d = datetime.strptime(dt, "%d/%m/%Y").date()
        except Exception:
            continue
        if d.toordinal() < cutoff:
            continue
        title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", title)).strip()
        cases = re.findall(r"C-\d+/\d+|T-\d+/\d+", title)
        out.append(dict(no=no, date=d.isoformat(), title=title[:180],
                        cases=cases, pdf=PR_BASE + href, cp=cp))
    return out, None

# CELEX sector-6 descriptor -> (kind, court)
DESC = {
    "CJ": ("judgment", "Court of Justice"),
    "CC": ("opinion", "Court of Justice"),      # AG Opinion (conclusions)
    "CO": ("order", "Court of Justice"),
    "CV": ("opinion_of_court", "Court of Justice"),  # avis 1/... (Art 218(11))
    "CD": ("decision", "Court of Justice"),
    "CB": ("order", "Court of Justice"),
    "CP": ("view", "Court of Justice"),         # AG view (prise de position)
    "TJ": ("judgment", "General Court"),
    "TO": ("order", "General Court"),
    "TC": ("order", "General Court"),
    "FJ": ("judgment", "Civil Service Tribunal"),
}

# Doctrine / low-signal keyword hints (applied to the subject-matter text)
LOW_HINTS = re.compile(r"time limit|out of time|inadmissib|staff case|"
                       r"appeal.*dismiss|manifestly|costs|interim meas. dismiss", re.I)
DOCTRINE_HINTS = re.compile(r"Charter|fundamental rights|preliminary ruling|"
                            r"Article \d+ TFEU|Article \d+ TEU|principle of|primacy|"
                            r"direct effect|rule of law|first time", re.I)


def parse_title(celex, title):
    """Split a Cellar case-law title into chamber / parties / subject / case."""
    t = (title or "").strip()
    # CELEX: 6 YYYY XX NNNN  ->  descriptor XX at positions 5-6
    m = re.match(r"6(\d{4})([A-Z]{2})(\d{4})", celex)
    year = m.group(1) if m else ""
    desc = m.group(2) if m else ""
    kind, court = DESC.get(desc, ("other", "EU Courts"))
    chamber = ""
    cm = re.search(r"\((Grand Chamber|Full Court|First|Second|Third|Fourth|Fifth|"
                   r"Sixth|Seventh|Eighth|Ninth|Tenth) ?(Chamber)?\)", t)
    if cm:
        chamber = cm.group(0).strip("()")
    case = ""
    csm = re.search(r"Case (C-\d+/\d+ ?P?|T-\d+/\d+ ?P?|C-\d+/\d+ PPU)", t)
    if csm:
        case = csm.group(1).strip()
    # subject-matter: Cellar joins segments with '#'; middle segments carry parties+subject
    segs = [s.strip() for s in t.split("#") if s.strip()]
    subject = ""
    parties = ""
    if len(segs) >= 3:
        parties = segs[1]
        subject = segs[2]
    elif len(segs) == 2:
        subject = segs[1]
    ag = ""
    agm = re.search(r"Advocate General ([A-Z][\wÀ-ÿ’'-]+(?: [A-Z][\wÀ-ÿ’'-]+){0,2})", t)
    if agm:
        ag = agm.group(1)
    return dict(celex=celex, year=year, desc=desc, kind=kind, court=court,
                chamber=chamber, case=case, parties=parties, subject=subject, ag=ag)


def rank(item):
    """HIGH / MEDIUM / LOW importance heuristic (final call is human judgment)."""
    if item["kind"] == "opinion":
        return "OPINION"           # trailers: bucketed separately
    if item["kind"] in ("order", "decision", "view"):
        return "LOW"
    subj = item["subject"] or ""
    if not subj and not item["chamber"]:
        return "PENDING"           # metadata not yet landed (1-2 working days)
    grand = item["chamber"] in ("Grand Chamber", "Full Court")
    doctrine = bool(DOCTRINE_HINTS.search(subj))
    low = bool(LOW_HINTS.search(subj))
    if grand:
        return "HIGH"              # Grand Chamber judgment = doctrine weight
    if item["court"] == "Court of Justice" and doctrine and not low:
        return "MEDIUM"
    if low:
        return "LOW"
    return "MEDIUM" if item["court"] == "Court of Justice" else "LOW"


def fetch(days, limit):
    out = subprocess.run(
        [sys.executable, os.path.join(HERE, "cellar_news_helper.py"),
         "--oj-today", "--days", str(days), "--sectors", "6", "--limit", str(limit)],
        capture_output=True, text=True)
    # helper prints logging + JSON; grab the JSON object
    txt = out.stdout
    start = txt.find("{")
    data = json.loads(txt[start:]) if start >= 0 else {"acts": []}
    # dedup on the BASE celex (strip _RES/_INF and other manifestation suffixes),
    # keeping the variant with the richest (longest) title.
    best = {}
    for a in data.get("acts", []):
        cx = a.get("celex")
        if not cx:
            continue
        base = re.sub(r"^(6\d{4}[A-Z]{2}\d{4}).*", r"\1", cx)
        if not re.match(r"6\d{4}[A-Z]{2}\d{4}$", base):
            continue
        title = a.get("title") or ""
        if base not in best or len(title) > len(best[base].get("title") or ""):
            best[base] = {"celex": base, "title": title, "date": a.get("date")}
    acts = []
    for base, a in best.items():
        it = parse_title(base, a["title"]); it["date"] = a["date"]
        acts.append(it)
    return acts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    acts = fetch(a.days, a.limit)
    prs, pr_err = fetch_press_releases(a.days)
    pr_cases = {c for p in prs for c in p["cases"]}
    for it in acts:
        it["importance"] = rank(it)
        it["has_pr"] = it["case"] in pr_cases
    if a.json:
        print(json.dumps({"press_releases": prs, "case_law": acts}, ensure_ascii=False, indent=2)); return
    buckets = {"HIGH": [], "MEDIUM": [], "LOW": [], "OPINION": [], "PENDING": []}
    for it in acts:
        buckets[it["importance"]].append(it)
    print(f"EU Court case-law, last {a.days} day(s): {len(acts)} items "
          f"(judgments HIGH {len(buckets['HIGH'])} / MED {len(buckets['MEDIUM'])} / "
          f"LOW {len(buckets['LOW'])} · opinions {len(buckets['OPINION'])} · "
          f"pending-metadata {len(buckets['PENDING'])})\n")

    # CURIA press releases first: the Court's curated notable cases WITH summaries.
    if pr_err:
        print(f"[warn] {pr_err}\n")
    elif prs:
        print(f"=== CURIA PRESS RELEASES ({len(prs)}) — Court-curated, plain-language "
              f"summary in the PDF (seed a KB guide / deep-dive from these) ===")
        for p in prs:
            cs = " ".join(p["cases"]) or "(no case ref in title)"
            print(f"  {p['date']} No {p['no']:<9} {cs:<22} {p['title'][:96]}")
            print(f"       {p['pdf']}")
        print()

    def line(it):
        tag = f"[{it['court'].split()[0]}·{it['chamber'] or it['kind']}]"
        cse = it["case"] or it["celex"]
        pr = " [PR]" if it.get("has_pr") else ""
        subj = (it["subject"] or it["parties"] or "")[:120]
        return f"  {it['date']} {cse:<14} {tag:<22}{pr} {subj}"
    for b in ("HIGH", "MEDIUM", "LOW"):
        if buckets[b]:
            print(f"=== JUDGMENTS — {b} ===")
            for it in buckets[b]:
                print(line(it))
            print()
    if buckets["OPINION"]:
        print("=== AG OPINIONS (the 'trailer' to a future judgment) ===")
        for it in buckets["OPINION"]:
            ag = f"AG {it['ag']}" if it["ag"] else "AG opinion"
            print(f"  {it['date']} {it['case'] or it['celex']:<14} {ag}")
        print()
    if buckets["PENDING"]:
        cels = ", ".join(it["celex"] for it in buckets["PENDING"][:12])
        print(f"=== PENDING METADATA ({len(buckets['PENDING'])}) — title not yet in Cellar "
              f"(1-2 working days; re-check next run) ===\n  {cels}")


if __name__ == "__main__":
    main()

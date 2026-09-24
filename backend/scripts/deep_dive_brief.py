#!/usr/bin/env python3.12
"""Fetch and parse every committee document behind a procedure, and brief on it.

WHY (22 September 2026)
----------------------
Six deep-dives were brought current in one day, and the same three steps were
done by hand six times: read OEIL's Documentation gateway, pull the documents
through a browser session that has cleared the WAF challenge, then count the
same six things in every one of them. About 11 MB of PDFs, re-fetched from
scratch each time because nothing stored them.

`audit_deep_dives.py` answers "which page is behind". This answers the next
question, "and what does the file actually say", far enough that the remaining
work is reading rather than plumbing.

WHAT IT REFUSES TO DO
---------------------
It does not write pages and it does not interpret. The numbers it produces are
the ones that were worth having every time (who tabled, what they fought over,
how the vote went), but what they MEAN is the job: that Sokol's binding
redistribution became a voluntary mechanism, that Breyer voted for the report he
filed 389 amendments against, that Article 81's six-year baseline was deleted
rather than trimmed. None of that is derivable from a count.

TWO RULES BUILT IN, BOTH LEARNED THE HARD WAY
---------------------------------------------
* **The last amendment number is not the count.** Parliament numbers amendments
  continuously across the draft report and every amendment document, so max(id)
  overstates the member count by the rapporteur's offset. The late-payments page
  said "405 amendments" when members tabled 380, numbered 26 to 405. This always
  reports distinct count, range AND gap count, so the arithmetic is checkable.
* **Never guess a doceo URL.** The gateway carries the real links. `curl` gets a
  202 WAF challenge, so documents come through a browser context that has
  cleared it.

USAGE
    python3.12 backend/scripts/deep_dive_brief.py --ref "2025/0102(COD)" --fetch
    python3.12 backend/scripts/deep_dive_brief.py --ref "2025/0406(COD)" --json
    python3.12 backend/scripts/deep_dive_brief.py --all --fetch      # every deep-dive
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
from collections import Counter
from typing import Dict, List, Optional

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "backend"))

CACHE = _REPO_ROOT / "backend" / "data" / "deep_dive_docs"
OEIL = "https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference={ref}"

# Gateway rows, flattened. Kept in step with audit_deep_dives._GATEWAY_ROW.
_ROW = re.compile(
    r"(Committee draft report|Committee opinion|Committee draft opinion|"
    r"Amendments tabled in committee|Specific opinion|"
    r"Committee report tabled for plenary[^A-Z]*|Committee recommendation[^A-Z]*|"
    r"Committee interim report[^A-Z]*|Text agreed during interinstitutional negotiations)"
    r"\s+([A-Z]{4}\s+)?(PE\d{3}\.\d{3}|A\d{1,2}-\d+/\d{4})\s+(\d{2}/\d{2}/\d{4})")

_AM = re.compile(r"^\s*Amendment\s+(\d+)\s*$", re.M)
_AM_RANGE = re.compile(r"AMENDMENTS?\s*\n\s*(\d+)\s*-\s*(\d+)")
_RAPP = re.compile(r"Rapporteurs?(?: for opinion)?:\s*([^\n]+)")
_DATE = re.compile(r"\n\s*(\d{1,2}\.\d{1,2}\.\d{4})\s*\n")
_TARGET = re.compile(
    r"Amendment\s+\d+\s*\n(?:.*\n)?\s*Proposal for a (?:regulation|directive|decision)\s*\n\s*(.{0,60})")
_TABLER = re.compile(r"^\s*Amendment\s+\d+\s*\n((?:\s*[^\n]{2,90}\n){1,6})", re.M)
_ROLLCALL = re.compile(r"\n\s*(\d+)\s*([+\-0])\s*\n")


_EP_COMMITTEES = {
    "foreign affairs": "AFET", "human rights": "DROI", "security and defence": "SEDE",
    "development": "DEVE", "international trade": "INTA", "budgets": "BUDG",
    "budgetary control": "CONT", "economic and monetary affairs": "ECON",
    "tax matters": "FISC", "employment and social affairs": "EMPL",
    "environment, climate and food safety": "ENVI", "environment, public health and food safety": "ENVI",
    "public health": "SANT", "industry, research and energy": "ITRE",
    "internal market and consumer protection": "IMCO", "transport and tourism": "TRAN",
    "regional development": "REGI", "agriculture and rural development": "AGRI",
    "fisheries": "PECH", "culture and education": "CULT", "legal affairs": "JURI",
    "civil liberties, justice and home affairs": "LIBE", "constitutional affairs": "AFCO",
    "women's rights and gender equality": "FEMM", "women\u2019s rights and gender equality": "FEMM",
    "petitions": "PETI", "housing crisis": "HOUS",
}


def _committee_from_header(path) -> str | None:
    """The committee code from a committee document's own first lines."""
    import re as _re
    try:
        head = " ".join(open(path, errors="ignore").read(1500).split()).lower()
    except OSError:
        return None
    m = _re.search(r"committee on (?:the )?([a-z ,\u2019']+?)(?: \d{4}/| amendments| draft| opinion| 20\d\d|$)", head)
    if not m:
        return None
    name = m.group(1).strip()
    for k, code in _EP_COMMITTEES.items():
        if name.startswith(k):
            return code
    return None


def slug(ref: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "_", ref).strip("_")


# --------------------------------------------------------------------------- OEIL

def oeil_page(ref: str) -> tuple[str, str]:
    """(plain text, raw html) of the live procedure file, via the WAF fetcher."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "wbf", str(_REPO_ROOT / "backend" / "services" / "scrapers" / "waf_browser_fetcher.py"))
    wbf = importlib.util.module_from_spec(spec)
    sys.modules["wbf"] = wbf
    spec.loader.exec_module(wbf)
    r = wbf.fetch_one(OEIL.format(ref=ref), expand_accordions=True, strip_chrome=False)
    return re.sub(r"[ \t]+", " ", r.text or ""), (r.html or "")


def gateway(text: str, html: str) -> List[dict]:
    """Parliament documents from the Documentation gateway, WITH their real links.

    The links matter: doceo paths are not derivable from a PE number. A joint
    committee file uses a CJnn prefix (CJ80 for the Industrial Accelerator Act,
    CJ53 for Biotech), an opinion uses <CTTE>-AD-, a draft report <CTTE>-PR-.
    Guessing produced 404s; the gateway states them.
    """
    flat = re.sub(r"\s+", " ", text)
    i = flat.find("Documentation gateway European Parliament")
    if i < 0:
        return []
    j = flat.find("European Commission Document type", i)
    block = flat[i:j if j > i else i + 4000]

    links = {}
    for url in set(re.findall(
            r"https://www\.europarl\.europa\.eu/doceo/document/[A-Za-z0-9_\-]+\.html", html)):
        digits = re.findall(r"(\d{6})_EN\.html$", url)
        if digits:
            links[f"PE{digits[0][:3]}.{digits[0][3:]}"] = url
        m = re.search(r"/A-(\d+)-(\d{4})-(\d+)_EN\.html$", url)
        if m:
            links[f"A{m.group(1)}-{m.group(3)}/{m.group(2)}"] = url

    out = []
    for m in _ROW.finditer(block):
        ref = m.group(3)
        out.append({"kind": m.group(1).strip(), "committee": (m.group(2) or "").strip() or None,
                    "ref": ref, "date": m.group(4), "url": links.get(ref)})
    return out


# OEIL prints the holder as SURNAME (caps) Forename (Group) dd/mm/yyyy, preceded
# by the committee code and its full name. Anchoring on "two or more consecutive
# capitals" stops the committee name bleeding into the surname, which is how
# "IMCO Internal Market and Consumer Protection IJABS Ivars" came out as a name.
# Structure in the regex, CASE in Python. An explicit [A-ZÀ-Ý] range silently
# excludes Latin Extended-A, so "KNOTEK Ondřej" (U+0159) was dropped from the
# Critical Medicines Act shadows and only six of seven were found. Same family
# as the accent-folding bug in audit_deep_dives: never hand-roll a letter range.
_PERSON_CAND = re.compile(r"([^\W\d_][^()\d]{2,60}?)\s*\(([^)]{1,32})\)", re.UNICODE)


def _people(segment: str) -> List[tuple]:
    """(name, group) pairs where the name looks like OEIL's SURNAME Forename."""
    out = []
    for raw, group in _PERSON_CAND.findall(segment):
        toks = [t for t in raw.replace("\u00a0", " ").split() if t]
        # walk back from the end: Forename(s) in title case, then an ALL-CAPS surname
        fore, i = [], len(toks) - 1
        while i >= 0 and toks[i][:1].isupper() and not toks[i].isupper():
            fore.insert(0, toks[i])
            i -= 1
        sur = []
        while i >= 0 and toks[i].isupper() and any(c.isalpha() for c in toks[i]):
            sur.insert(0, toks[i])
            i -= 1
        if sur and fore:
            out.append((" ".join(sur + fore), group.strip()))
    return out


def emeeting(ref: str) -> List[dict]:
    """Committee documents from eMeeting, in the gateway's shape.

    Needed because the two sources miss opposite things, proven on the same day:
    the Industrial Accelerator Act's draft report sat in OEIL's gateway while
    eMeeting had nothing, and the Digital Networks Act has six IMCO documents in
    eMeeting while OEIL's gateway for 2026/0013(COD) does not exist yet. Neither
    source alone is enough.
    """
    try:
        from dotenv import load_dotenv
        from sqlalchemy import create_engine, text as sql
    except ImportError:
        return []
    load_dotenv(str(_REPO_ROOT / "backend" / ".env"))
    url = os.environ.get("DATABASE_URL")
    if not url:
        return []
    KIND = {"draft_report": "Committee draft report", "amendment": "Amendments tabled in committee",
            "compromise_amendments": "Amendments tabled in committee",
            "draft_opinion": "Committee draft opinion", "opinion": "Committee opinion"}
    eng = create_engine(url.replace("postgresql://", "postgresql+psycopg2://"), pool_pre_ping=True)
    out = []
    with eng.connect() as c:
        for r in c.execute(sql("""
            SELECT DISTINCT ON (reference) reference, committee_code, doc_kind,
                   pdf_url, meeting_date
              FROM ep_emeeting_documents
             WHERE procedure_ref = :r AND reference IS NOT NULL AND pdf_url IS NOT NULL
               AND doc_kind IN ('draft_report','amendment','compromise_amendments',
                                'draft_opinion','opinion')
             ORDER BY reference, meeting_date DESC
        """), {"r": ref}).mappings():
            if not re.match(r"^PE\d{3}\.\d{3}$", str(r["reference"] or "")):
                continue
            out.append({"kind": KIND.get(r["doc_kind"], "Committee opinion"),
                        "committee": r["committee_code"], "ref": r["reference"],
                        "date": str(r["meeting_date"]), "url": r["pdf_url"],
                        "via": "emeeting"})
    return out


def merge(gw: List[dict], em: List[dict]) -> List[dict]:
    """Gateway wins on conflict; eMeeting fills what it has not published yet."""
    seen = {r["ref"] for r in gw}
    return gw + [r for r in em if r["ref"] not in seen]


def players(text: str) -> dict:
    flat = re.sub(r"\s+", " ", text)
    out: dict = {"joint": "Joint committee responsible" in flat}
    i = flat.find("Joint committee responsible")
    if i < 0:
        i = flat.find("Committee responsible")
    j = flat.find("Council of the European Union", i)
    block = flat[i:j] if i >= 0 and j > i else ""

    # Stop at the FORMER block, or a file that carried over a parliamentary term
    # reports the previous rapporteur as the current one.
    cur = block
    for marker in ("Former committee responsible", "Shadow rapporteur", "Committee for opinion"):
        k = cur.find(marker)
        if k > 0:
            cur = cur[:k]
            break
    out["rapporteurs"] = _people(cur)[:4]

    fm = block.find("Former committee responsible")
    if fm >= 0:
        seg = block[fm:fm + 400]
        out["former_rapporteurs"] = _people(seg)[:3]
    else:
        out["former_rapporteurs"] = []

    sh = block.find("Shadow rapporteur")
    if sh >= 0:
        end = block.find("Committee for opinion", sh)
        out["shadows"] = _people(block[sh:end if end > sh else sh + 1400])
    else:
        out["shadows"] = []
    m = re.search(r"Stage reached in procedure (.{3,70}?) (?:Committee dossier|Documentation)", flat)
    out["status"] = m.group(1).strip() if m else None
    f = flat.find("Forecasts Forecasts Date Subject")
    out["forecast"] = re.sub(r"\s+", " ", flat[f + 32:f + 110]).strip() if f >= 0 else None
    return out


# ------------------------------------------------------------------------ fetching

def fetch_documents(rows: List[dict], cache: pathlib.Path) -> dict:
    """Download every gateway document that is not cached, via a cleared browser."""
    cache.mkdir(parents=True, exist_ok=True)
    want = [r for r in rows if r.get("url") and not (cache / f"{slug(r['ref'])}.txt").exists()]
    stats = {"cached": len(rows) - len(want), "fetched": 0, "failed": []}
    if not want:
        return stats
    if not shutil.which("pdftotext"):
        stats["failed"].append("pdftotext not installed")
        return stats

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage",
                                    "--no-zygote", "--disable-gpu"])
        ctx = b.new_context(user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"))
        pg = ctx.new_page()
        # One navigation clears the challenge for the whole context.
        pg.goto(want[0]["url"], wait_until="domcontentloaded")
        pg.wait_for_timeout(6000)
        for r in want:
            pdf = r["url"] if r["url"].endswith(".pdf") else r["url"][:-5] + ".pdf"
            try:
                resp = ctx.request.get(pdf, timeout=150000)
                body = resp.body()
            except Exception as exc:                                  # noqa: BLE001
                stats["failed"].append(f"{r['ref']}: {exc}")
                continue
            if body[:4] != b"%PDF":
                stats["failed"].append(f"{r['ref']}: HTTP {resp.status}, not a PDF")
                continue
            base = cache / slug(r["ref"])
            base.with_suffix(".pdf").write_bytes(body)
            subprocess.run(["pdftotext", "-layout", str(base.with_suffix(".pdf")),
                            str(base.with_suffix(".txt"))], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            base.with_suffix(".pdf").unlink(missing_ok=True)   # keep the text, drop 0.5 MB
            stats["fetched"] += 1
        b.close()
    return stats


# ------------------------------------------------------------------------- parsing

def _tablers(text: str) -> Counter:
    c: Counter = Counter()
    for m in _TABLER.finditer(text):
        for line in m.group(1).split("\n"):
            line = line.strip()
            if not line or line.startswith(("Proposal for", "Draft report", "Draft opinion")):
                break
            c[line] += 1
    return c


def _targets(text: str) -> Counter:
    c: Counter = Counter()
    for g in _TARGET.findall(text):
        g = re.sub(r"\s+", " ", g).strip()
        m = re.match(r"(Recital \S+|Article \d+ ?\w?|Annex\S*)", g)
        if m:
            c[m.group(1).strip()] += 1
    return c


def parse_one(path: pathlib.Path) -> dict:
    t = path.read_text(errors="replace")
    nums = [int(x) for x in _AM.findall(t)]
    d = _DATE.search(t)
    rp = _RAPP.search(t)
    hdr = _AM_RANGE.search(t)
    return {"amendments": len(nums), "ids": nums,
            "header_range": list(hdr.groups()) if hdr else None,
            "date": d.group(1) if d else None,
            "rapporteur": rp.group(1).strip() if rp else None,
            "explanatory_statement": t.rfind("EXPLANATORY STATEMENT") > 2000,
            "tablers": _tablers(t), "targets": _targets(t), "text_len": len(t)}


def rollcall(path: pathlib.Path) -> Optional[dict]:
    t = path.read_text(errors="replace")
    i = t.rfind("FINAL VOTE BY ROLL CALL")
    if i < 0:
        return None
    pairs = _ROLLCALL.findall(t[i:i + 3000])
    got = {s: int(n) for n, s in pairs if s in "+-0"}
    if "+" not in got:
        return None
    return {"for": got.get("+"), "against": got.get("-"), "abstain": got.get("0")}


def brief(ref: str, do_fetch: bool) -> dict:
    text, html = oeil_page(ref)
    rows = merge(gateway(text, html), emeeting(ref))
    cache = CACHE / slug(ref)
    if do_fetch:
        stats = fetch_documents(rows, cache)
    else:
        # Report what IS cached even when not fetching, or a cache-only run
        # reads "0 cached" while happily parsing the files it just found.
        have = sum(1 for r in rows if (cache / f"{slug(r['ref'])}.txt").exists())
        stats = {"cached": have, "fetched": 0, "failed": []}

    res: dict = {"ref": ref, "players": players(text), "documents": rows,
                 "fetch": stats, "draft_report": None, "member_amendments": None,
                 "opinions": [], "opinion_amendments": [], "report_vote": None}

    # Amendments belong to a SERIES, and each committee numbers its own. Pooling
    # them produced 2,807 amendments with 137 gaps on Biotech where the real lead
    # figure is 2,595 contiguous: the extra documents were ITRE/ENVI/IMCO/JURI
    # amendments to their own draft OPINIONS. The contiguity check caught it,
    # which is the whole reason it reports gaps instead of smoothing them.
    series: Dict[str, dict] = {}
    n_docs = 0

    for r in rows:
        f = cache / f"{slug(r['ref'])}.txt"
        if not f.exists():
            continue
        kind = r["kind"].lower()
        if "draft report" in kind:
            p = parse_one(f)
            res["draft_report"] = {"ref": r["ref"], "date": p["date"],
                                  "rapporteur": p["rapporteur"], "amendments": p["amendments"],
                                  "explanatory_statement": p["explanatory_statement"],
                                  "targets": dict(p["targets"].most_common(8))}
        elif "amendments tabled" in kind:
            p = parse_one(f)
            # The document's OWN header names its committee (24 Sep 2026). The
            # gateway row carries the LEAD committee for every amendment
            # document, so IMCO's and LIBE's amendments to their own draft
            # opinions on 2025/2118(INI) were merged into one "AFCO" series.
            key = _committee_from_header(f) or r.get("committee") or "_lead"
            g = series.setdefault(key, {"ids": [], "tablers": Counter(),
                                        "targets": Counter(), "docs": 0, "refs": []})
            g["ids"] += p["ids"]
            g["tablers"] += p["tablers"]
            g["targets"] += p["targets"]
            g["docs"] += 1
            g["refs"].append(r["ref"])
            n_docs += 1
        elif "opinion" in kind:
            p = parse_one(f)
            res["opinions"].append({"committee": r["committee"], "ref": r["ref"],
                                    "date": p["date"], "rapporteur": p["rapporteur"],
                                    "amendments": p["amendments"]})
        elif "report tabled" in kind:
            res["report_vote"] = {"ref": r["ref"], **(rollcall(f) or {})}

    def stats(g: dict) -> dict:
        ids = sorted(set(g["ids"]))
        gaps = [x for x in range(ids[0], ids[-1] + 1) if x not in set(ids)]
        return {"documents": g["docs"], "refs": g["refs"],
                # DISTINCT count, never max(id). "405 amendments" was 380.
                "count": len(ids), "first": ids[0], "last": ids[-1], "gaps": len(gaps),
                "top_tablers": g["tablers"].most_common(10),
                "most_contested": g["targets"].most_common(10)}

    if series:
        scored = {k: stats(g) for k, g in series.items() if g["ids"]}
        # The lead series is the one that CONTINUES the draft report's numbering.
        # Falling back to the largest is safe: an opinion series is always smaller.
        after = (res["draft_report"]["amendments"] + 1) if res["draft_report"] else None
        lead = next((k for k, v in scored.items() if after and v["first"] == after), None)
        if lead is None:
            lead = max(scored, key=lambda k: scored[k]["count"])
        res["member_amendments"] = scored.pop(lead)
        res["member_amendments"]["committee"] = None if lead == "_lead" else lead
        res["opinion_amendments"] = [dict(v, committee=k) for k, v in scored.items()]
    return res


# -------------------------------------------------------------------------- output

def render(b: dict) -> None:
    p = b["players"]
    print(f"\n{'=' * 78}\n{b['ref']}   {p.get('status') or '(status unknown)'}")
    if p.get("forecast"):
        print(f"forecast: {p['forecast']}")
    if p.get("joint"):
        print("JOINT COMMITTEE file (Rule 58): no single rapporteur")
    if p.get("rapporteurs"):
        print("rapporteur(s): " + "; ".join(f"{n} ({g})" for n, g in p["rapporteurs"]))
    if p.get("former_rapporteurs"):
        print("former: " + "; ".join(f"{n} ({g})" for n, g in p["former_rapporteurs"]))
    if p.get("shadows"):
        print(f"shadows: {len(p['shadows'])}  " + ", ".join(n for n, _ in p["shadows"][:8]))

    f = b["fetch"]
    via_em = sum(1 for d in b["documents"] if d.get("via") == "emeeting")
    print(f"\ndocuments: {len(b['documents'])} ({len(b['documents'])-via_em} gateway, {via_em} eMeeting), "
          f"{f['cached']} cached, {f['fetched']} fetched"
          + (f", {len(f['failed'])} FAILED" if f["failed"] else ""))
    for x in f["failed"][:5]:
        print(f"   [WARN] {x}")

    dr = b["draft_report"]
    if dr:
        print(f"\nDRAFT REPORT {dr['ref']}  {dr['date']}  {dr['rapporteur']}")
        print(f"   {dr['amendments']} amendments"
              f"{'; explanatory statement present' if dr['explanatory_statement'] else ''}")
        if dr["targets"]:
            print("   most amended: " + ", ".join(f"{k} ({v})" for k, v in list(dr["targets"].items())[:5]))

    ma = b["member_amendments"]
    if ma:
        warn = "" if ma["gaps"] == 0 else f"  [WARN] {ma['gaps']} gap(s) in the range"
        print(f"\nMEMBER AMENDMENTS: {ma['count']} across {ma['documents']} document(s)")
        print(f"   numbered {ma['first']} to {ma['last']}{warn}")
        print(f"   NOTE: {ma['last']} is the highest NUMBER, the count is {ma['count']}")
        print("   top tablers:")
        for who, n in ma["top_tablers"][:6]:
            print(f"      {n:>5}  {who[:66]}")
        print("   most contested: " + ", ".join(f"{k} ({v})" for k, v in ma["most_contested"][:6]))

    for oa in b.get("opinion_amendments", []):
        print(f"\n   (separate series) {oa['committee']} amendments: {oa['count']}, "
              f"numbered {oa['first']} to {oa['last']}, {oa['documents']} document(s)")

    if b["opinions"]:
        print("\nOPINIONS:")
        for o in b["opinions"]:
            print(f"   {str(o['committee'] or '?'):<5} {o['ref']}  {o['amendments']:>4} amendments"
                  f"  {o['rapporteur'] or ''}  {o['date'] or ''}")
    if b["report_vote"] and b["report_vote"].get("for") is not None:
        v = b["report_vote"]
        print(f"\nCOMMITTEE VOTE ({v['ref']}): {v['for']} for, {v['against']} against, "
              f"{v['abstain']} abstentions")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ref", help='procedure reference, e.g. "2025/0102(COD)"')
    ap.add_argument("--all", action="store_true", help="every deep-dive in DEEP_DIVES")
    ap.add_argument("--fetch", action="store_true", help="download documents not yet cached")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.all:
        from services.comparator.deep_dives import DEEP_DIVES
        refs = [d["procedure_ref"] for d in DEEP_DIVES if d.get("procedure_ref")]
    elif a.ref:
        refs = [a.ref]
    else:
        ap.error("give --ref or --all")

    out = []
    for r in refs:
        try:
            b = brief(r, a.fetch)
        except Exception as exc:                                      # noqa: BLE001
            print(f"[ERROR] {r}: {exc}")
            continue
        out.append(b)
        if not a.json:
            render(b)
    if a.json:
        print(json.dumps(out, indent=1, default=str, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
